import numpy as np

from digital_paint.core.export_quality import (
    crossing_segment_count,
    duplicate_segment_count,
    vector_quality_from_region_map,
)
from digital_paint.core.labels import place_labels
from digital_paint.core.qc import run_qc
from digital_paint.core.regions import build_regions


def test_duplicate_segment_detection_is_direction_independent():
    segments = [(0.0, 0.0, 1.0, 0.0), (1.0, 0.0, 0.0, 0.0)]
    assert duplicate_segment_count(segments) == 1


def test_crossing_segment_detection_ignores_shared_endpoints():
    assert crossing_segment_count([(0, 0, 2, 2), (0, 2, 2, 0)]) == 1
    assert crossing_segment_count([(0, 0, 1, 0), (1, 0, 1, 1)]) == 0


def test_region_map_vector_quality_has_no_duplicate_shared_edges():
    region_id = np.array([[0, 0, 1], [0, 0, 1]], dtype=np.int32)
    report = vector_quality_from_region_map(region_id, [4.2, 6.0])
    assert report.duplicate_segments == 0
    assert report.crossing_segments == 0
    assert report.line_width_ok
    assert report.cmyk_ok
    assert report.label_sizes_ok


def test_qc_contains_located_checks_and_label_inside_region():
    color_id = np.array(
        [[0, 0, 1, 1], [0, 0, 1, 1], [2, 2, 2, 2]],
        dtype=np.int32,
    )
    regions = build_regions(color_id)
    placements = place_labels(regions.region_id, regions.regions)
    report = run_qc(regions, placements, min_area=1, palette_size=3)
    by_code = {item.code: item for item in report.items}
    assert by_code["LABEL_INSIDE_REGION"].status == "PASS"
    assert by_code["DUPLICATE_BOUNDARIES"].status == "PASS"
    assert by_code["CROSSING_BOUNDARIES"].status == "PASS"
    assert by_code["PRODUCTION_SPEC"].status == "PASS"
    assert by_code["TINY_REGIONS"].locations is not None
