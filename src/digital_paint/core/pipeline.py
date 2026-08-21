from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from digital_paint.core.labels import LabelPlacement, place_labels
from digital_paint.core.palette import PaletteColor, PaletteMatch, remap_image
from digital_paint.core.palette_quality import (
    PaletteQualityReport,
    classify_sensitive_sources,
    match_palette_ciede2000,
    palette_quality_report,
)
from digital_paint.core.performance import PerformanceReport, StageProfiler, recommended_sample_limit
from digital_paint.core.qc import QCReport, run_qc
from digital_paint.core.quantize import QuantizationResult, quantize_lab
from digital_paint.core.regions import RegionResult, build_regions
from digital_paint.core.runtime import (
    CancellationToken,
    MemoryPlan,
    StageCache,
    cached_array_stage,
    choose_tile_size,
)
from digital_paint.core.segmentation_quality import merge_small_regions_structure_aware


@dataclass(slots=True)
class ProductionResult:
    effect_rgb: np.ndarray
    palette_rgb: np.ndarray
    color_id: np.ndarray
    regions: RegionResult
    labels: list[LabelPlacement]
    palette_matches: list[PaletteMatch] | None
    palette_quality: PaletteQualityReport | None
    qc: QCReport
    performance: PerformanceReport
    memory_plan: MemoryPlan
    cache_hits: list[str]

    @property
    def region_id(self) -> np.ndarray:
        return self.regions.region_id


def build_production_result(
    image_rgb: np.ndarray,
    colors: int,
    *,
    min_region_area: int = 40,
    custom_palette: list[PaletteColor] | None = None,
    cancellation: CancellationToken | None = None,
    cache_dir: str | Path | None = None,
    memory_budget_mb: float = 2048.0,
) -> ProductionResult:
    """Run production with cancellation, deterministic stage cache and memory planning."""
    token = cancellation or CancellationToken()
    token.raise_if_cancelled()
    profiler = StageProfiler(image_rgb)
    sample_limit = recommended_sample_limit(image_rgb, colors)
    h, w = image_rgb.shape[:2]
    memory_plan = choose_tile_size(w, h, memory_budget_mb)
    cache = StageCache(cache_dir) if cache_dir is not None else None
    cache_hits: list[str] = []

    base: QuantizationResult = profiler.run(
        "quantize_lab",
        quantize_lab,
        image_rgb,
        colors,
        sample_limit=sample_limit,
    )
    token.raise_if_cancelled()

    merge_key = StageCache.key(
        "merge_structure_aware_v40",
        base.color_id,
        base.palette_rgb,
        min_region_area,
    )

    def do_merge() -> np.ndarray:
        return merge_small_regions_structure_aware(
            base.color_id,
            base.palette_rgb,
            image_rgb,
            min_area=min_region_area,
            hard_min_area=max(2, min(8, min_region_area)),
        )

    merged_color_id, cache_hit = profiler.run(
        "merge_structure_aware",
        cached_array_stage,
        cache,
        merge_key,
        do_merge,
    )
    if cache_hit:
        cache_hits.append("merge_structure_aware")
    token.raise_if_cancelled()

    regions = profiler.run("build_regions", build_regions, merged_color_id)
    token.raise_if_cancelled()

    palette_rgb = base.palette_rgb.copy()
    matches: list[PaletteMatch] | None = None
    quality: PaletteQualityReport | None = None
    if custom_palette:
        protected = profiler.run("classify_sensitive_colors", classify_sensitive_sources, base.palette_rgb)
        matches = profiler.run(
            "match_palette_ciede2000",
            match_palette_ciede2000,
            base.palette_rgb,
            custom_palette,
            protected_source_indices=protected,
        )
        quality = profiler.run(
            "palette_quality_report",
            palette_quality_report,
            custom_palette,
            matches,
            len(base.palette_rgb),
        )
        effect_rgb = profiler.run("remap_image", remap_image, merged_color_id, matches)
        palette_rgb = np.asarray([m.rgb for m in matches], dtype=np.uint8)
    else:
        effect_rgb = profiler.run("render_effect", lambda: palette_rgb[merged_color_id])
    token.raise_if_cancelled()

    labels = profiler.run("place_labels", place_labels, regions.region_id, regions.regions)
    token.raise_if_cancelled()
    qc = profiler.run(
        "run_qc",
        run_qc,
        regions,
        labels,
        min_area=min_region_area,
        palette_size=len(palette_rgb),
    )
    token.raise_if_cancelled()

    return ProductionResult(
        effect_rgb=effect_rgb,
        palette_rgb=palette_rgb,
        color_id=merged_color_id,
        regions=regions,
        labels=labels,
        palette_matches=matches,
        palette_quality=quality,
        qc=qc,
        performance=profiler.report,
        memory_plan=memory_plan,
        cache_hits=cache_hits,
    )


def color_code_map(result: ProductionResult) -> dict[int, str]:
    if result.palette_matches:
        return {m.source_index: m.code for m in result.palette_matches}
    return {idx: str(idx + 1) for idx in range(len(result.palette_rgb))}
