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


def choose_font_pt(clearance_px: float, *, px_per_pt: float = 1.333) -> float:
    """Choose the project's 4.2/6/8 pt label size from local clearance."""
    diameter_px = clearance_px * 2.0
    for pt in (8.0, 6.0, 4.2):
        if diameter_px >= pt * px_per_pt * 1.35:
            return pt
    return 4.2


def place_labels(region_id: np.ndarray, regions: list[RegionInfo]) -> list[LabelPlacement]:
    """Place each number at the deepest interior pixel of its region."""
    placements: list[LabelPlacement] = []
    for region in regions:
        mask = region_id == region.region_id
        if not np.any(mask):
            continue
        distance = distance_transform_edt(mask)
        flat_index = int(np.argmax(distance))
        y, x = np.unravel_index(flat_index, distance.shape)
        clearance = float(distance[y, x])
        pt = choose_font_pt(clearance)
        # Approximate 5 pt production capacity: tiny regions stay explicit QC candidates.
        fits = clearance * 2.0 >= 5.0 * 1.333 * 1.35
        placements.append(
            LabelPlacement(
                region_id=region.region_id,
                color_id=region.color_id,
                x=float(x),
                y=float(y),
                font_pt=pt,
                fits=fits,
            )
        )
    return placements
