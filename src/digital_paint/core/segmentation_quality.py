from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import gaussian_filter, sobel
from skimage.color import deltaE_ciede2000, rgb2gray, rgb2lab

from digital_paint.core.regions import RegionInfo, build_regions


@dataclass(frozen=True, slots=True)
class MergeWeights:
    shared_border: float = 4.0
    color_similarity: float = 2.5
    target_area: float = 0.35
    structure_penalty: float = 5.0


@dataclass(frozen=True, slots=True)
class RegionStructure:
    region_id: int
    mean_gradient: float
    max_gradient: float
    edge_fraction: float
    protected: bool


def edge_strength_map(image_rgb: np.ndarray, sigma: float = 0.8) -> np.ndarray:
    """Return normalized edge strength for structure-aware fragment decisions."""
    if image_rgb.ndim != 3 or image_rgb.shape[2] != 3:
        raise ValueError("image_rgb must have shape (H, W, 3)")
    gray = rgb2gray(image_rgb.astype(np.float32) / 255.0)
    if sigma > 0:
        gray = gaussian_filter(gray, sigma=sigma)
    gx = sobel(gray, axis=1)
    gy = sobel(gray, axis=0)
    magnitude = np.hypot(gx, gy).astype(np.float32)
    peak = float(magnitude.max(initial=0.0))
    if peak > 0:
        magnitude /= peak
    return magnitude


def analyze_region_structure(
    region_id: np.ndarray,
    regions: list[RegionInfo],
    edge_strength: np.ndarray,
    *,
    edge_threshold: float = 0.24,
    protect_mean_gradient: float = 0.20,
    protect_edge_fraction: float = 0.30,
) -> dict[int, RegionStructure]:
    """Estimate whether each region likely carries visually important structure."""
    if region_id.shape != edge_strength.shape:
        raise ValueError("region_id and edge_strength must have matching shapes")
    result: dict[int, RegionStructure] = {}
    for region in regions:
        values = edge_strength[region_id == region.region_id]
        if values.size == 0:
            continue
        mean_gradient = float(values.mean())
        max_gradient = float(values.max(initial=0.0))
        edge_fraction = float(np.mean(values >= edge_threshold))
        protected = mean_gradient >= protect_mean_gradient or edge_fraction >= protect_edge_fraction
        result[region.region_id] = RegionStructure(
            region_id=region.region_id,
            mean_gradient=mean_gradient,
            max_gradient=max_gradient,
            edge_fraction=edge_fraction,
            protected=protected,
        )
    return result


def _shared_border_counts(region_map: np.ndarray, region: RegionInfo, neighbours: set[int]) -> dict[int, int]:
    scores = {rid: 0 for rid in neighbours}
    ys, xs = np.nonzero(region_map == region.region_id)
    h, w = region_map.shape
    for y, x in zip(ys, xs, strict=False):
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < h and 0 <= nx < w:
                rid = int(region_map[ny, nx])
                if rid in scores:
                    scores[rid] += 1
    return scores


def merge_small_regions_structure_aware(
    color_id: np.ndarray,
    palette_rgb: np.ndarray,
    image_rgb: np.ndarray,
    *,
    min_area: int = 40,
    hard_min_area: int = 8,
    max_passes: int = 8,
    weights: MergeWeights = MergeWeights(),
) -> np.ndarray:
    """Merge fragments using color, adjacency and source-image structure.

    Regions below ``hard_min_area`` remain merge candidates even when edge-rich,
    because they are usually impossible to number. Between hard_min_area and
    min_area, edge-rich regions are protected from automatic merging.
    """
    if min_area < 1 or hard_min_area < 1 or hard_min_area > min_area:
        raise ValueError("require 1 <= hard_min_area <= min_area")
    if color_id.shape != image_rgb.shape[:2]:
        raise ValueError("color_id and image_rgb dimensions must match")

    work = color_id.astype(np.int32, copy=True)
    edge_map = edge_strength_map(image_rgb)
    palette_lab = rgb2lab((palette_rgb.astype(np.float32) / 255.0)[None, :, :])[0]

    for _ in range(max_passes):
        rr = build_regions(work)
        by_id = {r.region_id: r for r in rr.regions}
        structures = analyze_region_structure(rr.region_id, rr.regions, edge_map)
        candidates = [r for r in rr.regions if r.area < min_area]
        if not candidates:
            break

        changed = False
        for region in sorted(candidates, key=lambda r: r.area):
            structure = structures.get(region.region_id)
            if region.area >= hard_min_area and structure and structure.protected:
                continue
            neighbours = rr.adjacency.get(region.region_id, set())
            if not neighbours:
                continue
            borders = _shared_border_counts(rr.region_id, region, neighbours)
            perimeter_proxy = max(sum(borders.values()), 1)
            ranked: list[tuple[float, int]] = []
            for neighbour_id, shared in borders.items():
                neighbour = by_id[neighbour_id]
                delta_e = float(
                    deltaE_ciede2000(
                        palette_lab[region.color_id][None, :],
                        palette_lab[neighbour.color_id][None, :],
                    )[0]
                )
                shared_ratio = shared / perimeter_proxy
                color_similarity = 1.0 / (1.0 + delta_e)
                area_bonus = np.log1p(neighbour.area) / 10.0
                neighbour_structure = structures.get(neighbour_id)
                structure_penalty = 0.0
                if structure and structure.protected:
                    structure_penalty += structure.mean_gradient
                if neighbour_structure and neighbour_structure.protected:
                    # Prefer merging *into* stable structural regions, not across them.
                    area_bonus += 0.08
                score = (
                    weights.shared_border * shared_ratio
                    + weights.color_similarity * color_similarity
                    + weights.target_area * area_bonus
                    - weights.structure_penalty * structure_penalty
                )
                ranked.append((score, neighbour.color_id))

            if ranked:
                target_color = max(ranked, key=lambda item: item[0])[1]
                work[rr.region_id == region.region_id] = target_color
                changed = True
        if not changed:
            break
    return work
