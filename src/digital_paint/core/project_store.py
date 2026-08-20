from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json
import shutil
import time
from typing import Any

import numpy as np


@dataclass(slots=True)
class ProjectMeta:
    name: str
    source_path: str | None = None
    colors: int = 24
    min_region_area: int = 40
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    revision: int = 0


class ProjectStore:
    """Disk-backed project store with snapshots and compact array persistence."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "snapshots").mkdir(exist_ok=True)

    @property
    def meta_path(self) -> Path:
        return self.root / "project.json"

    @property
    def arrays_path(self) -> Path:
        return self.root / "project_arrays.npz"

    @property
    def journal_path(self) -> Path:
        return self.root / "journal.jsonl"

    def save(self, meta: ProjectMeta, **arrays: np.ndarray) -> None:
        meta.updated_at = time.time()
        self.meta_path.write_text(json.dumps(asdict(meta), ensure_ascii=False, indent=2), encoding="utf-8")
        if arrays:
            np.savez_compressed(self.arrays_path, **arrays)

    def load_meta(self) -> ProjectMeta:
        payload = json.loads(self.meta_path.read_text(encoding="utf-8"))
        return ProjectMeta(**payload)

    def load_arrays(self) -> dict[str, np.ndarray]:
        if not self.arrays_path.exists():
            return {}
        with np.load(self.arrays_path, allow_pickle=False) as data:
            return {name: data[name] for name in data.files}

    def snapshot(self, label: str, meta: ProjectMeta) -> Path:
        meta.revision += 1
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in label)[:40] or "snapshot"
        folder = self.root / "snapshots" / f"r{meta.revision:04d}_{safe}"
        folder.mkdir(parents=True, exist_ok=False)
        if self.meta_path.exists():
            shutil.copy2(self.meta_path, folder / self.meta_path.name)
        if self.arrays_path.exists():
            shutil.copy2(self.arrays_path, folder / self.arrays_path.name)
        self.append_journal("snapshot", {"revision": meta.revision, "label": label, "path": str(folder)})
        return folder

    def restore_snapshot(self, folder: str | Path) -> None:
        folder = Path(folder)
        meta = folder / "project.json"
        arrays = folder / "project_arrays.npz"
        if not meta.exists():
            raise FileNotFoundError(meta)
        shutil.copy2(meta, self.meta_path)
        if arrays.exists():
            shutil.copy2(arrays, self.arrays_path)
        self.append_journal("restore", {"path": str(folder)})

    def append_journal(self, action: str, payload: dict[str, Any]) -> None:
        record = {"time": time.time(), "action": action, "payload": payload}
        with self.journal_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def journal(self) -> list[dict[str, Any]]:
        if not self.journal_path.exists():
            return []
        return [json.loads(line) for line in self.journal_path.read_text(encoding="utf-8").splitlines() if line.strip()]
