from __future__ import annotations

import numpy as np

from digital_paint.core.labels import _local_region_mask, place_labels
from digital_paint.core.performance import recommended_sample_limit
from digital_paint.core.pipeline import build_production_result
from digital_paint.core.regions import build_regions


def test_label_distance_transform_uses_local_bbox() -> None:
    color_id = np.zeros((300, 400), dtype=np.int32)
    color_id[120:140, 210:250] = 1
    rr = build_regions(color_id)
    target = next(r for r in rr.regions if r.color_id == 1)

    local_mask, _, _ = _local_region_mask(rr.region_id, target)
    assert local_mask.shape[0] < 40
    assert local_mask.shape[1] < 60

    labels = place_labels(rr.region_id, rr.regions)
    label = next(item for item in labels if item.region_id == target.region_id)
    assert rr.region_id[int(round(label.y)), int(round(label.x))] == target.region_id


def test_kmeans_sample_limit_is_bounded_for_common_color_counts() -> None:
    image = np.zeros((5000, 5000, 3), dtype=np.uint8)
    assert recommended_sample_limit(image, 12) == 24_000
    assert recommended_sample_limit(image, 24) == 43_200
    assert recommended_sample_limit(image, 50) == 90_000
    assert recommended_sample_limit(image, 256) == 100_000


def test_second_production_run_reuses_quantize_and_merge_cache(tmp_path) -> None:
    image = np.zeros((48, 64, 3), dtype=np.uint8)
    image[:, :32] = (230, 80, 60)
    image[:, 32:] = (40, 90, 210)

    first = build_production_result(
        image,
        2,
        min_region_area=4,
        cache_dir=tmp_path,
    )
    second = build_production_result(
        image,
        2,
        min_region_area=4,
        cache_dir=tmp_path,
    )

    assert "quantize_lab" not in first.cache_hits
    assert "quantize_lab" in second.cache_hits
    assert "merge_structure_aware" in second.cache_hits
    assert np.array_equal(first.color_id, second.color_id)
    assert np.array_equal(first.palette_rgb, second.palette_rgb)
