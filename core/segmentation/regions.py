"""Connected region extraction with stable region/color mappings."""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from core.models import Region

_FOUR_CONNECTED = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=np.uint8)


def build_regions(color_id_map: np.ndarray) -> tuple[np.ndarray, list[Region]]:
    """Assign one region ID to every four-connected component of a color map."""
    colors = np.asarray(color_id_map)
    if colors.ndim != 2 or not np.issubdtype(colors.dtype, np.integer):
        raise ValueError("color_id_map 必须是二维整数数组")
    region_map = np.full(colors.shape, -1, dtype=np.int32)
    regions: list[Region] = []
    next_region_id = 0
    for color_id in sorted(int(value) for value in np.unique(colors)):
        labels, count = ndimage.label(colors == color_id, structure=_FOUR_CONNECTED)
        objects = ndimage.find_objects(labels)
        for component in range(1, count + 1):
            slices = objects[component - 1]
            if slices is None:
                continue
            mask = labels[slices] == component
            region_map_view = region_map[slices]
            region_map_view[mask] = next_region_id
            y_slice, x_slice = slices
            regions.append(
                Region(
                    region_id=next_region_id,
                    color_id=color_id,
                    area=int(mask.sum()),
                    bbox=(x_slice.start, y_slice.start, x_slice.stop, y_slice.stop),
                )
            )
            next_region_id += 1
    if np.any(region_map < 0):
        raise RuntimeError("区域分析后仍有未分配像素")
    return region_map, regions
