from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np


@dataclass(slots=True)
class GeometryMetrics:
    points_before: int
    points_after: int
    area_before: float
    area_after: float
    area_error_ratio: float
    self_intersections: int
    sharp_corners: int


def polygon_area(points: np.ndarray) -> float:
    """Return absolute polygon area using the shoelace formula."""
    if len(points) < 3:
        return 0.0
    x = points[:, 0]
    y = points[:, 1]
    return float(abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))) * 0.5)


def _distance_to_segment(point: np.ndarray, start: np.ndarray, end: np.ndarray) -> float:
    delta = end - start
    denom = float(np.dot(delta, delta))
    if denom == 0.0:
        return float(np.linalg.norm(point - start))
    t = float(np.clip(np.dot(point - start, delta) / denom, 0.0, 1.0))
    projection = start + t * delta
    return float(np.linalg.norm(point - projection))


def douglas_peucker(points: np.ndarray, epsilon: float) -> np.ndarray:
    """Simplify an open polyline while preserving endpoints."""
    pts = np.asarray(points, dtype=np.float64)
    if len(pts) <= 2 or epsilon <= 0:
        return pts.copy()
    start, end = pts[0], pts[-1]
    distances = np.array([_distance_to_segment(p, start, end) for p in pts[1:-1]])
    if distances.size == 0:
        return pts.copy()
    idx = int(np.argmax(distances))
    max_distance = float(distances[idx])
    if max_distance <= epsilon:
        return np.vstack([start, end])
    split = idx + 1
    left = douglas_peucker(pts[: split + 1], epsilon)
    right = douglas_peucker(pts[split:], epsilon)
    return np.vstack([left[:-1], right])


def corner_angle(prev: np.ndarray, point: np.ndarray, nxt: np.ndarray) -> float:
    a = prev - point
    b = nxt - point
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 180.0
    cosine = float(np.clip(np.dot(a, b) / (na * nb), -1.0, 1.0))
    return math.degrees(math.acos(cosine))


def simplify_closed_boundary(
    points: np.ndarray,
    *,
    epsilon: float = 0.8,
    protect_angle_deg: float = 55.0,
    max_area_error: float = 0.02,
) -> np.ndarray:
    """Simplify a closed boundary with curvature and area protection.

    Sharp corners are forced back into the simplified path. If the simplified
    polygon changes area beyond ``max_area_error`` the original path is kept.
    """
    pts = np.asarray(points, dtype=np.float64)
    if len(pts) < 4:
        return pts.copy()
    closed = np.allclose(pts[0], pts[-1])
    base = pts[:-1] if closed else pts
    if len(base) < 3:
        return pts.copy()

    open_loop = np.vstack([base, base[0]])
    simplified = douglas_peucker(open_loop, epsilon)
    protected: list[np.ndarray] = []
    for i, point in enumerate(base):
        angle = corner_angle(base[i - 1], point, base[(i + 1) % len(base)])
        if angle <= protect_angle_deg:
            protected.append(point)

    candidates = simplified[:-1] if np.allclose(simplified[0], simplified[-1]) else simplified
    if protected:
        combined = np.vstack([candidates, np.asarray(protected)])
        center = combined.mean(axis=0)
        order = np.argsort(np.arctan2(combined[:, 1] - center[1], combined[:, 0] - center[0]))
        candidates = combined[order]

    before = polygon_area(base)
    after = polygon_area(candidates)
    error = abs(after - before) / max(before, 1.0)
    if error > max_area_error or len(candidates) < 3:
        result = base
    else:
        result = candidates
    return np.vstack([result, result[0]])


def _orientation(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    return float(np.cross(b - a, c - a))


def _segments_intersect(a: np.ndarray, b: np.ndarray, c: np.ndarray, d: np.ndarray) -> bool:
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)
    return (o1 * o2 < 0) and (o3 * o4 < 0)


def count_self_intersections(points: np.ndarray) -> int:
    pts = np.asarray(points, dtype=np.float64)
    if len(pts) < 4:
        return 0
    count = 0
    segments = list(zip(pts[:-1], pts[1:]))
    for i, (a, b) in enumerate(segments):
        for j in range(i + 2, len(segments)):
            if i == 0 and j == len(segments) - 1:
                continue
            c, d = segments[j]
            if _segments_intersect(a, b, c, d):
                count += 1
    return count


def geometry_metrics(before: np.ndarray, after: np.ndarray, sharp_angle: float = 35.0) -> GeometryMetrics:
    before_area = polygon_area(before[:-1] if np.allclose(before[0], before[-1]) else before)
    after_area = polygon_area(after[:-1] if np.allclose(after[0], after[-1]) else after)
    base = after[:-1] if np.allclose(after[0], after[-1]) else after
    sharp = sum(
        corner_angle(base[i - 1], base[i], base[(i + 1) % len(base)]) <= sharp_angle
        for i in range(len(base))
    ) if len(base) >= 3 else 0
    return GeometryMetrics(
        points_before=len(before),
        points_after=len(after),
        area_before=before_area,
        area_after=after_area,
        area_error_ratio=abs(after_area - before_area) / max(before_area, 1.0),
        self_intersections=count_self_intersections(after),
        sharp_corners=int(sharp),
    )
