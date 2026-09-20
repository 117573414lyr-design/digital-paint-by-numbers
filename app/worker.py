"""Background processing worker used by the UI."""

from __future__ import annotations

import traceback

import numpy as np
from PySide6.QtCore import QObject, Signal, Slot

from core.pipeline import PaintByNumbersPipeline, PipelineConfig


class GenerationWorker(QObject):
    progress = Signal(int, str)
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, image: np.ndarray, config: PipelineConfig) -> None:
        super().__init__()
        self._image = image.copy()
        self._config = config

    @Slot()
    def run(self) -> None:
        try:
            pipeline = PaintByNumbersPipeline(self._config)
            result = pipeline.run(self._image, progress=self.progress.emit)
            self.completed.emit(result)
        except Exception:
            self.failed.emit(traceback.format_exc())
        finally:
            self.finished.emit()
