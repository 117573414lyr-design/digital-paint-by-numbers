from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from digital_paint.core.labels import LabelPlacement, place_labels
from digital_paint.core.palette import PaletteColor, PaletteMatch, match_palette, remap_image
from digital_paint.core.performance import PerformanceReport, StageProfiler, recommended_sample_limit
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
    performance: PerformanceReport

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
    """Run the V7 CPU production pipeline with stage-level performance telemetry."""
    profiler = StageProfiler(image_rgb)
    sample_limit = recommended_sample_limit(image_rgb, colors)

    base: QuantizationResult = profiler.run(
        "quantize_lab",
        quantize_lab,
        image_rgb,
        colors,
        sample_limit=sample_limit,
    )
    merged_color_id = profiler.run(
        "merge_small_regions",
        merge_small_regions,
        base.color_id,
        base.palette_rgb,
        min_area=min_region_area,
    )
    regions = profiler.run("build_regions", build_regions, merged_color_id)

    palette_rgb = base.palette_rgb.copy()
    matches: list[PaletteMatch] | None = None
    if custom_palette:
        matches = profiler.run("match_palette", match_palette, base.palette_rgb, custom_palette)
        effect_rgb = profiler.run("remap_image", remap_image, merged_color_id, matches)
        palette_rgb = np.asarray([m.rgb for m in matches], dtype=np.uint8)
    else:
        effect_rgb = profiler.run("render_effect", lambda: palette_rgb[merged_color_id])

    labels = profiler.run("place_labels", place_labels, regions.region_id, regions.regions)
    qc = profiler.run(
        "run_qc",
        run_qc,
        regions,
        labels,
        min_area=min_region_area,
        palette_size=len(palette_rgb),
    )
    return ProductionResult(
        effect_rgb=effect_rgb,
        palette_rgb=palette_rgb,
        color_id=merged_color_id,
        regions=regions,
        labels=labels,
        palette_matches=matches,
        qc=qc,
        performance=profiler.report,
    )


def color_code_map(result: ProductionResult) -> dict[int, str]:
    if result.palette_matches:
        return {m.source_index: m.code for m in result.palette_matches}
    return {idx: str(idx + 1) for idx in range(len(result.palette_rgb))}
