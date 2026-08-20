import numpy as np

from digital_paint.core.labels import place_labels
from digital_paint.core.regions import build_regions


def test_vertical_region_prefers_vertical_label():
    color_id = np.zeros((20, 10), dtype=np.int32)
    result = build_regions(color_id)
    labels = place_labels(result.region_id, result.regions)
    assert len(labels) == 1
    assert labels[0].rotation_deg == 90.0
    assert labels[0].clearance_px > 0


def test_label_candidate_stays_inside_region():
    color_id = np.zeros((12, 12), dtype=np.int32)
    color_id[:, 6:] = 1
    result = build_regions(color_id)
    labels = place_labels(result.region_id, result.regions)
    assert len(labels) == 2
    for item in labels:
        x = int(round(item.x))
        y = int(round(item.y))
        assert result.region_id[y, x] == item.region_id
