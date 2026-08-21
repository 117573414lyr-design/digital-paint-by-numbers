from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from sklearn.cluster import KMeans
from skimage.color import lab2rgb, rgb2lab


@dataclass(slots=True)
class QuantizationResult:
    image_rgb: np.ndarray
    palette_rgb: np.ndarray
    label_map: np.ndarray
    region_id: np.ndarray
    color_id: np.ndarray


def load_rgb_image(path: str | Path, max_side: int = 2200) -> np.ndarray:
    """Load an image as uint8 RGB, reducing very large inputs when requested."""
    image = Image.open(path).convert("RGB")
    if max(image.size) > max_side:
        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return np.asarray(image, dtype=np.uint8)


def quantize_lab(
    image_rgb: np.ndarray,
    colors: int,
    *,
    random_state: int = 42,
    sample_limit: int = 120_000,
) -> QuantizationResult:
    """Quantize an RGB image in CIE Lab space using deterministic KMeans.

    The production path fits on a bounded representative sample and predicts all
    pixels. A fixed random state plus one k-means++ initialization removes the
    previous five redundant full restarts while keeping deterministic output.
    """
    if image_rgb.ndim != 3 or image_rgb.shape[2] != 3:
        raise ValueError("image_rgb must have shape (H, W, 3)")
    if not 2 <= colors <= 256:
        raise ValueError("colors must be between 2 and 256")

    rgb_float = image_rgb.astype(np.float32) / 255.0
    lab = rgb2lab(rgb_float)
    pixels = lab.reshape(-1, 3)

    if len(pixels) > sample_limit:
        rng = np.random.default_rng(random_state)
        sample_idx = rng.choice(len(pixels), size=sample_limit, replace=False)
        fit_pixels = pixels[sample_idx]
    else:
        fit_pixels = pixels

    # Guard tiny or nearly-flat images without asking sklearn for impossible clusters.
    unique_count = len(np.unique(fit_pixels, axis=0))
    effective_colors = min(int(colors), int(unique_count))
    if effective_colors < 2:
        effective_colors = 1

    model = KMeans(
        n_clusters=effective_colors,
        random_state=random_state,
        n_init=1,
        max_iter=160,
        tol=1e-3,
        algorithm="lloyd",
    )
    model.fit(fit_pixels)

    labels = model.predict(pixels).reshape(image_rgb.shape[:2])
    palette_lab = model.cluster_centers_
    palette_rgb_float = lab2rgb(palette_lab[np.newaxis, :, :])[0]
    palette_rgb = np.clip(np.rint(palette_rgb_float * 255), 0, 255).astype(np.uint8)

    quantized = palette_rgb[labels]
    h, w = labels.shape
    region_id = np.arange(h * w, dtype=np.int32).reshape(h, w)
    color_id = labels.astype(np.int32, copy=False)

    return QuantizationResult(
        image_rgb=quantized,
        palette_rgb=palette_rgb,
        label_map=labels.astype(np.int32, copy=False),
        region_id=region_id,
        color_id=color_id,
    )


def save_rgb_png(image_rgb: np.ndarray, path: str | Path) -> None:
    Image.fromarray(image_rgb.astype(np.uint8), mode="RGB").save(path, format="PNG")
