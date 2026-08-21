from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QImage, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from digital_paint.core.palette import PaletteColor, load_palette_json
from digital_paint.core.pipeline import ProductionResult, build_production_result, color_code_map
from digital_paint.core.quantize import load_rgb_image, save_rgb_png
from digital_paint.core.runtime import CancellationToken, PipelineCancelled
from digital_paint.core.vector import export_line_svg, export_vector_pdf

APP_LABEL = "V100 RC1"


class WorkerSignals(QObject):
    finished = Signal(object)
    cancelled = Signal()
    error = Signal(str)


class ProductionWorker(QRunnable):
    def __init__(
        self,
        image_rgb: np.ndarray,
        colors: int,
        min_area: int,
        palette: list[PaletteColor] | None,
        memory_budget_mb: float,
        cache_dir: Path,
        token: CancellationToken,
    ) -> None:
        super().__init__()
        self.image_rgb = image_rgb
        self.colors = colors
        self.min_area = min_area
        self.palette = palette
        self.memory_budget_mb = memory_budget_mb
        self.cache_dir = cache_dir
        self.token = token
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = build_production_result(
                self.image_rgb,
                self.colors,
                min_region_area=self.min_area,
                custom_palette=self.palette,
                cancellation=self.token,
                cache_dir=self.cache_dir,
                memory_budget_mb=self.memory_budget_mb,
            )
        except PipelineCancelled:
            self.signals.cancelled.emit()
            return
        except Exception as exc:
            self.signals.error.emit(f"{type(exc).__name__}: {exc}")
            return
        self.signals.finished.emit(result)


