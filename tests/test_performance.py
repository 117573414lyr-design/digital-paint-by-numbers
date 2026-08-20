import numpy as np

from digital_paint.core.performance import (
    StageProfiler,
    estimated_working_set_mb,
    recommended_sample_limit,
    should_downscale_for_interactive_preview,
)


def test_sample_limit_is_bounded_for_large_images():
    image = np.zeros((5000, 7000, 3), dtype=np.uint8)
    assert recommended_sample_limit(image, 24) <= 180_000
    assert recommended_sample_limit(image, 50) <= 180_000


def test_sample_limit_never_exceeds_pixel_count():
    image = np.zeros((100, 120, 3), dtype=np.uint8)
    assert recommended_sample_limit(image, 24) == 12_000


def test_preview_policy_detects_large_images():
    small = np.zeros((1000, 1000, 3), dtype=np.uint8)
    large = np.zeros((4000, 4000, 3), dtype=np.uint8)
    assert not should_downscale_for_interactive_preview(small)
    assert should_downscale_for_interactive_preview(large)


def test_working_set_estimate_is_positive_and_scales():
    a = np.zeros((100, 100, 3), dtype=np.uint8)
    b = np.zeros((200, 200, 3), dtype=np.uint8)
    assert estimated_working_set_mb(a) > 0
    assert estimated_working_set_mb(b) > estimated_working_set_mb(a)


def test_stage_profiler_records_stage():
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    profiler = StageProfiler(image)
    value = profiler.run("sample", lambda x: x + 1, 3)
    assert value == 4
    assert len(profiler.report.stages) == 1
    assert profiler.report.stages[0].name == "sample"
    assert profiler.report.total_seconds >= 0
