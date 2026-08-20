from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from skimage.measure import label, regionprops


@dataclass(slots=True)
class RegionInfo:
    region_id: int
    color_id: int
    area: int
    bbox: tuple[int, int, int, int]
    centroid: tuple[float, float]


@dataclass(slots=True)
class RegionResult:
    color_id: np.ndarray
    region_id: np.ndarray
    regions: list[RegionInfo]
    adjacency: dict[int, set[int]]


def build_regions(color_id: np.ndarray) -> RegionResult:
    """Build stable connected-region IDs for a palette-index map."""
    if color_id.ndim != 2:
        raise ValueError("color_id must be a 2-D array")

    region_map = np.full(color_id.shape, -1, dtype=np.int32)
    regions: list[RegionInfo] = []
    next_id = 0

    for cid in np.unique(color_id):
        components = label(color_id == cid, connectivity=1)
        for prop in regionprops(components):
            mask = components == prop.label
            region_map[mask] = next_id
            regions.append(
                RegionInfo(
                    region_id=next_id,
                    color_id=int(cid),
                    area=int(prop.area),
                    bbox=tuple(int(v) for v in prop.bbox),
                    centroid=(float(prop.centroid[0]), float(prop.centroid[1])),
                )
            )
            next_id += 1

    return RegionResult(
        color_id=color_id.astype(np.int32, copy=True),
        region_id=region_map,
        regions=regions,
        adjacency=build_adjacency(region_map),
    )


def build_adjacency(region_id: np.ndarray) -> dict[int, set[int]]:
    """Return 4-neighbour region adjacency without duplicate edges."""
    ids = np.unique(region_id)
    graph = {int(rid): set() for rid in ids if rid >= 0}
    pairs = []
    if region_id.shape[1] > 1:
        pairs.append((region_id[:, :-1], region_id[:, 1:]))
    if region_id.shape[0] > 1:
        pairs.append((region_id[:-1, :], region_id[1:, :]))
    for a, b in pairs:
        changed = a != b
        for left, right in zip(a[changed].ravel(), b[changed].ravel(), strict=False):
            left_i, right_i = int(left), int(right)
            if left_i >= 0 and right_i >= 0:
                graph[left_i].add(right_i)
                graph[right_i].add(left_i)
    return graph


def merge_small_regions(
    color_id: np.ndarray,
    palette_rgb: np.ndarray,
    *,
    min_area: int = 40,
    max_passes: int = 8,
) -> np.ndarray:
    """Merge small connected fragments into the best touching neighbour.

    The score prefers long shared borders first and smaller RGB distance second.
    This preserves subject structure better than a global majority filter.
    """
    if min_area < 1:
        raise ValueError("min_area must be >= 1")
    work = color_id.astype(np.int32, copy=True)

    for _ in range(max_passes):
        rr = build_regions(work)
        by_id = {r.region_id: r for r in rr.regions}
        small = [r for r in rr.regions if r.area < min_area]
        if not small:
            break
        changed = False
        for region in sorted(small, key=lambda r: r.area):
            mask = rr.region_id == region.region_id
            neighbours = rr.adjacency.get(region.region_id, set())
            if not neighbours:
                continue
            border_scores: dict[int, int] = {n: 0 for n in neighbours}
            ys, xs = np.nonzero(mask)
            for y, x in zip(ys, xs, strict=False):
                for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                    if 0 <= ny < work.shape[0] and 0 <= nx < work.shape[1]:
                        rid = int(rr.region_id[ny, nx])
                        if rid in border_scores:
                            border_scores[rid] += 1
            src_rgb = palette_rgb[region.color_id].astype(np.float32)
            ranked: list[tuple[float, int]] = []
            for neighbour_id, shared in border_scores.items():
                neighbour = by_id[neighbour_id]
                dst_rgb = palette_rgb[neighbour.color_id].astype(np.float32)
                distance = float(np.linalg.norm(src_rgb - dst_rgb))
                score = shared * 1000.0 - distance
                ranked.append((score, neighbour.color_id))
            if ranked:
                target_color = max(ranked, key=lambda item: item[0])[1]
                work[mask] = target_color
                changed = True
        if not changed:
            break
    return work
