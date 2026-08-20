from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from digital_paint.core.geometry import count_self_intersections, polygon_area


@dataclass(slots=True)
class SmoothResult:
    points: np.ndarray
    accepted: bool
    area_error_ratio: float
    self_intersections: int


def chaikin_closed(points: np.ndarray, iterations: int = 1) -> np.ndarray:
    """Smooth a closed polygon using Chaikin corner cutting.

    This is used as a conservative V10 curve-smoothing layer before later
    Bezier fitting. The function preserves closure and is deterministic.
    """
    pts = np.asarray(points, dtype=np.float64)
    if len(pts) < 4:
        return pts.copy()
    base = pts[:-1] if np.allclose(pts[0], pts[-1]) else pts
    if len(base) < 3:
        return pts.copy()
    current = base
    for _ in range(max(0, iterations)):
        out: list[np.ndarray] = []
        for i, p in enumerate(current):
            q = current[(i + 1) % len(current)]
            out.append(0.75 * p + 0.25 * q)
            out.append(0.25 * p + 0.75 * q)
        current = np.asarray(out, dtype=np.float64)
    return np.vstack([current, current[0]])


def smooth_closed_boundary(
    points: np.ndarray,
    *,
    iterations: int = 1,
    max_area_error: float = 0.025,
) -> SmoothResult:
    """Apply smoothing only when topology and area remain production-safe."""
    original = np.asarray(points, dtype=np.float64)
    candidate = chaikin_closed(original, iterations=iterations)
    before = polygon_area(original[:-1] if np.allclose(original[0], original[-1]) else original)
    after = polygon_area(candidate[:-1] if np.allclose(candidate[0], candidate[-1]) else candidate)
    area_error = abs(after - before) / max(before, 1.0)
    intersections = count_self_intersections(candidate)
    accepted = intersections == 0 and area_error <= max_area_error
    return SmoothResult(
        points=candidate if accepted else original.copy(),
        accepted=accepted,
        area_error_ratio=area_error,
        self_intersections=intersections,
    )


def cubic_bezier_controls(points: np.ndarray, tension: float = 0.25) -> list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    """Create cubic Bezier segments from a closed polyline.

    Adjacent segments share the same endpoint objects conceptually, making the
    result suitable for a single shared-boundary representation. This is a
    Catmull-Rom-inspired control-point construction, not independent per-side fitting.
    """
    pts = np.asarray(points, dtype=np.float64)
    base = pts[:-1] if len(pts) > 1 and np.allclose(pts[0], pts[-1]) else pts
    if len(base) < 3:
        return []
    segments: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = []
    n = len(base)
    for i in range(n):
        p0 = base[(i - 1) % n]
        p1 = base[i]
        p2 = base[(i + 1) % n]
        p3 = base[(i + 2) % n]
        c1 = p1 + (p2 - p0) * (tension / 3.0)
        c2 = p2 - (p3 - p1) * (tension / 3.0)
        segments.append((p1.copy(), c1, c2, p2.copy()))
    return segments
