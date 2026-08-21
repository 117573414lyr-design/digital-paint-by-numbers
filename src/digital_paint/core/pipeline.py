from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

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
from digital_paint.core.performance_gate import PerformanceGateResult, evaluate_performance_gate
from digital_paint.core.qc import QCReport, run_qc
from digital_paint.core.quantize import quantize_lab
from digital_paint.core.regions import RegionResult, build_regions
from digital_paint.core.runtime import (
    CancellationToken,
    MemoryPlan,
    StageCache,
    cached_array_stage,
    choose_tile_size,
)
from digital_paint.core.segmentation_quality import merge_small_regions_structure_aware

ProgressCallback = Callable[[str, int], None]


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
    performance_gate: PerformanceGateResult
    memory_plan: MemoryPlan
    cache_hits: list[str]

    @property
    def region_id(self) -> np.ndarray:
        return self.regions.region_id


def _emit(callback: ProgressCallback | None, stage: str, percent: int) -> None:
    if callback is not None:
        callback(stage, max(0, min(100, int(percent))))


def _load_or_quantize(
    profiler: StageProfiler,
    cache: StageCache | None,
    image_rgb: np.ndarray,
    colors: int,
    sample_limit: int,
    cache_hits: list[str],
) -> tuple[np.ndarray, np.ndarray]:
    if cache is not None:
        key = StageCache.key("quantize_lab_v3", image_rgb, int(colors), int(sample_limit))
        color_key = f"{key}_color"
        palette_key = f"{key}_palette"
        cached_color = cache.load_array(color_key)
        cached_palette = cache.load_array(palette_key)
        if cached_color is not None and cached_palette is not None:
            cache_hits.append("quantize_lab")
            return cached_color.astype(np.int32, copy=False), cached_palette.astype(np.uint8, copy=False)
    else:
        color_key = palette_key = ""

    base = profiler.run(
        "quantize_lab",
        quantize_lab,
        image_rgb,
        colors,
        sample_limit=sample_limit,
    )
    color_id = base.color_id.astype(np.int32, copy=False)
    palette_rgb = base.palette_rgb.astype(np.uint8, copy=False)
    if cache is not None:
        cache.save_array(color_key, color_id)
        cache.save_array(palette_key, palette_rgb)
    return color_id, palette_rgb


def build_production_result(
    image_rgb: np.ndarray,
    colors: int,
    *,
    min_region_area: int = 40,
    custom_palette: list[PaletteColor] | None = None,
    cancellation: CancellationToken | None = None,
    cache_dir: str | Path | None = None,
    memory_budget_mb: float = 2048.0,
    progress_callback: ProgressCallback | None = None,
) -> ProductionResult:
    """Run the production chain with cache, cancellation and visible stage progress."""
    token = cancellation or CancellationToken()
    token.raise_if_cancelled()
    profiler = StageProfiler(image_rgb)
    sample_limit = recommended_sample_limit(image_rgb, colors)
    h, w = image_rgb.shape[:2]
    megapixels = (h * w) / 1_000_000.0
    memory_plan = choose_tile_size(w, h, memory_budget_mb)
    cache = StageCache(cache_dir) if cache_dir is not None else None
    cache_hits: list[str] = []

    _emit(progress_callback, "分色 / KMeans", 8)
    base_color_id, base_palette_rgb = _load_or_quantize(
        profiler,
        cache,
        image_rgb,
        colors,
        sample_limit,
        cache_hits,
    )
    token.raise_if_cancelled()
    _emit(progress_callback, "分色完成", 24)

    # Large canvases can contain thousands of tiny connected regions. More than
    # three full structure-aware passes has poor interactive value at >=4 MP.
    merge_passes = 3 if megapixels >= 4.0 else 4 if megapixels >= 2.0 else 5
    merge_key = StageCache.key(
        "merge_structure_aware_v42",
        base_color_id,
        base_palette_rgb,
        min_region_area,
        merge_passes,
    )

    def on_merge_progress(pass_index: int, total: int, candidates: int) -> None:
        span_start, span_end = 28, 62
        pct = span_start + int((pass_index - 1) / max(total, 1) * (span_end - span_start))
        _emit(progress_callback, f"碎块优化 {pass_index}/{total}（候选 {candidates}）", pct)

    def do_merge() -> np.ndarray:
        return merge_small_regions_structure_aware(
            base_color_id,
            base_palette_rgb,
            image_rgb,
            min_area=min_region_area,
            hard_min_area=max(2, min(8, min_region_area)),
            max_passes=merge_passes,
            progress_callback=on_merge_progress,
            cancel_check=token.raise_if_cancelled,
        )

    _emit(progress_callback, "结构保护 / 碎块优化", 28)
    merged_color_id, cache_hit = profiler.run(
        "merge_structure_aware",
        cached_array_stage,
        cache,
        merge_key,
        do_merge,
    )
    if cache_hit:
        cache_hits.append("merge_structure_aware")
        _emit(progress_callback, "碎块优化（缓存命中）", 62)
    token.raise_if_cancelled()

    _emit(progress_callback, "建立连通区域", 68)
    regions = profiler.run("build_regions", build_regions, merged_color_id)
    token.raise_if_cancelled()

    palette_rgb = base_palette_rgb.copy()
    matches: list[PaletteMatch] | None = None
    quality: PaletteQualityReport | None = None
    if custom_palette:
        _emit(progress_callback, "匹配自有色库 CIEDE2000", 74)
        protected = profiler.run("classify_sensitive_colors", classify_sensitive_sources, base_palette_rgb)
        matches = profiler.run(
            "match_palette_ciede2000",
            match_palette_ciede2000,
            base_palette_rgb,
            custom_palette,
            protected_source_indices=protected,
        )
        quality = profiler.run(
            "palette_quality_report",
            palette_quality_report,
            custom_palette,
            matches,
            len(base_palette_rgb),
        )
        effect_rgb = profiler.run("remap_image", remap_image, merged_color_id, matches)
        palette_rgb = np.asarray([m.rgb for m in matches], dtype=np.uint8)
    else:
        _emit(progress_callback, "生成效果图", 76)
        effect_rgb = profiler.run("render_effect", lambda: palette_rgb[merged_color_id])
    token.raise_if_cancelled()

    _emit(progress_callback, "自动放置编号", 84)
    labels = profiler.run("place_labels", place_labels, regions.region_id, regions.regions)
    token.raise_if_cancelled()

    _emit(progress_callback, "生产质检 QC", 94)
    qc = profiler.run(
        "run_qc",
        run_qc,
        regions,
        labels,
        min_area=min_region_area,
        palette_size=len(palette_rgb),
    )
    token.raise_if_cancelled()

    performance_gate = evaluate_performance_gate(profiler.report, memory_plan)
    _emit(progress_callback, "完成", 100)
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
        performance_gate=performance_gate,
        memory_plan=memory_plan,
        cache_hits=cache_hits,
    )


def color_code_map(result: ProductionResult) -> dict[int, str]:
    if result.palette_matches:
        return {m.source_index: m.code for m in result.palette_matches}
    return {idx: str(idx + 1) for idx in range(len(result.palette_rgb))}
