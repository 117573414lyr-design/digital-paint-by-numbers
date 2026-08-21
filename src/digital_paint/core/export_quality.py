from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from xml.etree import ElementTree as ET

import numpy as np

from digital_paint.core.boundaries import merge_collinear_segments, shared_boundary_segments
from digital_paint.core.production_specs import validate_production_spec

CancelCheck = Callable[[], None]
ProgressCallback = Callable[[str, int], None]


@dataclass(slots=True)
class VectorQualityReport:
    segment_count: int
    duplicate_segments: int
    crossing_segments: int
    line_width_ok: bool
    cmyk_ok: bool
    label_sizes_ok: bool

    @property
    def passed(self) -> bool:
        return (
            self.duplicate_segments == 0
            and self.crossing_segments == 0
            and self.line_width_ok
            and self.cmyk_ok
            and self.label_sizes_ok
        )


def canonical_segment(segment: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = segment
    a = (x1, y1)
    b = (x2, y2)
    return (x1, y1, x2, y2) if a <= b else (x2, y2, x1, y1)


def duplicate_segment_count(segments: list[tuple[float, float, float, float]]) -> int:
    canonical = [canonical_segment(s) for s in segments]
    return len(canonical) - len(set(canonical))


def _orientation(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _proper_cross(a, b, c, d) -> bool:
    if a in (c, d) or b in (c, d):
        return False
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)
    return (o1 * o2 < 0.0) and (o3 * o4 < 0.0)


def _segment_cells(
    segment: tuple[float, float, float, float],
    cell_size: float,
) -> tuple[range, range]:
    x1, y1, x2, y2 = segment
    min_x, max_x = sorted((x1, x2))
    min_y, max_y = sorted((y1, y2))
    gx0 = int(np.floor(min_x / cell_size))
    gx1 = int(np.floor(max_x / cell_size))
    gy0 = int(np.floor(min_y / cell_size))
    gy1 = int(np.floor(max_y / cell_size))
    return range(gx0, gx1 + 1), range(gy0, gy1 + 1)


def crossing_segment_count(
    segments: list[tuple[float, float, float, float]],
    *,
    cell_size: float = 32.0,
    cancel_check: CancelCheck | None = None,
    progress_callback: ProgressCallback | None = None,
) -> int:
    """Count true interior crossings using spatial buckets instead of O(N^2).

    Shared region-map boundaries are mostly short horizontal/vertical segments.
    A uniform grid restricts exact intersection tests to segments whose bounding
    boxes occupy at least one common spatial cell. Duplicate candidate pairs are
    de-duplicated before the exact orientation test.
    """
    if len(segments) < 2:
        return 0

    cell_size = max(float(cell_size), 4.0)
    buckets: dict[tuple[int, int], list[int]] = {}
    total = len(segments)
    for idx, segment in enumerate(segments):
        xs, ys = _segment_cells(segment, cell_size)
        for gx in xs:
            for gy in ys:
                buckets.setdefault((gx, gy), []).append(idx)
        if cancel_check is not None and idx % 2048 == 0:
            cancel_check()
        if progress_callback is not None and idx % 4096 == 0:
            progress_callback("建立边界空间索引", min(45, int(idx / total * 45)))

    candidate_pairs: set[tuple[int, int]] = set()
    bucket_items = list(buckets.values())
    bucket_total = max(len(bucket_items), 1)
    for bucket_index, ids in enumerate(bucket_items):
        if len(ids) > 1:
            ids = sorted(set(ids))
            for pos, first in enumerate(ids[:-1]):
                for second in ids[pos + 1 :]:
                    candidate_pairs.add((first, second))
        if cancel_check is not None and bucket_index % 512 == 0:
            cancel_check()
        if progress_callback is not None and bucket_index % 1024 == 0:
            progress_callback(
                "筛选可能交叉的边界",
                45 + min(30, int(bucket_index / bucket_total * 30)),
            )

    count = 0
    pair_total = max(len(candidate_pairs), 1)
    for pair_index, (i, j) in enumerate(candidate_pairs):
        first = segments[i]
        second = segments[j]
        a = (first[0], first[1])
        b = (first[2], first[3])
        c = (second[0], second[1])
        d = (second[2], second[3])
        if _proper_cross(a, b, c, d):
            count += 1
        if cancel_check is not None and pair_index % 4096 == 0:
            cancel_check()
        if progress_callback is not None and pair_index % 8192 == 0:
            progress_callback(
                "精确检查边界交叉",
                75 + min(25, int(pair_index / pair_total * 25)),
            )

    if progress_callback is not None:
        progress_callback("边界交叉检查完成", 100)
    return count


def vector_quality_from_region_map(
    region_id: np.ndarray,
    label_sizes: list[float],
    *,
    cancel_check: CancelCheck | None = None,
    progress_callback: ProgressCallback | None = None,
) -> VectorQualityReport:
    if progress_callback is not None:
        progress_callback("提取共享边界", 5)
    segments = merge_collinear_segments(shared_boundary_segments(region_id))
    if cancel_check is not None:
        cancel_check()
    if progress_callback is not None:
        progress_callback(f"共享边界 {len(segments)} 条", 12)

    duplicate_segments = duplicate_segment_count(segments)
    if cancel_check is not None:
        cancel_check()
    if progress_callback is not None:
        progress_callback("重复边界检查完成", 18)

    crossing_segments = crossing_segment_count(
        segments,
        cancel_check=cancel_check,
        progress_callback=(
            (lambda stage, pct: progress_callback(stage, 18 + int(pct * 0.78)))
            if progress_callback is not None
            else None
        ),
    )
    spec = validate_production_spec(label_sizes=label_sizes)
    if progress_callback is not None:
        progress_callback("生产参数检查完成", 100)
    return VectorQualityReport(
        segment_count=len(segments),
        duplicate_segments=duplicate_segments,
        crossing_segments=crossing_segments,
        line_width_ok=spec.line_width_ok,
        cmyk_ok=spec.cmyk_ok,
        label_sizes_ok=spec.label_sizes_ok,
    )


def inspect_svg_layers(path: str | Path) -> dict[str, bool]:
    """Verify expected editable SVG production groups and text objects."""
    root = ET.parse(path).getroot()
    groups: set[str] = set()
    text_count = 0
    for elem in root.iter():
        tag = elem.tag.split("}")[-1]
        if tag == "g" and elem.get("id"):
            groups.add(str(elem.get("id")))
        elif tag == "text":
            text_count += 1
    return {
        "has_boundaries_layer": "shared-boundaries" in groups,
        "has_labels_layer": "labels" in groups,
        "labels_are_text": text_count > 0,
    }
