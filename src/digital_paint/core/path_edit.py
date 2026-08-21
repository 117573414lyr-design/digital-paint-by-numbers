from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from digital_paint.core.geometry import count_self_intersections


@dataclass(slots=True)
class PathOverride:
    region_id: int
    points: np.ndarray
    closed: bool = True

    def validated(self) -> "PathOverride":
        pts = np.asarray(self.points, dtype=np.float64)
        if pts.ndim != 2 or pts.shape[1] != 2 or len(pts) < 3:
            raise ValueError("path override must be an Nx2 array with at least three points")
        if self.closed and not np.allclose(pts[0], pts[-1]):
            pts = np.vstack([pts, pts[0]])
        if count_self_intersections(pts) > 0:
            raise ValueError("manual path override contains self intersections")
        return PathOverride(region_id=int(self.region_id), points=pts, closed=self.closed)


def move_anchor(override: PathOverride, index: int, x: float, y: float) -> PathOverride:
    """Move one editable anchor while preserving a valid non-self-crossing path."""
    current = override.validated()
    pts = current.points.copy()
    if not 0 <= index < len(pts):
        raise IndexError(index)
    pts[index] = (float(x), float(y))
    if current.closed:
        if index == 0:
            pts[-1] = pts[0]
        elif index == len(pts) - 1:
            pts[0] = pts[-1]
    return PathOverride(region_id=current.region_id, points=pts, closed=current.closed).validated()
