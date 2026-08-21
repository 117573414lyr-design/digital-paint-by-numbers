from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import threading
from typing import Any, Callable, TypeVar

import numpy as np

T = TypeVar("T")


class PipelineCancelled(RuntimeError):
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
            raise PipelineCancelled("production pipeline cancelled")


@dataclass(frozen=True, slots=True)
class Tile:
    y0: int
    y1: int
    x0: int
    x1: int


@dataclass(frozen=True, slots=True)
class MemoryPlan:
    estimated_mb: float
    budget_mb: float
    tile_size: int
    use_tiles: bool


def choose_tile_size(width: int, height: int, budget_mb: float, *, bytes_per_pixel: int = 40) -> MemoryPlan:
    pixels = width * height
    estimated = pixels * bytes_per_pixel / (1024 * 1024)
    budget = max(float(budget_mb), 128.0)
    if estimated <= budget * 0.75:
        return MemoryPlan(estimated, budget, max(width, height), False)
    target_bytes = budget * 1024 * 1024 * 0.35
    side = int(max(256, min(2048, (target_bytes / max(bytes_per_pixel, 1)) ** 0.5)))
    return MemoryPlan(estimated, budget, side, True)


def iter_tiles(shape: tuple[int, int], tile_size: int, *, overlap: int = 8) -> list[Tile]:
    h, w = shape
    tile_size = max(64, int(tile_size))
    overlap = max(0, min(int(overlap), tile_size // 4))
    tiles: list[Tile] = []
    step = max(1, tile_size - overlap)
    for y0 in range(0, h, step):
        for x0 in range(0, w, step):
            tiles.append(Tile(y0, min(h, y0 + tile_size), x0, min(w, x0 + tile_size)))
    return tiles


class StageCache:
    """Disk-backed NPZ/JSON cache for deterministic expensive stages."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(name: str, *parts: Any) -> str:
        h = sha256(name.encode("utf-8"))
        for part in parts:
            if isinstance(part, np.ndarray):
                h.update(str(part.shape).encode())
                h.update(str(part.dtype).encode())
                h.update(np.ascontiguousarray(part).view(np.uint8))
            else:
                h.update(json.dumps(part, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8"))
        return h.hexdigest()

    def load_array(self, key: str) -> np.ndarray | None:
        path = self.root / f"{key}.npy"
        if not path.exists():
            return None
        return np.load(path, allow_pickle=False)

    def save_array(self, key: str, array: np.ndarray) -> None:
        np.save(self.root / f"{key}.npy", np.asarray(array), allow_pickle=False)


def cached_array_stage(
    cache: StageCache | None,
    key: str,
    func: Callable[[], np.ndarray],
) -> tuple[np.ndarray, bool]:
    if cache is not None:
        existing = cache.load_array(key)
        if existing is not None:
            return existing, True
    result = np.asarray(func())
    if cache is not None:
        cache.save_array(key, result)
    return result, False
