"""Lab-space color quantization."""

from __future__ import annotations

import numpy as np
from sklearn.cluster import MiniBatchKMeans

from core.image.color import lab_to_rgb, rgb_to_lab
from core.models import PaletteColor


def quantize_lab(
    image_rgb: np.ndarray,
    target_colors: int,
    *,
    random_state: int = 42,
    max_samples: int = 100_000,
) -> tuple[np.ndarray, list[PaletteColor]]:
    """Quantize an RGB image in perceptual Lab space and return stable color IDs."""
    image = np.asarray(image_rgb)
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("输入必须是 H×W×3 RGB 图像")
    if image.dtype != np.uint8:
        raise ValueError("输入图像必须为 uint8")
    pixel_count = image.shape[0] * image.shape[1]
    if not 2 <= target_colors <= min(128, pixel_count):
        raise ValueError("目标色数必须在 2 到 128 之间，且不能超过像素数")

    lab_pixels = rgb_to_lab(image).reshape(-1, 3)
    rng = np.random.default_rng(random_state)
    if pixel_count > max_samples:
        training = lab_pixels[rng.choice(pixel_count, size=max_samples, replace=False)]
    else:
        training = lab_pixels
    estimator = MiniBatchKMeans(
        n_clusters=target_colors,
        random_state=random_state,
        batch_size=min(4096, len(training)),
        n_init=3,
        max_iter=100,
        reassignment_ratio=0.01,
    )
    estimator.fit(training)
    labels = estimator.predict(lab_pixels).astype(np.int32)
    centers = estimator.cluster_centers_.astype(np.float32)
    order = np.lexsort((centers[:, 2], centers[:, 1], -centers[:, 0]))
    old_to_new = np.empty(target_colors, dtype=np.int32)
    old_to_new[order] = np.arange(target_colors, dtype=np.int32)
    color_id_map = old_to_new[labels].reshape(image.shape[:2])
    sorted_centers = centers[order]
    palette_rgb = lab_to_rgb(sorted_centers)
    palette = [
        PaletteColor(
            color_id=index,
            rgb=tuple(int(channel) for channel in rgb),
            lab=tuple(float(channel) for channel in sorted_centers[index]),
            hex="#" + "".join(f"{int(channel):02X}" for channel in rgb),
        )
        for index, rgb in enumerate(palette_rgb)
    ]
    return color_id_map, palette
