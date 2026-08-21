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


def _local_region_mask(
    region_id: np.ndarray,
    region: RegionInfo,
    *,
    padding: int = 1,
) -> tuple[np.ndarray, int, int]:
    """Return a padded local mask and its global origin.

    Distance transforms previously ran over the full canvas once per region. Using
    each region's bounding box reduces the work dramatically on artworks with many
    small/medium regions while preserving the same interior-distance semantics.
    """
    min_row, min_col, max_row, max_col = region.bbox
    h, w = region_id.shape
    y0 = max(0, min_row - padding)
    x0 = max(0, min_col - padding)
    y1 = min(h, max_row + padding)
    x1 = min(w, max_col + padding)
    local = region_id[y0:y1, x0:x1] == region.region_id
    # A zero border guarantees distance-to-background remains correct even when a
    # region touches the image edge.
    local = np.pad(local, 1, mode="constant", constant_values=False)
    return local, y0 - 1, x0 - 1


def place_labels(region_id: np.ndarray, regions: list[RegionInfo]) -> list[LabelPlacement]:
    """Place labels with localized distance transforms and multiple candidates."""
    placements: list[LabelPlacement] = []
    for region in regions:
        local_mask, origin_y, origin_x = _local_region_mask(region_id, region)
        if not np.any(local_mask):
            continue

        distance = distance_transform_edt(local_mask)
        ys, xs = np.nonzero(local_mask)
        cx = float(xs.mean())
        cy = float(ys.mean())
        best: tuple[float, int, int, float] | None = None
        diagonal = max(float(np.hypot(local_mask.shape[1], local_mask.shape[0])), 1.0)

        for y, x, clearance in _candidate_points(distance):
            if not local_mask[y, x]:
                continue
            centroid_penalty = float(np.hypot(float(x) - cx, float(y) - cy)) / diagonal
            score = clearance - 0.35 * centroid_penalty
            if best is None or score > best[0]:
                best = (score, y, x, clearance)

        if best is None:
            continue

        score, local_y, local_x, clearance = best
        global_y = float(local_y + origin_y)
        global_x = float(local_x + origin_x)
        pt = choose_font_pt(clearance)
        fits = clearance * 2.0 >= 5.0 * 1.333 * 1.35
        placements.append(
            LabelPlacement(
                region_id=region.region_id,
                color_id=region.color_id,
                x=global_x,
                y=global_y,
                font_pt=pt,
                fits=fits,
                rotation_deg=_principal_rotation(local_mask),
                clearance_px=clearance,
                score=float(score),
            )
        )
    return placements
