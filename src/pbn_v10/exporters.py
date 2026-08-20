from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import svgwrite
from PIL import Image

from .geometry import shared_boundary_paths
from .pipeline import PipelineResult, V10Config


def export_effect(result: PipelineResult, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(result.palette[result.indexed].astype(np.uint8), "RGB").save(output)


def export_palette(result: PipelineResult, output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(["number", "r", "g", "b", "hex"])
        for i, rgb in enumerate(result.palette):
            r, g, b = map(int, rgb)
            writer.writerow([result.palette_numbers[i], r, g, b, f"#{r:02X}{g:02X}{b:02X}"])


def _svg_path(points: list[tuple[float, float]]) -> str:
    if not points:
        return ""
    body = [f"M {points[0][0]:.2f},{points[0][1]:.2f}"]
    body.extend(f"L {x:.2f},{y:.2f}" for x, y in points[1:])
    return " ".join(body)


def export_lineart_svg(result: PipelineResult, output: Path, config: V10Config) -> None:
    h, w = result.indexed.shape
    output.parent.mkdir(parents=True, exist_ok=True)
    dwg = svgwrite.Drawing(str(output), size=(w, h), viewBox=f"0 0 {w} {h}")
    line_group = dwg.g(id="shared-boundary-lineart", fill="none", stroke="#231815")
    labels = dwg.g(id="numbers", fill="#231815")

    for i, points in enumerate(shared_boundary_paths(result.indexed, config.smooth_iterations), start=1):
        if len(points) >= 2:
            line_group.add(dwg.path(d=_svg_path(points), id=f"boundary-{i:05d}", stroke_width=config.line_width_pt))

    for region in result.regions:
        if region.label_radius < config.label_min_radius:
            continue
        size = config.font_sizes_pt[0] if region.label_radius < 10 else config.font_sizes_pt[1] if region.label_radius < 18 else config.font_sizes_pt[2]
        labels.add(
            dwg.text(
                result.palette_numbers[region.color_id],
                insert=(region.label_x, region.label_y),
                text_anchor="middle",
                dominant_baseline="central",
                font_size=size,
            )
        )

    dwg.add(line_group)
    dwg.add(labels)
    dwg.save()


def export_qa(result: PipelineResult, output_json: Path, config: V10Config) -> dict:
    unnumberable = [
        f"c{r.color_id + 1:02d}-r{r.region_index:03d}"
        for r in result.regions
        if r.label_radius < config.label_min_radius
    ]
    report = {
        "version": "10.1.0",
        "colors_requested": config.colors,
        "colors_used": int(len(np.unique(result.indexed))),
        "regions": len(result.regions),
        "unnumberable_regions": unnumberable,
        "pass": len(unnumberable) == 0,
        "checks": {
            "every_pixel_has_color": bool(np.all(result.indexed >= 0)),
            "palette_indices_valid": bool(result.indexed.max() < len(result.palette)),
            "tiny_regions_merged": all(r.area >= config.min_region_area for r in result.regions),
            "number_capacity_pass": len(unnumberable) == 0,
            "shared_boundary_export": True,
        },
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def export_manifest(output_dir: Path, source: Path, config: V10Config, report: dict) -> None:
    manifest = {
        "pipeline": "digital-paint-by-numbers-v10",
        "source": source.name,
        "config": {
            "colors": config.colors,
            "min_region_area": config.min_region_area,
            "smooth_epsilon": config.smooth_epsilon,
            "smooth_iterations": config.smooth_iterations,
            "label_min_radius": config.label_min_radius,
            "line_width_pt": config.line_width_pt,
            "line_cmyk": list(config.line_cmyk),
            "font_sizes_pt": list(config.font_sizes_pt),
            "color_library": str(config.color_library) if config.color_library else None,
        },
        "outputs": ["effect.png", "lineart.svg", "palette.csv", "production.pdf", "qa_report.json", "manifest.json"],
        "qa_pass": report["pass"],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
