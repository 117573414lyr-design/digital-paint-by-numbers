"""Vectorized sRGB and CIE Lab conversions using D65 white."""

from __future__ import annotations

import numpy as np

_D65 = np.array([0.95047, 1.0, 1.08883], dtype=np.float64)
_RGB_TO_XYZ = np.array(
    [
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ],
    dtype=np.float64,
)
_XYZ_TO_RGB = np.linalg.inv(_RGB_TO_XYZ)


def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """Convert uint8-like sRGB values to CIE Lab (D65)."""
    values = np.asarray(rgb, dtype=np.float64) / 255.0
    linear = np.where(values <= 0.04045, values / 12.92, ((values + 0.055) / 1.055) ** 2.4)
    xyz = linear @ _RGB_TO_XYZ.T
    scaled = xyz / _D65
    delta = 6 / 29
    f = np.where(scaled > delta**3, np.cbrt(scaled), scaled / (3 * delta**2) + 4 / 29)
    return np.stack(
        (116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])),
        axis=-1,
    ).astype(np.float32)


def lab_to_rgb(lab: np.ndarray) -> np.ndarray:
    """Convert CIE Lab (D65) values to clipped uint8 sRGB."""
    values = np.asarray(lab, dtype=np.float64)
    fy = (values[..., 0] + 16) / 116
    f = np.stack((fy + values[..., 1] / 500, fy, fy - values[..., 2] / 200), axis=-1)
    delta = 6 / 29
    scaled = np.where(f > delta, f**3, 3 * delta**2 * (f - 4 / 29))
    linear = (scaled * _D65) @ _XYZ_TO_RGB.T
    srgb = np.where(
        linear <= 0.0031308,
        12.92 * linear,
        1.055 * np.maximum(linear, 0) ** (1 / 2.4) - 0.055,
    )
    return np.rint(np.clip(srgb, 0, 1) * 255).astype(np.uint8)
