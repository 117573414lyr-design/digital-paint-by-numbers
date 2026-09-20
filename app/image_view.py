"""Zoomable and pannable image preview."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QWheelEvent
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView


class ImageView(QGraphicsView):
    """QGraphicsView configured for smooth image zoom and hand dragging."""

    def __init__(self) -> None:
        super().__init__()
        self._scene = QGraphicsScene(self)
        self._item = QGraphicsPixmapItem()
        self._scene.addItem(self._item)
        self.setScene(self._scene)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(Qt.GlobalColor.darkGray)

    def set_pixmap(self, pixmap: QPixmap) -> None:
        self._item.setPixmap(pixmap)
        self._scene.setSceneRect(self._item.boundingRect())
        if not pixmap.isNull():
            self.fit_image()

    def fit_image(self) -> None:
        if not self._item.pixmap().isNull():
            self.resetTransform()
            self.fitInView(self._item, Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if self._item.pixmap().isNull():
            return
        factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
        current = self.transform().m11()
        if 0.03 <= current * factor <= 50:
            self.scale(factor, factor)
