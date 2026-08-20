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

from digital_paint.core.quantize import QuantizationResult, load_rgb_image, quantize_lab, save_rgb_png


class WorkerSignals(QObject):
    finished = Signal(object)
    error = Signal(str)


class QuantizeWorker(QRunnable):
    def __init__(self, image_rgb: np.ndarray, colors: int) -> None:
        super().__init__()
        self.image_rgb = image_rgb
        self.colors = colors
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = quantize_lab(self.image_rgb, self.colors)
        except Exception as exc:  # UI boundary: convert processing failures into readable logs.
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

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        super().resizeEvent(event)
        self._refresh_pixmap()

    def _refresh_pixmap(self) -> None:
        if self._pixmap is None:
            return
        scaled = self._pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("数字油画生产软件 V0.1")
        self.resize(1200, 780)

        self.thread_pool = QThreadPool.globalInstance()
        self.source_path: Path | None = None
        self.source_image: np.ndarray | None = None
        self.result: QuantizationResult | None = None

        self.open_button = QPushButton("导入 JPG / PNG")
        self.process_button = QPushButton("生成数字油画效果图")
        self.export_button = QPushButton("导出 PNG")
        self.process_button.setEnabled(False)
        self.export_button.setEnabled(False)

        self.color_spin = QSpinBox()
        self.color_spin.setRange(2, 256)
        self.color_spin.setValue(24)
        self.color_spin.setSuffix(" 色")

        self.source_preview = ImagePreview("原图预览")
        self.result_preview = ImagePreview("效果图预览")
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(150)

        controls = QHBoxLayout()
        controls.addWidget(self.open_button)
        controls.addWidget(QLabel("目标色数:"))
        controls.addWidget(self.color_spin)
        controls.addWidget(self.process_button)
        controls.addWidget(self.export_button)
        controls.addStretch(1)

        previews = QHBoxLayout()
        previews.addWidget(self.source_preview, 1)
        previews.addWidget(self.result_preview, 1)

        layout = QVBoxLayout()
        layout.addLayout(controls)
        layout.addLayout(previews, 1)
        layout.addWidget(QLabel("运行日志"))
        layout.addWidget(self.log)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self.open_button.clicked.connect(self.open_image)
        self.process_button.clicked.connect(self.start_quantize)
        self.export_button.clicked.connect(self.export_result)
        self._log("V0.1 已启动。请先导入 JPG/PNG 图片。")

    @Slot()
    def open_image(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "选择原图",
            "",
            "Images (*.png *.jpg *.jpeg *.webp);;All Files (*)",
        )
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
        self.export_button.setEnabled(False)
        self._log(f"已导入：{self.source_path.name}，尺寸 {image.shape[1]}×{image.shape[0]}")

    @Slot()
    def start_quantize(self) -> None:
        if self.source_image is None:
            return
        colors = self.color_spin.value()
        self._set_busy(True)
        self._log(f"开始 Lab + KMeans 分色，目标 {colors} 色……")
        worker = QuantizeWorker(self.source_image.copy(), colors)
        worker.signals.finished.connect(self._quantize_finished)
        worker.signals.error.connect(self._quantize_failed)
        self.thread_pool.start(worker)

    @Slot(object)
    def _quantize_finished(self, result: QuantizationResult) -> None:
        self.result = result
        self.result_preview.set_array(result.image_rgb)
        self.export_button.setEnabled(True)
        self._set_busy(False)
        self._log(
            f"分色完成：{len(result.palette_rgb)} 色；已保留 color_id / region_id 数据接口，供后续线稿与区域分析使用。"
        )

    @Slot(str)
    def _quantize_failed(self, message: str) -> None:
        self._set_busy(False)
        self._show_error(f"分色失败：{message}")

    @Slot()
    def export_result(self) -> None:
        if self.result is None:
            return
        suggested = "paint_by_numbers_v01.png"
        if self.source_path is not None:
            suggested = f"{self.source_path.stem}_paint_v01.png"
        filename, _ = QFileDialog.getSaveFileName(self, "导出效果图", suggested, "PNG (*.png)")
        if not filename:
            return
        if not filename.lower().endswith(".png"):
            filename += ".png"
        try:
            save_rgb_png(self.result.image_rgb, filename)
        except Exception as exc:
            self._show_error(f"导出失败：{exc}")
            return
        self._log(f"已导出：{filename}")

    def _set_busy(self, busy: bool) -> None:
        self.open_button.setEnabled(not busy)
        self.process_button.setEnabled(not busy and self.source_image is not None)
        self.color_spin.setEnabled(not busy)
        if busy:
            self.export_button.setEnabled(False)
        elif self.result is not None:
            self.export_button.setEnabled(True)

    def _log(self, text: str) -> None:
        self.log.append(text)

    def _show_error(self, text: str) -> None:
        self._log(text)
        QMessageBox.critical(self, "错误", text)
