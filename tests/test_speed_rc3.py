from __future__ import annotations

import numpy as np

from digital_paint.core.editing import expand_bbox, recompute_dirty
from digital_paint.core.runtime import CancellationToken, Tile, parallel_map_tiles, recommended_workers


def test_expand_bbox_is_clamped() -> None:
    assert expand_bbox((2, 3, 8, 9), (10, 12), padding=5) == (0, 0, 10, 12)


def test_recompute_dirty_returns_full_canvas_label_coordinates() -> None:
    color_id = np.zeros((40, 60), dtype=np.int32)
    color_id[10:30, 20:45] = 1
    result = recompute_dirty(color_id, (12, 22, 28, 43), padding=3)
    y0, x0, y1, x1 = result.bbox
    assert (y0, x0, y1, x1) == (9, 19, 31, 46)
    assert result.local_labels
    for label in result.local_labels:
        assert x0 <= label.x < x1
        assert y0 <= label.y < y1


def test_parallel_map_tiles_preserves_input_order() -> None:
    tiles = [Tile(0, 10, i * 10, i * 10 + 10) for i in range(6)]
    result = parallel_map_tiles(tiles, lambda tile: tile.x0, max_workers=3)
    assert result == [0, 10, 20, 30, 40, 50]


def test_parallel_map_tiles_honours_pre_cancelled_token() -> None:
    token = CancellationToken()
    token.cancel()
    tiles = [Tile(0, 10, 0, 10)]
    try:
        parallel_map_tiles(tiles, lambda tile: tile.shape, cancellation=token, max_workers=1)
    except RuntimeError as exc:
        assert "cancelled" in str(exc)
    else:
        raise AssertionError("expected cancellation")


def test_worker_count_is_conservative() -> None:
    workers = recommended_workers(limit=8)
    assert 1 <= workers <= 8
