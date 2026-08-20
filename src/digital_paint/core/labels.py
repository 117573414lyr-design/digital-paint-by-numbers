from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import distance_transform_edt

from digital_paint.core.regions import RegionInfo


@dataclass(slots=True)
class LabelPlacement:
    region_id: int
    color_id: int
    x: float
    y: float
    font_pt: float
    fits: bool
    rotation_deg: float = 0.0
    clearance_px: float = 0.0
    score: float = 0.0


def choose_font_pt(clearance_px: float, *, px_per_pt: float = 1.333) -> float:
    """Choose the project's 4.2/6/8 pt label size from local clearance."""
    diameter_px = clearance_px * 2.0
    for pt in (8.0, 6.0, 4.2):
        if diameter_px >= pt * px_per_pt * 1.35:
            return pt
    return 4.2


def _principal_rotation(mask: np.ndarray) -> float:
    """Return 0 or 90 degrees for elongated regions using second moments."""
    ys, xs = np.nonzero(mask)
    if len(xs) < 3:
        return 0.0
    x = xs.astype(float) - float(xs.mean())
    y = ys.astype(float) - float(ys.mean())
    cov = np.array([[np.mean(x * x), np.mean(x * y)], [np.mean(x * y), np.mean(y * y)]])
    vals, vecs = np.linalg.eigh(cov)
    major = vecs[:, int(np.argmax(vals))]
    angle = float(np.degrees(np.arctan2(major[1], major[0])))
    # Keep production labels easy to read: only horizontal or vertical.
    normalized = ((angle + 180.0) % 180.0)
    return 90.0 if 45.0 <= normalized < 135.0 else 0.0


def _candidate_points(distance: np.ndarray, limit: int = 8) -> list[tuple[int, int, float]]:
    """Return the strongest interior candidates without exhaustive sorting."""
    flat = distance.ravel()
    if flat.size == 0:
        return []
    k = min(limit, flat.size)
    idx = np.argpartition(flat, -k)[-k:]
    ordered = idx[np.argsort(flat[idx])[::-1]]
    return [(*np.unravel_index(int(i), distance.shape), float(flat[int(i)])) for i in ordered]


def place_labels(region_id: np.ndarray, regions: list[RegionInfo]) -> list[LabelPlacement]:
    """Place labels using multiple deep-interior candidates and elongated-region orientation.

    Candidate scoring rewards boundary clearance and modestly rewards closeness to the
    region centroid, improving visual balance without allowing labels to cross borders.
    """
    placements: list[LabelPlacement] = []
    for region in regions:
        mask = region_id == region.region_id
        if not np.any(mask):
            continue
        distance = distance_transform_edt(mask)
        ys, xs = np.nonzero(mask)
        cx = float(xs.mean())
        cy = float(ys.mean())
        best: tuple[float, int, int, float] | None = None
        diagonal = max(float(np.hypot(mask.shape[1], mask.shape[0])), 1.0)
        for y, x, clearance in _candidate_points(distance):
            centroid_penalty = float(np.hypot(float(x) - cx, float(y) - cy)) / diagonal
            score = clearance - 0.35 * centroid_penalty
            if best is None or score > best[0]:
                best = (score, y, x, clearance)
        if best is None:
            continue
        score, y, x, clearance = best
        pt = choose_font_pt(clearance)
        fits = clearance * 2.0 >= 5.0 * 1.333 * 1.35
        placements.append(
            LabelPlacement(
                region_id=region.region_id,
                color_id=region.color_id,
                x=float(x),
                y=float(y),
                font_pt=pt,
                fits=fits,
                rotation_deg=_principal_rotation(mask),
                clearance_px=clearance,
                score=float(score),
            )
        )
    return placements
