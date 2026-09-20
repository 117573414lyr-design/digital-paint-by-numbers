"""Stable project data structures shared by all output formats."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class PaletteColor:
    """A generated palette entry with a stable color identifier."""

    color_id: int
    rgb: tuple[int, int, int]
    lab: tuple[float, float, float]
    hex: str


@dataclass(frozen=True, slots=True)
class Region:
    """One connected image region mapped to exactly one palette color."""

    region_id: int
    color_id: int
    area: int
    bbox: tuple[int, int, int, int]


@dataclass(slots=True)
class PaintByNumbersResult:
    """Canonical result preserving mappings for future vector outputs."""

    source_rgb: np.ndarray
    rendered_rgb: np.ndarray
    color_id_map: np.ndarray
    region_id_map: np.ndarray
    palette: list[PaletteColor]
    regions: list[Region]

    def validate(self) -> None:
        height, width, channels = self.source_rgb.shape
        if channels != 3 or self.rendered_rgb.shape != self.source_rgb.shape:
            raise ValueError("原图和效果图必须为相同尺寸的 RGB 图像")
        if self.color_id_map.shape != (height, width):
            raise ValueError("color_id_map 尺寸与图像不一致")
        if self.region_id_map.shape != (height, width):
            raise ValueError("region_id_map 尺寸与图像不一致")
        palette_ids = {item.color_id for item in self.palette}
        if set(np.unique(self.color_id_map).tolist()) - palette_ids:
            raise ValueError("存在未映射到调色板的 color_id")
        region_lookup = {item.region_id: item for item in self.regions}
        if set(np.unique(self.region_id_map).tolist()) != set(region_lookup):
            raise ValueError("region_id_map 与区域清单不一致")
        for region_id, region in region_lookup.items():
            colors = np.unique(self.color_id_map[self.region_id_map == region_id])
            if colors.size != 1 or int(colors[0]) != region.color_id:
                raise ValueError(f"区域 {region_id} 未唯一映射到 color_id")
