import numpy as np
import pytest

from digital_paint.core.performance import PerformanceReport, StageTiming
from digital_paint.core.performance_gate import benchmark_targets, evaluate_performance_gate
from digital_paint.core.runtime import (
    CancellationToken,
    PipelineCancelled,
    StageCache,
    cached_array_stage,
    choose_tile_size,
    iter_tiles,
)


def test_cancellation_token_raises():
    token = CancellationToken()
    token.cancel()
    with pytest.raises(PipelineCancelled):
        token.raise_if_cancelled()


def test_large_image_requests_tiled_mode():
    plan = choose_tile_size(8000, 6000, 512)
    assert plan.use_tiles
    assert 256 <= plan.tile_size <= 2048


def test_tiles_cover_image_bounds():
    tiles = iter_tiles((1000, 1200), 400, overlap=16)
    assert tiles
    assert min(t.y0 for t in tiles) == 0
    assert min(t.x0 for t in tiles) == 0
    assert max(t.y1 for t in tiles) == 1000
    assert max(t.x1 for t in tiles) == 1200


def test_stage_cache_reuses_array(tmp_path):
    cache = StageCache(tmp_path)
    key = StageCache.key("demo", {"a": 1})
    calls = {"n": 0}

    def build():
        calls["n"] += 1
        return np.arange(6, dtype=np.int32)

    a, hit_a = cached_array_stage(cache, key, build)
    b, hit_b = cached_array_stage(cache, key, build)
    assert not hit_a and hit_b
    assert calls["n"] == 1
    assert np.array_equal(a, b)


def test_performance_gate_and_targets():
    report = PerformanceReport(width=4000, height=3000, megapixels=12.0)
    report.stages.append(StageTiming("all", 24.0))
    plan = choose_tile_size(4000, 3000, 2048)
    gate = evaluate_performance_gate(report, plan, max_seconds_per_mp=3.0)
    assert gate.status == "PASS"
    assert benchmark_targets() == {"12MP": 12_000_000, "24MP": 24_000_000, "48MP": 48_000_000}
