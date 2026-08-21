from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable

import numpy as np

from digital_paint.core.labels import LabelPlacement
from digital_paint.core.regions import build_regions


@dataclass(slots=True)
class EditState:
    color_id: np.ndarray
    labels: list[LabelPlacement]
    revision: int = 0
    dirty_bbox: tuple[int, int, int, int] | None = None

    def clone(self) -> "EditState":
        return EditState(
            color_id=self.color_id.copy(),
            labels=[replace(item) for item in self.labels],
            revision=self.revision,
            dirty_bbox=self.dirty_bbox,
        )


@dataclass(slots=True)
class EditRecord:
    name: str
    before: EditState
    after: EditState


class EditSession:
    """Deterministic edit session with undo/redo and dirty-region tracking."""

    def __init__(self, state: EditState) -> None:
        self.state = state
        self._undo: list[EditRecord] = []
        self._redo: list[EditRecord] = []

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def apply(self, name: str, operation: Callable[[EditState], EditState]) -> EditState:
        before = self.state.clone()
        after = operation(before.clone())
        after.revision = self.state.revision + 1
        self._undo.append(EditRecord(name=name, before=self.state.clone(), after=after.clone()))
        self._redo.clear()
        self.state = after
        return self.state

    def undo(self) -> EditState:
        if not self._undo:
            return self.state
        record = self._undo.pop()
        self._redo.append(record)
        self.state = record.before.clone()
        return self.state

    def redo(self) -> EditState:
        if not self._redo:
            return self.state
        record = self._redo.pop()
        self._undo.append(record)
        self.state = record.after.clone()
        return self.state


def _bbox_from_mask(mask: np.ndarray, padding: int = 2) -> tuple[int, int, int, int] | None:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    h, w = mask.shape
    return (
        max(0, int(ys.min()) - padding),
        max(0, int(xs.min()) - padding),
        min(h, int(ys.max()) + 1 + padding),
        min(w, int(xs.max()) + 1 + padding),
    )


def recolor_region(state: EditState, region_id: int, new_color_id: int) -> EditState:
    regions = build_regions(state.color_id)
    mask = regions.region_id == int(region_id)
    if not np.any(mask):
        raise ValueError(f"unknown region_id: {region_id}")
    state.color_id[mask] = int(new_color_id)
    state.dirty_bbox = _bbox_from_mask(mask)
    return state


def merge_regions(state: EditState, region_ids: list[int], target_color_id: int | None = None) -> EditState:
    if len(region_ids) < 2:
        raise ValueError("at least two region IDs are required")
    regions = build_regions(state.color_id)
    selected = [r for r in regions.regions if r.region_id in set(region_ids)]
    if len(selected) != len(set(region_ids)):
        raise ValueError("one or more region IDs are invalid")
    if target_color_id is None:
        selected.sort(key=lambda r: r.area, reverse=True)
        target_color_id = selected[0].color_id
    mask = np.isin(regions.region_id, np.asarray(region_ids, dtype=np.int32))
    state.color_id[mask] = int(target_color_id)
    state.dirty_bbox = _bbox_from_mask(mask)
    return state


def split_region_by_mask(
    state: EditState,
    region_id: int,
    split_mask: np.ndarray,
    new_color_id: int,
) -> EditState:
    if split_mask.shape != state.color_id.shape:
        raise ValueError("split_mask shape must match color_id")
    regions = build_regions(state.color_id)
    region_mask = regions.region_id == int(region_id)
    selected = region_mask & split_mask.astype(bool)
    if not np.any(selected) or np.all(selected == region_mask):
        raise ValueError("split mask must select a non-empty proper subset of the region")
    state.color_id[selected] = int(new_color_id)
    state.dirty_bbox = _bbox_from_mask(region_mask)
    return state


def move_label(state: EditState, region_id: int, x: float, y: float) -> EditState:
    regions = build_regions(state.color_id)
    h, w = state.color_id.shape
    xi = int(round(x))
    yi = int(round(y))
    if not (0 <= xi < w and 0 <= yi < h):
        raise ValueError("label position is outside the canvas")
    if int(regions.region_id[yi, xi]) != int(region_id):
        raise ValueError("label must remain inside its own region")
    found = False
    for item in state.labels:
        if item.region_id == int(region_id):
            item.x = float(x)
            item.y = float(y)
            found = True
            break
    if not found:
        raise ValueError(f"label for region {region_id} not found")
    state.dirty_bbox = (max(0, yi - 16), max(0, xi - 16), min(h, yi + 17), min(w, xi + 17))
    return state


def crop_dirty(array: np.ndarray, bbox: tuple[int, int, int, int] | None) -> np.ndarray:
    """Return the dirty subarray for localized redraw/recompute paths."""
    if bbox is None:
        return array
    y0, x0, y1, x1 = bbox
    return array[y0:y1, x0:x1]