class ZoomableImageView(QGraphicsView):
    """Image preview with wheel zoom, drag-to-pan and fit-to-window reset."""

    def __init__(self, placeholder: str) -> None:
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        self.placeholder = placeholder
        self.setMinimumSize(420, 420)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(Qt.GlobalColor.black)
        self._has_image = False

    def set_array(self, image_rgb: np.ndarray) -> None:
        array = np.ascontiguousarray(image_rgb.astype(np.uint8))
        h, w, _ = array.shape
        qimage = QImage(array.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
        self.pixmap_item.setPixmap(QPixmap.fromImage(qimage))
        self.scene.setSceneRect(self.pixmap_item.boundingRect())
        self._has_image = True
        self.fit_image()

    def clear_image(self) -> None:
        self.pixmap_item.setPixmap(QPixmap())
        self.scene.setSceneRect(0, 0, 1, 1)
        self._has_image = False

    def fit_image(self) -> None:
        if self._has_image:
            self.resetTransform()
            self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if not self._has_image:
            return super().wheelEvent(event)
        factor = 1.20 if event.angleDelta().y() > 0 else 1 / 1.20
        current = self.transform().m11()
        target = current * factor
        if 0.03 <= target <= 40.0:
            self.scale(factor, factor)
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self.fit_image()
        super().mouseDoubleClickEvent(event)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"数字油画生产软件 {APP_LABEL}")
        self.resize(1440, 900)

        self.thread_pool = QThreadPool.globalInstance()
        self.source_path: Path | None = None
        self.source_image: np.ndarray | None = None
        self.result: ProductionResult | None = None
        self.custom_palette: list[PaletteColor] | None = None
        self.active_token: CancellationToken | None = None
        self.cache_dir = Path.home() / ".digital_paint_by_numbers" / "cache"

        self.open_button = QPushButton("导入原图")
        self.palette_button = QPushButton("导入自有色库 JSON")
        self.process_button = QPushButton("生成生产结果")
        self.cancel_button = QPushButton("取消处理")
        self.fit_button = QPushButton("预览适应窗口")
        self.png_button = QPushButton("导出效果图 PNG")
        self.svg_button = QPushButton("导出编号线稿 SVG")
        self.pdf_button = QPushButton("导出三页矢量 PDF")
        self.qc_button = QPushButton("导出 QC JSON")

        self.color_spin = QSpinBox()
        self.color_spin.setRange(2, 256)
        self.color_spin.setValue(24)
        self.color_spin.setSuffix(" 色")
        self.min_area_spin = QSpinBox()
        self.min_area_spin.setRange(1, 10000)
        self.min_area_spin.setValue(40)
        self.min_area_spin.setSuffix(" px")
        self.memory_spin = QSpinBox()
        self.memory_spin.setRange(256, 32768)
        self.memory_spin.setValue(2048)
        self.memory_spin.setSingleStep(256)
        self.memory_spin.setSuffix(" MB")

        self.source_preview = ZoomableImageView("原图预览")
        self.result_preview = ZoomableImageView("效果图预览")
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(210)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFormat("就绪")

        controls1 = QHBoxLayout()
        controls1.addWidget(self.open_button)
        controls1.addWidget(self.palette_button)
        controls1.addWidget(QLabel("目标色数:"))
        controls1.addWidget(self.color_spin)
        controls1.addWidget(QLabel("最小色块:"))
        controls1.addWidget(self.min_area_spin)
        controls1.addWidget(QLabel("内存预算:"))
        controls1.addWidget(self.memory_spin)
        controls1.addWidget(self.process_button)
        controls1.addWidget(self.cancel_button)
        controls1.addStretch(1)

        controls2 = QHBoxLayout()
        controls2.addWidget(self.fit_button)
        controls2.addWidget(self.png_button)
        controls2.addWidget(self.svg_button)
        controls2.addWidget(self.pdf_button)
        controls2.addWidget(self.qc_button)
        controls2.addStretch(1)

        previews = QHBoxLayout()
        previews.addWidget(self.source_preview, 1)
        previews.addWidget(self.result_preview, 1)

        layout = QVBoxLayout()
        layout.addLayout(controls1)
        layout.addLayout(controls2)
        layout.addWidget(self.progress)
        layout.addLayout(previews, 1)
        layout.addWidget(QLabel("运行日志 / QC / 性能摘要"))
        layout.addWidget(self.log)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self.open_button.clicked.connect(self.open_image)
        self.palette_button.clicked.connect(self.open_palette)
        self.process_button.clicked.connect(self.start_processing)
        self.cancel_button.clicked.connect(self.cancel_processing)
        self.fit_button.clicked.connect(self.fit_previews)
        self.png_button.clicked.connect(self.export_png)
        self.svg_button.clicked.connect(self.export_svg)
        self.pdf_button.clicked.connect(self.export_pdf)
        self.qc_button.clicked.connect(self.export_qc)

        self.cancel_button.setEnabled(False)
        self._set_result_actions(False)
        self.process_button.setEnabled(False)
        self._log(f"{APP_LABEL} 已启动。滚轮缩放、鼠标拖动画面；双击预览可恢复适应窗口。")
        self._log("生产链：分色 → 结构保护 → 碎块优化 → 自有色库 CIEDE2000 → 编号 → QC → SVG/PDF。")

    @Slot()
    def open_image(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "选择原图", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All Files (*)"
        )
        if not filename:
            return
        try:
            image = load_rgb_image(filename, max_side=10000)
        except Exception as exc:
            self._show_error(f"图片读取失败：{exc}")
            return
        self.source_path = Path(filename)
        self.source_image = image
        self.result = None
        self.source_preview.set_array(image)
        self.result_preview.clear_image()
        self.process_button.setEnabled(True)
        self._set_result_actions(False)
        megapixels = image.shape[1] * image.shape[0] / 1_000_000
        self._log(f"已导入：{self.source_path.name}，{image.shape[1]}×{image.shape[0]}，{megapixels:.2f} MP")

    @Slot()
    def open_palette(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "选择自有色库", "", "Palette JSON (*.json)")
        if not filename:
            return
        try:
            self.custom_palette = load_palette_json(filename)
        except Exception as exc:
            self._show_error(f"色库读取失败：{exc}")
            return
        self._log(f"已加载自有色库：{len(self.custom_palette)} 色；正式匹配使用 CIEDE2000。")

    @Slot()
    def start_processing(self) -> None:
        if self.source_image is None:
            return
        self.active_token = CancellationToken()
        self._set_busy(True)
        self.progress.setRange(0, 0)
        self.progress.setFormat("处理中……")
        self._log(f"开始 {APP_LABEL} 生产流水线……")
        worker = ProductionWorker(
            self.source_image.copy(),
            self.color_spin.value(),
            self.min_area_spin.value(),
            self.custom_palette,
            float(self.memory_spin.value()),
            self.cache_dir,
            self.active_token,
        )
        worker.signals.finished.connect(self._processing_finished)
        worker.signals.cancelled.connect(self._processing_cancelled)
        worker.signals.error.connect(self._processing_failed)
        self.thread_pool.start(worker)

    @Slot()
    def cancel_processing(self) -> None:
        if self.active_token is not None:
            self.active_token.cancel()
            self.cancel_button.setEnabled(False)
            self._log("已请求取消；将在当前安全阶段结束后停止。")

    @Slot(object)
    def _processing_finished(self, result: ProductionResult) -> None:
        self.active_token = None
        self.result = result
        self.result_preview.set_array(result.effect_rgb)
        self._set_busy(False)
        self._set_result_actions(True)
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.progress.setFormat("完成")
        counts = result.qc.counts()
        plan = result.memory_plan
        self._log(
            f"完成：{len(result.palette_rgb)} 色，{len(result.regions.regions)} 个区域；"
            f"QC PASS={counts['PASS']} WARN={counts['WARN']} FAIL={counts['FAIL']}。"
        )
        self._log(
            f"性能：{result.performance.total_seconds:.2f}s；估算内存 {plan.estimated_mb:.0f}MB / "
            f"预算 {plan.budget_mb:.0f}MB；Tile={'是' if plan.use_tiles else '否'}；"
            f"缓存命中={','.join(result.cache_hits) if result.cache_hits else '无'}。"
        )
        gate = result.performance_gate
        self._log(f"性能门禁：{'PASS' if gate.passed else 'WARN'}；{'；'.join(gate.reasons) if gate.reasons else '正常'}")
        for item in result.qc.items:
            self._log(f"[{item.status}] {item.code}: {item.message}")

    @Slot()
    def _processing_cancelled(self) -> None:
        self.active_token = None
        self._set_busy(False)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFormat("已取消")
        self._log("处理已安全取消。")

    @Slot(str)
    def _processing_failed(self, message: str) -> None:
        self.active_token = None
        self._set_busy(False)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFormat("失败")
        self._show_error(f"生产处理失败：{message}")

    @Slot()
    def fit_previews(self) -> None:
        self.source_preview.fit_image()
        self.result_preview.fit_image()

    @Slot()
    def export_png(self) -> None:
        if self.result is None:
            return
        filename = self._save_name("效果图", "effect_v100_rc1.png", "PNG (*.png)", ".png")
        if filename:
            save_rgb_png(self.result.effect_rgb, filename)
            self._log(f"已导出 PNG：{filename}")

    @Slot()
    def export_svg(self) -> None:
        if self.result is None:
            return
        filename = self._save_name("编号线稿", "linework_v100_rc1.svg", "SVG (*.svg)", ".svg")
        if filename:
            export_line_svg(
                filename,
                self.result.region_id,
                self.result.regions.regions,
                self.result.labels,
                color_code_map(self.result),
            )
            self._log(f"已导出 SVG：{filename}")

    @Slot()
    def export_pdf(self) -> None:
        if self.result is None:
            return
        filename = self._save_name("矢量 PDF", "production_v100_rc1.pdf", "PDF (*.pdf)", ".pdf")
        if filename:
            export_vector_pdf(
                filename,
                self.result.region_id,
                self.result.regions.regions,
                self.result.labels,
                self.result.palette_rgb,
                color_code_map(self.result),
            )
            self._log(f"已导出三页矢量 PDF：{filename}")

    @Slot()
    def export_qc(self) -> None:
        if self.result is None:
            return
        filename = self._save_name("QC 报告", "qc_v100_rc1.json", "JSON (*.json)", ".json")
        if filename:
            self.result.qc.save_json(filename)
            self._log(f"已导出 QC：{filename}")

    def _save_name(self, title: str, fallback: str, file_filter: str, suffix: str) -> str | None:
        suggested = fallback if self.source_path is None else f"{self.source_path.stem}_{fallback}"
        filename, _ = QFileDialog.getSaveFileName(self, f"导出{title}", suggested, file_filter)
        if not filename:
            return None
        return filename if filename.lower().endswith(suffix) else filename + suffix

    def _set_result_actions(self, enabled: bool) -> None:
        for button in (self.png_button, self.svg_button, self.pdf_button, self.qc_button):
            button.setEnabled(enabled)

    def _set_busy(self, busy: bool) -> None:
        self.open_button.setEnabled(not busy)
        self.palette_button.setEnabled(not busy)
        self.color_spin.setEnabled(not busy)
        self.min_area_spin.setEnabled(not busy)
        self.memory_spin.setEnabled(not busy)
        self.process_button.setEnabled(not busy and self.source_image is not None)
        self.cancel_button.setEnabled(busy)
        self._set_result_actions(not busy and self.result is not None)

    def _log(self, text: str) -> None:
        self.log.append(text)

    def _show_error(self, text: str) -> None:
        self._log(text)
        QMessageBox.critical(self, "错误", text)
