import numpy as np
import pytest

from digital_paint.core.editing import (
    EditSession,
    EditState,
    merge_regions,
    move_label,
    recolor_region,
    split_region_by_mask,
)
from digital_paint.core.labels import place_labels
from digital_paint.core.regions import build_regions


def _state() -> EditState:
    color_id = np.array([
        [0, 0, 1, 1],
        [0, 0, 1, 1],
        [2, 2, 1, 1],
        [2, 2, 1, 1],
    ], dtype=np.int32)
    regions = build_regions(color_id)
    labels = place_labels(regions.region_id, regions.regions)
    return EditState(color_id=color_id, labels=labels)


def test_recolor_and_undo_redo():
    session = EditSession(_state())
    original = session.state.color_id.copy()
    session.apply("recolor", lambda s: recolor_region(s, 0, 2))
    assert not np.array_equal(session.state.color_id, original)
    assert session.state.dirty_bbox is not None
    assert session.can_undo
    session.undo()
    assert np.array_equal(session.state.color_id, original)
    assert session.can_redo
    session.redo()
    assert not np.array_equal(session.state.color_id, original)


def test_merge_regions_recolors_complete_regions():
    state = _state()
    result = merge_regions(state, [0, 2], target_color_id=1)
    assert np.all(result.color_id[np.isin(build_regions(_state().color_id).region_id, [0, 2])] == 1)


def test_split_region_requires_proper_subset():
    state = _state()
    mask = np.zeros_like(state.color_id, dtype=bool)
    mask[0, 0] = True
    result = split_region_by_mask(state, 0, mask, 2)
    assert result.color_id[0, 0] == 2

    state = _state()
    whole = build_regions(state.color_id).region_id == 0
    with pytest.raises(ValueError):
        split_region_by_mask(state, 0, whole, 2)


def test_move_label_must_stay_inside_region():
    state = _state()
    regions = build_regions(state.color_id)
    label = next(item for item in state.labels if item.region_id == 0)
    result = move_label(state, 0, label.x, label.y)
    assert result.dirty_bbox is not None

    with pytest.raises(ValueError):
        move_label(_state(), 0, 3, 3)
