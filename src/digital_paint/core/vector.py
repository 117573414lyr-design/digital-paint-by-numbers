from __future__ import annotations

from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree

import numpy as np
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from skimage.measure import find_contours

from digital_paint.core.labels import LabelPlacement
from digital_paint.core.regions import RegionInfo

LINE_CMYK = (0.40, 1.00, 1.00, 1.00)
LINE_WIDTH_PT = 0.1


def region_contours(region_id: np.ndarray, region: RegionInfo, tolerance: float = 0.8) -> list[np.ndarray]:
    """Extract closed region contours. Coordinates are returned as x/y floats."""
    mask = (region_id == region.region_id).astype(np.uint8)
    raw = find_contours(mask, 0.5)
    result: list[np.ndarray] = []
    for contour in raw:
        if len(contour) < 4:
            continue
        xy = np.column_stack((contour[:, 1], contour[:, 0])).astype(np.float64)
        # Lightweight distance-based point reduction; keeps endpoints and avoids dense pixel stair-steps.
        kept = [xy[0]]
        for point in xy[1:]:
            if float(np.linalg.norm(point - kept[-1])) >= tolerance:
                kept.append(point)
        arr = np.asarray(kept)
        if len(arr) >= 3:
            result.append(arr)
    return result


def export_line_svg(
    path: str | Path,
    region_id: np.ndarray,
    regions: list[RegionInfo],
    labels: list[LabelPlacement],
    color_codes: dict[int, str] | None = None,
) -> None:
    """Export editable SVG linework and text labels."""
    h, w = region_id.shape
    root = Element("svg", xmlns="http://www.w3.org/2000/svg", width=str(w), height=str(h), viewBox=f"0 0 {w} {h}")
    paths = SubElement(root, "g", id="boundaries", fill="none", stroke="#231815", **{"stroke-width": "0.1"})
    # Region loops can overlap on shared borders in SVG V6; QC reports this as a vector-optimization candidate.
    for region in regions:
        for contour in region_contours(region_id, region):
            points = " ".join(f"{x:.2f},{y:.2f}" for x, y in contour)
            SubElement(paths, "polyline", points=points, fill="none")
    label_group = SubElement(root, "g", id="labels", fill="#231815", **{"font-family": "Arial"})
    for item in labels:
        text = SubElement(
            label_group,
            "text",
            x=f"{item.x:.2f}",
            y=f"{item.y:.2f}",
            **{"font-size": f"{item.font_pt:.1f}pt", "text-anchor": "middle", "dominant-baseline": "middle"},
        )
        text.text = color_codes.get(item.color_id, str(item.color_id + 1)) if color_codes else str(item.color_id + 1)
    ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def export_vector_pdf(
    path: str | Path,
    region_id: np.ndarray,
    regions: list[RegionInfo],
    labels: list[LabelPlacement],
    palette_rgb: np.ndarray,
    color_codes: dict[int, str] | None = None,
) -> None:
    """Export a three-page PDF: effect, numbered linework, and palette.

    Pages use vector polygons/text. The effect page is reconstructed from region paths rather than embedded as one raster page.
    """
    h, w = region_id.shape
    c = canvas.Canvas(str(path), pagesize=(float(w), float(h)))

    # Page 1: effect image reconstructed as filled vector regions.
    c.setTitle("Digital Paint by Numbers V6")
    for region in regions:
        rgb = palette_rgb[region.color_id].astype(float) / 255.0
        c.setFillColorRGB(float(rgb[0]), float(rgb[1]), float(rgb[2]))
        c.setStrokeColorRGB(float(rgb[0]), float(rgb[1]), float(rgb[2]))
        for contour in region_contours(region_id, region):
            p = c.beginPath()
            x0, y0 = contour[0]
            p.moveTo(float(x0), float(h - y0))
            for x, y in contour[1:]:
                p.lineTo(float(x), float(h - y))
            p.close()
            c.drawPath(p, fill=1, stroke=0)
    c.showPage()

    # Page 2: production linework.
    c.setLineWidth(LINE_WIDTH_PT)
    c.setStrokeColorCMYK(*LINE_CMYK)
    c.setFillColorCMYK(*LINE_CMYK)
    for region in regions:
        for contour in region_contours(region_id, region):
            p = c.beginPath()
            x0, y0 = contour[0]
            p.moveTo(float(x0), float(h - y0))
            for x, y in contour[1:]:
                p.lineTo(float(x), float(h - y))
            p.close()
            c.drawPath(p, fill=0, stroke=1)
    for item in labels:
        code = color_codes.get(item.color_id, str(item.color_id + 1)) if color_codes else str(item.color_id + 1)
        c.setFont("Helvetica", item.font_pt)
        x = item.x - stringWidth(code, "Helvetica", item.font_pt) / 2.0
        c.drawString(float(x), float(h - item.y - item.font_pt / 3.0), code)
    c.showPage()

    # Page 3: editable palette swatches and text.
    row_h = max(18.0, h / max(len(palette_rgb) + 2, 8))
    y = h - row_h
    c.setFont("Helvetica", 9)
    for idx, rgb8 in enumerate(palette_rgb):
        rgb = rgb8.astype(float) / 255.0
        c.setFillColorRGB(float(rgb[0]), float(rgb[1]), float(rgb[2]))
        c.rect(24, y - 12, 48, 12, fill=1, stroke=0)
        c.setFillColorRGB(0, 0, 0)
        code = color_codes.get(idx, str(idx + 1)) if color_codes else str(idx + 1)
        c.drawString(82, y - 10, f"{code}   RGB {tuple(int(v) for v in rgb8)}")
        y -= row_h
        if y < 20:
            break
    c.save()
