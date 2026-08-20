from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from digital_paint.core.palette import PaletteColor, load_palette_json
from digital_paint.core.pipeline import ProductionResult, build_production_result, color_code_map
from digital_paint.core.quantize import load_rgb_image, save_rgb_png
from digital_paint.core.vector import export_line_svg, export_vector_pdf


class WorkerSignals(QObject):
    finished = Signal(object)
    error = Signal(str)


class ProductionWorker(QRunnable):
    def __init__(self, image_rgb: np.ndarray, colors: int, min_area: int, palette: list[PaletteColor] | None) -> None:
        super().__init__()
        self.image_rgb = image_rgb
        self.colors = colors
        self.min_area = min_area
        self.palette = palette
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = build_production_result(
                self.image_rgb,
                self.colors,
                min_region_area=self.min_area,
                custom_palette=self.palette,
            )
        except Exception as exc:
            self.signals.error.emit(f"{type(exc).__name__}: {exc}")
            return
        self.signals.finished.emit(result)


class ImagePreview(QLabel):
    def __init__(self, placeholder: str) -> None:
        super().__init__(placeholder)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(420, 420)
        self.setStyleSheet("QLabel { border: 1px solid #888; background: #202020; color: #ddd; }")
        self._pixmap: QPixmap | None = None

    def set_array(self, image_rgb: np.ndarray) -> None:
        array = np.ascontiguousarray(image_rgb.astype(np.uint8))
        h, w, _ = array.shape
        qimage = QImage(array.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
        self._pixmap = QPixmap.fromImage(qimage)
        self._refresh_pixmap()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._refresh_pixmap()

    def _refresh_pixmap(self) -> None:
        if self._pixmap is None:
            return
        self.setPixmap(self._pixmap.scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        ))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("数字油画生产软件 V6")
        self.resize(1360, 840)

        self.thread_pool = QThreadPool.globalInstance()
        self.source_path: Path | None = None
        self.source_image: np.ndarray | None = None
        self.result: ProductionResult | None = None
        self.custom_palette: list[PaletteColor] | None = None

        self.open_button = QPushButton("导入原图")
        self.palette_button = QPushButton("导入自有色库 JSON")
        self.process_button = QPushButton("生成 V6 生产结果")
        self.png_button = QPushButton("导出效果图 PNG")
        self.svg_button = QPushButton("导出线稿 SVG")
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

        self.source_preview = ImagePreview("原图预览")
        self.result_preview = ImagePreview("效果图预览")
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(180)

        controls1 = QHBoxLayout()
        controls1.addWidget(self.open_button)
        controls1.addWidget(self.palette_button)
        controls1.addWidget(QLabel("目标色数:"))
        controls1.addWidget(self.color_spin)
        controls1.addWidget(QLabel("最小色块:"))
        controls1.addWidget(self.min_area_spin)
        controls1.addWidget(self.process_button)
        controls1.addStretch(1)

        controls2 = QHBoxLayout()
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
        layout.addLayout(previews, 1)
        layout.addWidget(QLabel("运行日志 / QC 摘要"))
        layout.addWidget(self.log)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self.open_button.clicked.connect(self.open_image)
        self.palette_button.clicked.connect(self.open_palette)
        self.process_button.clicked.connect(self.start_processing)
        self.png_button.clicked.connect(self.export_png)
        self.svg_button.clicked.connect(self.export_svg)
        self.pdf_button.clicked.connect(self.export_pdf)
        self.qc_button.clicked.connect(self.export_qc)
        self._set_result_actions(False)
        self.process_button.setEnabled(False)
        self._log("V6 已启动：分色 → 区域化 → 碎块合并 → 编号 → 色库 → 矢量输出 → QC。")

    @Slot()
    def open_image(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "选择原图", "", "Images (*.png *.jpg *.jpeg *.webp);;All Files (*)")
        if not filename:
            return
        try:
            image = load_rgb_image(filename)
        except Exception as exc:
            self._show_error(f"图片读取失败：{exc}")
            return
        self.source_path = Path(filename)
        self.source_image = image
        self.result = None
        self.source_preview.set_array(image)
        self.result_preview.clear()
        self.result_preview.setText("效果图预览")
        self.process_button.setEnabled(True)
        self._set_result_actions(False)
        self._log(f"已导入：{self.source_path.name}，{image.shape[1]}×{image.shape[0]}")

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
        self._log(f"已加载自有色库：{len(self.custom_palette)} 色。正式色号将在 Lab 空间匹配。")

    @Slot()
    def start_processing(self) -> None:
        if self.source_image is None:
            return
        self._set_busy(True)
        self._log("开始 V6 生产流水线……")
        worker = ProductionWorker(
            self.source_image.copy(), self.color_spin.value(), self.min_area_spin.value(), self.custom_palette
        )
        worker.signals.finished.connect(self._processing_finished)
        worker.signals.error.connect(self._processing_failed)
        self.thread_pool.start(worker)

    @Slot(object)
    def _processing_finished(self, result: ProductionResult) -> None:
        self.result = result
        self.result_preview.set_array(result.effect_rgb)
        self._set_busy(False)
        self._set_result_actions(True)
        counts = result.qc.counts()
        self._log(
            f"完成：{len(result.palette_rgb)} 色，{len(result.regions.regions)} 个连通区域；"
            f"QC PASS={counts['PASS']} WARN={counts['WARN']} FAIL={counts['FAIL']}。"
        )
        for item in result.qc.items:
            self._log(f"[{item.status}] {item.code}: {item.message}")

    @Slot(str)
    def _processing_failed(self, message: str) -> None:
        self._set_busy(False)
        self._show_error(f"生产处理失败：{message}")

    @Slot()
    def export_png(self) -> None:
        if self.result is None:
            return
        filename = self._save_name("效果图", "paint_v6.png", "PNG (*.png)", ".png")
        if filename:
            save_rgb_png(self.result.effect_rgb, filename)
            self._log(f"已导出 PNG：{filename}")

    @Slot()
    def export_svg(self) -> None:
        if self.result is None:
            return
        filename = self._save_name("线稿", "linework_v6.svg", "SVG (*.svg)", ".svg")
        if filename:
            export_line_svg(
                filename, self.result.region_id, self.result.regions.regions, self.result.labels, color_code_map(self.result)
            )
            self._log(f"已导出 SVG：{filename}")

    @Slot()
    def export_pdf(self) -> None:
        if self.result is None:
            return
        filename = self._save_name("矢量 PDF", "production_v6.pdf", "PDF (*.pdf)", ".pdf")
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
        filename = self._save_name("QC 报告", "qc_v6.json", "JSON (*.json)", ".json")
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
        self.process_button.setEnabled(not busy and self.source_image is not None)
        self._set_result_actions(not busy and self.result is not None)

    def _log(self, text: str) -> None:
        self.log.append(text)

    def _show_error(self, text: str) -> None:
        self._log(text)
        QMessageBox.critical(self, "错误", text)
