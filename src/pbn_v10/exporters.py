from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np
import svgwrite
from PIL import Image, ImageDraw, ImageFont

from .pipeline import PipelineResult, V10Config


def export_effect(result: PipelineResult, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(result.palette[result.indexed].astype(np.uint8), "RGB").save(output)


def export_palette(result: PipelineResult, output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(["number", "r", "g", "b", "hex"])
        for i, rgb in enumerate(result.palette, start=1):
            r, g, b = map(int, rgb)
            writer.writerow([i, r, g, b, f"#{r:02X}{g:02X}{b:02X}"])


def _path_from_contour(contour: np.ndarray) -> str:
    pts = contour.reshape(-1, 2)
    if len(pts) == 0:
        return ""
    parts = [f"M {pts[0,0]:.2f},{pts[0,1]:.2f}"]
    parts.extend(f"L {x:.2f},{y:.2f}" for x, y in pts[1:])
    parts.append("Z")
    return " ".join(parts)


def export_lineart_svg(result: PipelineResult, output: Path, config: V10Config) -> None:
    h, w = result.indexed.shape
    output.parent.mkdir(parents=True, exist_ok=True)
    dwg = svgwrite.Drawing(str(output), size=(w, h), viewBox=f"0 0 {w} {h}")
    line_group = dwg.g(id="shared-boundary-lineart", fill="none", stroke="#231815")
    labels = dwg.g(id="numbers", fill="#231815")

    for region in result.regions:
        rid = f"c{region.color_id + 1:02d}-r{region.region_index:03d}"
        path = _path_from_contour(region.contour)
        line_group.add(dwg.path(d=path, id=rid, stroke_width=config.line_width_pt))
        if region.label_radius >= config.label_min_radius:
            if region.label_radius < 10:
                size = config.font_sizes_pt[0]
            elif region.label_radius < 18:
                size = config.font_sizes_pt[1]
            else:
                size = config.font_sizes_pt[2]
            labels.add(
                dwg.text(
                    str(region.color_id + 1),
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
    total_regions = len(result.regions)
    unnumberable = [
        f"c{r.color_id + 1:02d}-r{r.region_index:03d}"
        for r in result.regions
        if r.label_radius < config.label_min_radius
    ]
    report = {
        "version": "10.0.0",
        "colors_requested": config.colors,
        "colors_used": int(len(np.unique(result.indexed))),
        "regions": total_regions,
        "unnumberable_regions": unnumberable,
        "pass": len(unnumberable) == 0,
        "checks": {
            "every_pixel_has_color": bool(np.all(result.indexed >= 0)),
            "palette_indices_valid": bool(result.indexed.max() < len(result.palette)),
            "tiny_regions_merged": all(r.area >= config.min_region_area for r in result.regions),
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
            "label_min_radius": config.label_min_radius,
            "line_width_pt": config.line_width_pt,
            "line_cmyk": list(config.line_cmyk),
            "font_sizes_pt": list(config.font_sizes_pt),
        },
        "outputs": ["effect.png", "lineart.svg", "palette.csv", "qa_report.json", "manifest.json"],
        "qa_pass": report["pass"],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
