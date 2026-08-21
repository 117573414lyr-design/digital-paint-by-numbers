from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np

from digital_paint.core.boundaries import merge_collinear_segments, shared_boundary_segments
from digital_paint.core.production_specs import validate_production_spec


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


def crossing_segment_count(segments: list[tuple[float, float, float, float]]) -> int:
    """Count true interior crossings; shared endpoints are legal."""
    count = 0
    for i, first in enumerate(segments):
        a = (first[0], first[1])
        b = (first[2], first[3])
        for second in segments[i + 1 :]:
            c = (second[0], second[1])
            d = (second[2], second[3])
            if _proper_cross(a, b, c, d):
                count += 1
    return count


def vector_quality_from_region_map(region_id: np.ndarray, label_sizes: list[float]) -> VectorQualityReport:
    segments = merge_collinear_segments(shared_boundary_segments(region_id))
    spec = validate_production_spec(label_sizes=label_sizes)
    return VectorQualityReport(
        segment_count=len(segments),
        duplicate_segments=duplicate_segment_count(segments),
        crossing_segments=crossing_segment_count(segments),
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
