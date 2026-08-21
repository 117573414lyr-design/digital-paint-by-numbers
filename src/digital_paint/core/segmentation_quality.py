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
    """Vectorized structure statistics for all regions in one pass."""
    if region_id.shape != edge_strength.shape:
        raise ValueError("region_id and edge_strength must have matching shapes")
    if not regions:
        return {}

    ids = region_id.ravel().astype(np.int64, copy=False)
    values = edge_strength.ravel().astype(np.float64, copy=False)
    max_id = int(ids.max(initial=-1))
    if max_id < 0:
        return {}

    counts = np.bincount(ids, minlength=max_id + 1).astype(np.float64)
    sums = np.bincount(ids, weights=values, minlength=max_id + 1)
    edge_counts = np.bincount(ids, weights=(values >= edge_threshold), minlength=max_id + 1)

    maxima = np.zeros(max_id + 1, dtype=np.float64)
    np.maximum.at(maxima, ids, values)

    means = np.divide(sums, counts, out=np.zeros_like(sums), where=counts > 0)
    fractions = np.divide(edge_counts, counts, out=np.zeros_like(edge_counts), where=counts > 0)

    result: dict[int, RegionStructure] = {}
    for region in regions:
        rid = region.region_id
        mean_gradient = float(means[rid])
        max_gradient = float(maxima[rid])
        edge_fraction = float(fractions[rid])
        protected = mean_gradient >= protect_mean_gradient or edge_fraction >= protect_edge_fraction
        result[rid] = RegionStructure(
            region_id=rid,
            mean_gradient=mean_gradient,
            max_gradient=max_gradient,
            edge_fraction=edge_fraction,
            protected=protected,
        )
    return result


def _region_slice(region: RegionInfo, shape: tuple[int, int], padding: int = 1) -> tuple[slice, slice]:
    minr, minc, maxr, maxc = region.bbox
    h, w = shape
    return (
        slice(max(0, minr - padding), min(h, maxr + padding)),
        slice(max(0, minc - padding), min(w, maxc + padding)),
    )


def _shared_border_counts(region_map: np.ndarray, region: RegionInfo, neighbours: set[int]) -> dict[int, int]:
    """Count touching borders inside the region bounding box instead of rescanning the full image."""
    scores = {rid: 0 for rid in neighbours}
    if not scores:
        return scores
    ys, xs = _region_slice(region, region_map.shape, padding=1)
    local = region_map[ys, xs]
    mask = local == region.region_id
    if not np.any(mask):
        return scores

    # Compare the selected region with four shifted neighbours using array operations.
    pairs = (
        (mask[1:, :], local[:-1, :]),
        (mask[:-1, :], local[1:, :]),
        (mask[:, 1:], local[:, :-1]),
        (mask[:, :-1], local[:, 1:]),
    )
    for src_mask, neighbour_values in pairs:
        touched = neighbour_values[src_mask]
        if touched.size == 0:
            continue
        ids, counts = np.unique(touched, return_counts=True)
        for rid, count in zip(ids, counts, strict=False):
            rid_i = int(rid)
            if rid_i in scores:
                scores[rid_i] += int(count)
    return scores


def merge_small_regions_structure_aware(
    color_id: np.ndarray,
    palette_rgb: np.ndarray,
    image_rgb: np.ndarray,
    *,
    min_area: int = 40,
    hard_min_area: int = 8,
    max_passes: int = 5,
    weights: MergeWeights = MergeWeights(),
) -> np.ndarray:
    """Merge fragments using color, adjacency and source-image structure.

    The implementation keeps the existing production scoring rules but avoids
    repeated whole-canvas scans for every fragment, which is the dominant cost
    on detailed images with many connected regions.
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
                ys, xs = _region_slice(region, work.shape, padding=0)
                local_regions = rr.region_id[ys, xs]
                local_work = work[ys, xs]
                local_work[local_regions == region.region_id] = target_color
                changed = True
        if not changed:
            break
    return work
