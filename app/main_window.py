"""Main window for the Windows desktop application."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
from PySide6.QtCore import QThread
from PySide6.QtGui import QAction, QCloseEvent, QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.image_view import ImageView
from app.worker import GenerationWorker
from core.export.png import export_png
from core.models import PaintByNumbersResult
from core.pipeline import PipelineConfig


def array_to_pixmap(image: np.ndarray) -> QPixmap:
    """Convert an RGB uint8 array to a detached QPixmap."""
    contiguous = np.ascontiguousarray(image, dtype=np.uint8)
    height, width, channels = contiguous.shape
    if channels != 3:
        raise ValueError("预览图像必须是 RGB 三通道")
    qimage = QImage(
        contiguous.data, width, height, contiguous.strides[0], QImage.Format.Format_RGB888
    ).copy()
    return QPixmap.fromImage(qimage)


class MainWindow(QMainWindow):
    """Import, generate, inspect, and export a paint-by-numbers result."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("数字油画生产软件 V0.1")
        self.resize(1280, 800)
        self._source: np.ndarray | None = None
        self._result: PaintByNumbersResult | None = None
        self._thread: QThread | None = None
        self._worker: GenerationWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        toolbar = QToolBar("文件", self)
        self.addToolBar(toolbar)
        open_action = QAction("导入图片", self)
        open_action.triggered.connect(self.open_image)
        toolbar.addAction(open_action)
        export_action = QAction("导出 PNG", self)
        export_action.triggered.connect(self.export_result)
        toolbar.addAction(export_action)
        controls = QWidget()
        layout = QVBoxLayout(controls)
        layout.addWidget(QLabel("目标色数"))
        self.color_combo = QComboBox()
        self.color_combo.addItems(["12", "24", "36", "50", "自定义"])
        self.color_combo.setCurrentText("24")
        layout.addWidget(self.color_combo)
        self.custom_colors = QSpinBox()
        self.custom_colors.setRange(2, 128)
        self.custom_colors.setValue(24)
        self.custom_colors.setEnabled(False)
        self.color_combo.currentTextChanged.connect(
            lambda value: self.custom_colors.setEnabled(value == "自定义")
        )
        layout.addWidget(self.custom_colors)
        self.generate_button = QPushButton("生成效果图")
        self.generate_button.clicked.connect(self.generate)
        layout.addWidget(self.generate_button)
        self.optimize_button = QPushButton("优化碎块（V0.2 基础版）")
        self.optimize_button.clicked.connect(self.generate)
        layout.addWidget(self.optimize_button)
        for label in ("生成线稿（后续版本）", "生成配色图（后续版本）", "自动质检（后续版本）"):
            button = QPushButton(label)
            button.setEnabled(False)
            layout.addWidget(button)
        self.export_button = QPushButton("导出 PNG")
        self.export_button.clicked.connect(self.export_result)
        self.export_button.setEnabled(False)
        layout.addWidget(self.export_button)
        layout.addStretch(1)
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(180)
        layout.addWidget(self.log)
        self.source_view = ImageView()
        self.result_view = ImageView()
        previews = QWidget()
        preview_layout = QHBoxLayout(previews)
        for title, view in (("原图", self.source_view), ("效果图", self.result_view)):
            column = QVBoxLayout()
            column.addWidget(QLabel(title))
            column.addWidget(view, 1)
            preview_layout.addLayout(column, 1)
        splitter = QSplitter()
        splitter.addWidget(controls)
        splitter.addWidget(previews)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)
        self.statusBar().showMessage("请导入 JPG 或 PNG 图片")

    def _target_colors(self) -> int:
        value = self.color_combo.currentText()
        return self.custom_colors.value() if value == "自定义" else int(value)

    def _append_log(self, message: str) -> None:
        self.log.append(message)
        self.statusBar().showMessage(message)

    def open_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "导入原图", "", "图片 (*.jpg *.jpeg *.png)")
        if not path:
            return
        try:
            with Image.open(path) as opened:
                image = ImageOps.exif_transpose(opened).convert("RGB")
                self._source = np.asarray(image, dtype=np.uint8).copy()
                image_size = image.size
            self._result = None
            self.source_view.set_pixmap(array_to_pixmap(self._source))
            self.result_view.set_pixmap(QPixmap())
            self.export_button.setEnabled(False)
            self._append_log(f"已导入：{Path(path).name}（{image_size[0]}×{image_size[1]}）")
        except Exception as exc:
            QMessageBox.critical(self, "导入失败", f"无法读取图片：\n{exc}")

    def generate(self) -> None:
        if self._source is None:
            QMessageBox.information(self, "需要原图", "请先导入 JPG 或 PNG 图片。")
            return
        if self._thread is not None:
            return
        config = PipelineConfig(target_colors=self._target_colors(), min_region_area=20)
        self._thread = QThread(self)
        self._worker = GenerationWorker(self._source, config)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.completed.connect(self._on_completed)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread_finished)
        self.generate_button.setEnabled(False)
        self.optimize_button.setEnabled(False)
        self.progress.setValue(0)
        self._append_log(f"开始生成：{config.target_colors} 色")
        self._thread.start()

    def _on_progress(self, value: int, message: str) -> None:
        self.progress.setValue(value)
        self._append_log(message)

    def _on_completed(self, result: object) -> None:
        if not isinstance(result, PaintByNumbersResult):
            self._on_failed("后台任务返回了未知结果")
            return
        self._result = result
        self.result_view.set_pixmap(array_to_pixmap(result.rendered_rgb))
        self.export_button.setEnabled(True)
        self._append_log(f"完成：{len(result.palette)} 个颜色，{len(result.regions)} 个连通区域")

    def _on_failed(self, details: str) -> None:
        self._append_log("生成失败")
        QMessageBox.critical(self, "生成失败", details)

    def _thread_finished(self) -> None:
        if self._thread is not None:
            self._thread.deleteLater()
        self._thread = None
        self._worker = None
        self.generate_button.setEnabled(True)
        self.optimize_button.setEnabled(True)

    def export_result(self) -> None:
        if self._result is None:
            QMessageBox.information(self, "没有结果", "请先生成效果图。")
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出效果图", "效果图.png", "PNG (*.png)")
        if not path:
            return
        try:
            final_path = export_png(self._result.rendered_rgb, path)
            self._append_log(f"已导出：{final_path}")
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", str(exc))

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._thread is not None and self._thread.isRunning():
            QMessageBox.information(self, "正在处理", "请等待当前生成任务完成后再关闭。")
            event.ignore()
            return
        event.accept()
