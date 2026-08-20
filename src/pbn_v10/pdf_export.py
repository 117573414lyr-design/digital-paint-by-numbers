from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .geometry import shared_boundary_paths
from .pipeline import PipelineResult, V10Config


def _fit(width: float, height: float, box_w: float, box_h: float) -> tuple[float, float, float]:
    scale = min(box_w / width, box_h / height)
    return width * scale, height * scale, scale


def export_production_pdf(result: PipelineResult, output: Path, config: V10Config) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    page_w, page_h = landscape(A4)
    c = canvas.Canvas(str(output), pagesize=(page_w, page_h))
    margin = 28
    h, w = result.indexed.shape

    # Page 1: effect image.
    effect = Image.fromarray(result.palette[result.indexed].astype("uint8"), "RGB")
    buf = BytesIO()
    effect.save(buf, format="PNG")
    buf.seek(0)
    draw_w, draw_h, _ = _fit(w, h, page_w - 2 * margin, page_h - 2 * margin)
    c.drawImage(ImageReader(buf), (page_w - draw_w) / 2, (page_h - draw_h) / 2, draw_w, draw_h)
    c.showPage()

    # Page 2: vector line art + numbers.
    draw_w, draw_h, scale = _fit(w, h, page_w - 2 * margin, page_h - 2 * margin)
    ox, oy = (page_w - draw_w) / 2, (page_h - draw_h) / 2
    c.setLineWidth(config.line_width_pt)
    c.setStrokeColorCMYK(*(v / 100 for v in config.line_cmyk))
    for path in shared_boundary_paths(result.indexed, config.smooth_iterations):
        if len(path) < 2:
            continue
        p = c.beginPath()
        p.moveTo(ox + path[0][0] * scale, oy + (h - path[0][1]) * scale)
        for x, y in path[1:]:
            p.lineTo(ox + x * scale, oy + (h - y) * scale)
        c.drawPath(p, stroke=1, fill=0)
    c.setFillColorCMYK(*(v / 100 for v in config.line_cmyk))
    for r in result.regions:
        size = config.font_sizes_pt[0] if r.label_radius < 10 else config.font_sizes_pt[1] if r.label_radius < 18 else config.font_sizes_pt[2]
        c.setFont("Helvetica", size)
        number = result.palette_numbers[r.color_id]
        c.drawCentredString(ox + r.label_x * scale, oy + (h - r.label_y) * scale - size / 3, number)
    c.showPage()

    # Page 3: palette card.
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, page_h - margin - 10, "Color Palette")
    sw, sh = 80, 34
    cols = 6
    start_y = page_h - margin - 55
    for i, rgb in enumerate(result.palette):
        row, col = divmod(i, cols)
        x = margin + col * 130
        y = start_y - row * 52
        r, g, b = [int(v) for v in rgb]
        c.setFillColorRGB(r / 255, g / 255, b / 255)
        c.rect(x, y, sw, sh, fill=1, stroke=1)
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica", 9)
        c.drawString(x + sw + 6, y + 12, str(result.palette_numbers[i]))
    c.save()
