import numpy as np
import pytest

from digital_paint.core.path_edit import PathOverride, move_anchor


def test_path_override_closes_open_loop():
    override = PathOverride(3, np.array([[0, 0], [4, 0], [4, 4], [0, 4]], dtype=float)).validated()
    assert np.allclose(override.points[0], override.points[-1])


def test_move_anchor_preserves_closure():
    override = PathOverride(1, np.array([[0, 0], [4, 0], [4, 4], [0, 4]], dtype=float)).validated()
    moved = move_anchor(override, 0, -1, 0)
    assert np.allclose(moved.points[0], moved.points[-1])


def test_self_intersection_is_rejected():
    bow = np.array([[0, 0], [4, 4], [0, 4], [4, 0], [0, 0]], dtype=float)
    with pytest.raises(ValueError):
        PathOverride(1, bow).validated()
