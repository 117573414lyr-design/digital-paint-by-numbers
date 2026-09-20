"""End-to-end V0.1 pipeline plus the first connected-region cleanup."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from core.models import PaintByNumbersResult
from core.palette.quantize import quantize_lab
from core.regions.merge import merge_small_regions
from core.segmentation.regions import build_regions

ProgressCallback = Callable[[int, str], None]


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    target_colors: int = 24
    min_region_area: int = 20
    random_state: int = 42
    max_samples: int = 100_000


class PaintByNumbersPipeline:
    """CPU pipeline that produces a validated canonical project result."""

    def __init__(self, config: PipelineConfig | None = None) -> None:
        self.config = config or PipelineConfig()

    def run(
        self,
        source_rgb: np.ndarray,
        *,
        progress: ProgressCallback | None = None,
    ) -> PaintByNumbersResult:
        notify = progress or (lambda _value, _message: None)
        source = np.asarray(source_rgb)
        if source.dtype != np.uint8 or source.ndim != 3 or source.shape[2] != 3:
            raise ValueError("原图必须是 uint8 RGB 图像")
        source = np.ascontiguousarray(source)
        notify(10, "正在转换到 Lab 色彩空间并训练调色板…")
        color_map, palette = quantize_lab(
            source,
            self.config.target_colors,
            random_state=self.config.random_state,
            max_samples=self.config.max_samples,
        )
        notify(65, "正在合并极小连通色块…")
        color_map = merge_small_regions(color_map, self.config.min_region_area)
        notify(80, "正在建立 region_id / color_id 映射…")
        region_map, regions = build_regions(color_map)
        palette_rgb = np.asarray([entry.rgb for entry in palette], dtype=np.uint8)
        rendered = palette_rgb[color_map]
        result = PaintByNumbersResult(
            source_rgb=source.copy(),
            rendered_rgb=rendered,
            color_id_map=color_map,
            region_id_map=region_map,
            palette=palette,
            regions=regions,
        )
        result.validate()
        notify(100, "效果图和区域映射已生成")
        return result
