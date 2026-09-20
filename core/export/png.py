"""Lossless PNG export."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def export_png(image_rgb: np.ndarray, path: str | Path) -> Path:
    """Write an RGB uint8 image to a PNG path, adding the suffix when absent."""
    output = Path(path)
    if output.suffix.lower() != ".png":
        output = output.with_suffix(".png")
    image = np.asarray(image_rgb)
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("只能导出 uint8 RGB 图像")
    output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(image, mode="RGB").save(output, format="PNG", optimize=True)
    return output
