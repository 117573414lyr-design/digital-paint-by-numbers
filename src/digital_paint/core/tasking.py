from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
import json
import threading
import time
from typing import Any, Callable

import numpy as np


class CancelledError(RuntimeError):
    pass


class CancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise CancelledError("processing cancelled")


@dataclass(slots=True)
class StageRecord:
    name: str
    elapsed_s: float
    cache_hit: bool
    key: str


@dataclass(slots=True)
class StageCache:
    root: Path
    records: list[StageRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key_for(name: str, *parts: Any) -> str:
        digest = sha256(name.encode("utf-8"))
        for part in parts:
            if isinstance(part, np.ndarray):
                digest.update(str(part.shape).encode())
                digest.update(str(part.dtype).encode())
                digest.update(memoryview(np.ascontiguousarray(part)))
            else:
                digest.update(json.dumps(part, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8"))
        return digest.hexdigest()

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.npz"

    def load_arrays(self, key: str) -> dict[str, np.ndarray] | None:
        path = self._path(key)
        if not path.exists():
            return None
        with np.load(path, allow_pickle=False) as data:
            return {name: data[name] for name in data.files}

    def save_arrays(self, key: str, **arrays: np.ndarray) -> None:
        np.savez_compressed(self._path(key), **arrays)

    def run_array_stage(
        self,
        name: str,
        key_parts: tuple[Any, ...],
        producer: Callable[[], dict[str, np.ndarray]],
        token: CancellationToken | None = None,
    ) -> dict[str, np.ndarray]:
        if token:
            token.raise_if_cancelled()
        key = self.key_for(name, *key_parts)
        start = time.perf_counter()
        cached = self.load_arrays(key)
        if cached is not None:
            self.records.append(StageRecord(name, time.perf_counter() - start, True, key))
            return cached
        result = producer()
        if token:
            token.raise_if_cancelled()
        self.save_arrays(key, **result)
        self.records.append(StageRecord(name, time.perf_counter() - start, False, key))
        return result


def estimate_working_set_bytes(width: int, height: int, *, channels: int = 3, maps: int = 4) -> int:
    """Conservative CPU working-set estimate for planning large-image jobs."""
    pixels = int(width) * int(height)
    rgb = pixels * channels
    float_lab = pixels * channels * 4
    integer_maps = pixels * maps * 4
    overhead = int((rgb + float_lab + integer_maps) * 0.35)
    return rgb + float_lab + integer_maps + overhead


def choose_tile_size(width: int, height: int, memory_budget_mb: int = 1024) -> int:
    """Choose a square tile bounded by a conservative memory estimate."""
    budget = max(128, int(memory_budget_mb)) * 1024 * 1024
    bytes_per_pixel = 3 + 12 + 16
    side = int((budget / max(bytes_per_pixel * 2.0, 1.0)) ** 0.5)
    side = max(256, min(4096, side))
    return min(side, max(width, height))
