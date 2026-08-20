from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True, slots=True)
class LibraryColor:
    number: str
    rgb: tuple[int, int, int]


def load_color_library(path: str | Path) -> list[LibraryColor]:
    colors: list[LibraryColor] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            colors.append(
                LibraryColor(
                    number=str(row["number"]).strip(),
                    rgb=(int(row["r"]), int(row["g"]), int(row["b"])),
                )
            )
    if not colors:
        raise ValueError("color library is empty")
    return colors


def _rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    arr = rgb.astype(np.uint8).reshape(1, -1, 3)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)


def match_palette_to_library(
    palette: np.ndarray,
    library: list[LibraryColor],
) -> tuple[np.ndarray, list[str]]:
    lib_rgb = np.asarray([c.rgb for c in library], dtype=np.uint8)
    src_lab = _rgb_to_lab(palette)
    lib_lab = _rgb_to_lab(lib_rgb)
    distances = ((src_lab[:, None, :] - lib_lab[None, :, :]) ** 2).sum(axis=2)
    chosen = distances.argmin(axis=1)
    matched = lib_rgb[chosen]
    numbers = [library[int(i)].number for i in chosen]
    return matched, numbers
