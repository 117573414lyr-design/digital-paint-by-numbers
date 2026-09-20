import numpy as np

from core.regions.merge import merge_small_regions
from core.segmentation.regions import build_regions


def test_regions_are_connected_and_fully_assigned() -> None:
    colors = np.array([[0, 0, 1], [0, 1, 1], [2, 2, 1]], dtype=np.int32)
    region_map, regions = build_regions(colors)
    assert len(regions) == 3
    assert np.all(region_map >= 0)
    assert sum(region.area for region in regions) == colors.size


def test_small_region_merges_to_longest_boundary_neighbor() -> None:
    colors = np.zeros((5, 5), dtype=np.int32)
    colors[2, 2] = 2
    colors[:, 4] = 1
    merged = merge_small_regions(colors, min_area=2)
    assert merged[2, 2] == 0
    assert np.all(merged[:, 4] == 1)
