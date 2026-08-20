from __future__ import annotations

import numpy as np


def shared_boundary_segments(region_id: np.ndarray) -> list[tuple[float, float, float, float]]:
    """Return each internal/outer pixel-grid boundary exactly once.

    This is the topology-safe source for linework. Later curve fitting may smooth
    these segments, but duplicate shared edges must never be reintroduced.
    """
    if region_id.ndim != 2:
        raise ValueError("region_id must be a 2-D array")
    h, w = region_id.shape
    segments: list[tuple[float, float, float, float]] = []

    # Outer frame.
    segments.extend([
        (0.0, 0.0, float(w), 0.0),
        (float(w), 0.0, float(w), float(h)),
        (float(w), float(h), 0.0, float(h)),
        (0.0, float(h), 0.0, 0.0),
    ])

    # Vertical boundaries between horizontally adjacent pixels.
    for x in range(1, w):
        changed = region_id[:, x - 1] != region_id[:, x]
        ys = np.flatnonzero(changed)
        for y in ys:
            segments.append((float(x), float(y), float(x), float(y + 1)))

    # Horizontal boundaries between vertically adjacent pixels.
    for y in range(1, h):
        changed = region_id[y - 1, :] != region_id[y, :]
        xs = np.flatnonzero(changed)
        for x in xs:
            segments.append((float(x), float(y), float(x + 1), float(y)))
    return segments


def merge_collinear_segments(
    segments: list[tuple[float, float, float, float]],
) -> list[tuple[float, float, float, float]]:
    """Merge contiguous horizontal/vertical unit segments to reduce vector nodes."""
    horizontal: dict[float, list[tuple[float, float]]] = {}
    vertical: dict[float, list[tuple[float, float]]] = {}
    other: list[tuple[float, float, float, float]] = []
    for x1, y1, x2, y2 in segments:
        if y1 == y2:
            a, b = sorted((x1, x2))
            horizontal.setdefault(y1, []).append((a, b))
        elif x1 == x2:
            a, b = sorted((y1, y2))
            vertical.setdefault(x1, []).append((a, b))
        else:
            other.append((x1, y1, x2, y2))

    merged = list(other)
    for y, spans in horizontal.items():
        for start, end in _merge_spans(spans):
            merged.append((start, y, end, y))
    for x, spans in vertical.items():
        for start, end in _merge_spans(spans):
            merged.append((x, start, x, end))
    return merged


def _merge_spans(spans: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if not spans:
        return []
    ordered = sorted(spans)
    out: list[tuple[float, float]] = []
    start, end = ordered[0]
    for a, b in ordered[1:]:
        if a <= end:
            end = max(end, b)
        else:
            out.append((start, end))
            start, end = a, b
    out.append((start, end))
    return out
