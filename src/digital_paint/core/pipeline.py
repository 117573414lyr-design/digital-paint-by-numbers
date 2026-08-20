from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from digital_paint.core.labels import LabelPlacement, place_labels
from digital_paint.core.palette import PaletteColor, PaletteMatch, match_palette, remap_image
from digital_paint.core.qc import QCReport, run_qc
from digital_paint.core.quantize import QuantizationResult, quantize_lab
from digital_paint.core.regions import RegionResult, build_regions, merge_small_regions


@dataclass(slots=True)
class ProductionResult:
    effect_rgb: np.ndarray
    palette_rgb: np.ndarray
    color_id: np.ndarray
    regions: RegionResult
    labels: list[LabelPlacement]
    palette_matches: list[PaletteMatch] | None
    qc: QCReport

    @property
    def region_id(self) -> np.ndarray:
        return self.regions.region_id


def build_production_result(
    image_rgb: np.ndarray,
    colors: int,
    *,
    min_region_area: int = 40,
    custom_palette: list[PaletteColor] | None = None,
) -> ProductionResult:
    """Run V6 CPU production pipeline from source pixels to QC-ready region data."""
    base: QuantizationResult = quantize_lab(image_rgb, colors)
    merged_color_id = merge_small_regions(
        base.color_id,
        base.palette_rgb,
        min_area=min_region_area,
    )
    regions = build_regions(merged_color_id)

    palette_rgb = base.palette_rgb.copy()
    matches: list[PaletteMatch] | None = None
    if custom_palette:
        matches = match_palette(base.palette_rgb, custom_palette)
        effect_rgb = remap_image(merged_color_id, matches)
        palette_rgb = np.asarray([m.rgb for m in matches], dtype=np.uint8)
    else:
        effect_rgb = palette_rgb[merged_color_id]

    labels = place_labels(regions.region_id, regions.regions)
    qc = run_qc(regions, labels, min_area=min_region_area, palette_size=len(palette_rgb))
    return ProductionResult(
        effect_rgb=effect_rgb,
        palette_rgb=palette_rgb,
        color_id=merged_color_id,
        regions=regions,
        labels=labels,
        palette_matches=matches,
        qc=qc,
    )


def color_code_map(result: ProductionResult) -> dict[int, str]:
    if result.palette_matches:
        return {m.source_index: m.code for m in result.palette_matches}
    return {idx: str(idx + 1) for idx in range(len(result.palette_rgb))}
