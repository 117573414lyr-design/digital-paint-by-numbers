import numpy as np

from digital_paint.core.regions import build_regions
from digital_paint.core.segmentation_quality import (
    analyze_region_structure,
    edge_strength_map,
    merge_small_regions_structure_aware,
)


def test_edge_strength_map_is_normalized():
    image = np.zeros((20, 20, 3), dtype=np.uint8)
    image[:, 10:] = 255
    edges = edge_strength_map(image)
    assert edges.shape == image.shape[:2]
    assert float(edges.min()) >= 0.0
    assert float(edges.max()) <= 1.0
    assert float(edges[:, 9:11].mean()) > float(edges[:, :4].mean())


def test_structure_analysis_marks_edge_rich_region():
    region_id = np.zeros((10, 10), dtype=np.int32)
    region_id[:, 5:] = 1
    regions = build_regions(region_id).regions
    edge = np.zeros((10, 10), dtype=np.float32)
    edge[:, 4:6] = 1.0
    result = analyze_region_structure(region_id, regions, edge, protect_mean_gradient=0.05)
    assert result[0].protected
    assert result[1].protected


def test_structure_aware_merge_removes_impossible_single_pixel_fragment():
    color_id = np.zeros((12, 12), dtype=np.int32)
    color_id[6, 6] = 1
    palette = np.asarray([[100, 100, 100], [110, 110, 110]], dtype=np.uint8)
    image = np.full((12, 12, 3), 100, dtype=np.uint8)
    result = merge_small_regions_structure_aware(
        color_id,
        palette,
        image,
        min_area=10,
        hard_min_area=2,
    )
    assert int(result[6, 6]) == 0


def test_structure_aware_merge_can_preserve_edge_rich_small_region():
    color_id = np.zeros((20, 20), dtype=np.int32)
    color_id[8:12, 8:12] = 1
    palette = np.asarray([[120, 120, 120], [10, 10, 10]], dtype=np.uint8)
    image = np.full((20, 20, 3), 120, dtype=np.uint8)
    image[8:12, 8:12] = 10
    result = merge_small_regions_structure_aware(
        color_id,
        palette,
        image,
        min_area=30,
        hard_min_area=4,
    )
    assert np.any(result[8:12, 8:12] == 1)
