from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np
from skimage.color import rgb2lab


@dataclass(frozen=True, slots=True)
class PaletteColor:
    code: str
    rgb: tuple[int, int, int]
    name: str = ""

    @property
    def hex(self) -> str:
        return "#%02X%02X%02X" % self.rgb


@dataclass(slots=True)
class PaletteMatch:
    source_index: int
    code: str
    rgb: tuple[int, int, int]
    delta_e76: float


def load_palette_json(path: str | Path) -> list[PaletteColor]:
    """Load a user palette from JSON [{code,rgb,name?}, ...]."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("palette JSON must be a non-empty list")
    colors: list[PaletteColor] = []
    for item in data:
        code = str(item["code"]).strip()
        rgb_raw = item["rgb"]
        if len(rgb_raw) != 3:
            raise ValueError(f"invalid RGB for palette code {code}")
        rgb = tuple(int(np.clip(v, 0, 255)) for v in rgb_raw)
        colors.append(PaletteColor(code=code, rgb=rgb, name=str(item.get("name", ""))))
    return colors


def save_palette_json(colors: list[PaletteColor], path: str | Path) -> None:
    payload = [{"code": c.code, "rgb": list(c.rgb), "hex": c.hex, "name": c.name} for c in colors]
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def match_palette(source_rgb: np.ndarray, target: list[PaletteColor]) -> list[PaletteMatch]:
    """Match generated colors to the user's color library in CIE Lab (Delta E 1976)."""
    if source_rgb.ndim != 2 or source_rgb.shape[1] != 3:
        raise ValueError("source_rgb must have shape (N, 3)")
    if not target:
        raise ValueError("target palette is empty")
    src_lab = rgb2lab((source_rgb.astype(np.float32) / 255.0)[None, :, :])[0]
    dst_rgb = np.asarray([c.rgb for c in target], dtype=np.float32)
    dst_lab = rgb2lab((dst_rgb / 255.0)[None, :, :])[0]
    distances = np.linalg.norm(src_lab[:, None, :] - dst_lab[None, :, :], axis=2)
    best = np.argmin(distances, axis=1)
    return [
        PaletteMatch(
            source_index=i,
            code=target[int(j)].code,
            rgb=target[int(j)].rgb,
            delta_e76=float(distances[i, int(j)]),
        )
        for i, j in enumerate(best)
    ]


def remap_image(color_id: np.ndarray, matches: list[PaletteMatch]) -> np.ndarray:
    lookup = np.asarray([m.rgb for m in matches], dtype=np.uint8)
    if int(color_id.max(initial=0)) >= len(lookup):
        raise ValueError("color_id refers to a color missing from palette matches")
    return lookup[color_id]
