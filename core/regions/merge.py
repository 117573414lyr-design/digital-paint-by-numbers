"""Conservative small-component merging for the first V0.2 increment."""

from __future__ import annotations

from collections import Counter

import numpy as np

from core.segmentation.regions import build_regions


def merge_small_regions(color_id_map: np.ndarray, min_area: int) -> np.ndarray:
    """Merge tiny connected regions into the neighbor sharing the longest boundary."""
    if min_area <= 1:
        return np.asarray(color_id_map, dtype=np.int32).copy()
    output = np.asarray(color_id_map, dtype=np.int32).copy()
    region_map, regions = build_regions(output)
    height, width = output.shape
    for region in sorted(regions, key=lambda item: item.area):
        if region.area >= min_area:
            continue
        x0, y0, x1, y1 = region.bbox
        local_region_map = region_map[y0:y1, x0:x1]
        mask = local_region_map == region.region_id
        local_ys, local_xs = np.nonzero(mask)
        ys = local_ys + y0
        xs = local_xs + x0
        neighboring_colors: Counter[int] = Counter()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny = ys + dy
            nx = xs + dx
            valid = (ny >= 0) & (ny < height) & (nx >= 0) & (nx < width)
            candidates = output[ny[valid], nx[valid]]
            neighboring_colors.update(
                int(value) for value in candidates if int(value) != region.color_id
            )
        if neighboring_colors:
            replacement = min(neighboring_colors, key=lambda v: (-neighboring_colors[v], v))
            output[ys, xs] = replacement
    return output
