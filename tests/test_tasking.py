from pathlib import Path

import numpy as np
import pytest

from digital_paint.core.tasking import (
    CancellationToken,
    CancelledError,
    StageCache,
    choose_tile_size,
    estimate_working_set_bytes,
)


def test_cancellation_token_raises():
    token = CancellationToken()
    token.cancel()
    with pytest.raises(CancelledError):
        token.raise_if_cancelled()


def test_stage_cache_reuses_array_result(tmp_path: Path):
    cache = StageCache(tmp_path / "cache")
    source = np.arange(9, dtype=np.int32).reshape(3, 3)
    calls = {"count": 0}

    def producer():
        calls["count"] += 1
        return {"result": source * 2}

    first = cache.run_array_stage("double", (source, 2), producer)
    second = cache.run_array_stage("double", (source, 2), producer)
    assert np.array_equal(first["result"], second["result"])
    assert calls["count"] == 1
    assert cache.records[-1].cache_hit is True


def test_memory_and_tile_planning_are_bounded():
    assert estimate_working_set_bytes(4000, 3000) > 0
    tile = choose_tile_size(8000, 6000, memory_budget_mb=512)
    assert 256 <= tile <= 4096
