from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Callable

import numpy as np

from digital_paint.core.editing import EditSession, EditState
from digital_paint.core.labels import LabelPlacement
from digital_paint.core.project_store import ProjectMeta, ProjectStore


class ProjectEditor:
    """Persist edit sessions with project snapshots and edit journal records."""

    def __init__(self, store: ProjectStore, meta: ProjectMeta, session: EditSession) -> None:
        self.store = store
        self.meta = meta
        self.session = session

    @classmethod
    def open(cls, root: str | Path, labels: list[LabelPlacement] | None = None) -> "ProjectEditor":
        store = ProjectStore(root)
        meta = store.load_meta()
        arrays = store.load_arrays()
        if "color_id" not in arrays:
            raise ValueError("project does not contain color_id")
        state = EditState(
            color_id=arrays["color_id"].astype(np.int32, copy=True),
            labels=list(labels or []),
            revision=meta.revision,
        )
        return cls(store, meta, EditSession(state))

    def apply(self, name: str, operation: Callable[[EditState], EditState]) -> EditState:
        state = self.session.apply(name, operation)
        self.meta.revision = state.revision
        self.store.append_journal(
            "edit",
            {
                "name": name,
                "revision": state.revision,
                "dirty_bbox": list(state.dirty_bbox) if state.dirty_bbox else None,
            },
        )
        return state

    def save(self, *, snapshot_label: str | None = None, **extra_arrays: np.ndarray) -> None:
        if snapshot_label and self.store.meta_path.exists():
            self.store.snapshot(snapshot_label, self.meta)
        arrays = {"color_id": self.session.state.color_id, **extra_arrays}
        self.store.save(self.meta, **arrays)
        self.store.append_journal(
            "save_edit_state",
            {
                "revision": self.session.state.revision,
                "dirty_bbox": list(self.session.state.dirty_bbox) if self.session.state.dirty_bbox else None,
                "labels": [asdict(item) for item in self.session.state.labels],
            },
        )

    def undo(self) -> EditState:
        state = self.session.undo()
        self.meta.revision = state.revision
        self.store.append_journal("undo", {"revision": state.revision})
        return state

    def redo(self) -> EditState:
        state = self.session.redo()
        self.meta.revision = state.revision
        self.store.append_journal("redo", {"revision": state.revision})
        return state
