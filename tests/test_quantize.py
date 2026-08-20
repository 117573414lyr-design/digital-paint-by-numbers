import numpy as np
import pytest

from digital_paint.core.quantize import quantize_lab


def test_quantize_preserves_shape_and_ids():
    image = np.zeros((8, 10, 3), dtype=np.uint8)
    image[:, :5] = [255, 0, 0]
    image[:, 5:] = [0, 0, 255]

    result = quantize_lab(image, 2, sample_limit=1000)

    assert result.image_rgb.shape == image.shape
    assert result.label_map.shape == image.shape[:2]
    assert result.region_id.shape == image.shape[:2]
    assert result.color_id.shape == image.shape[:2]
    assert result.palette_rgb.shape == (2, 3)
    assert len(np.unique(result.color_id)) == 2


def test_quantize_rejects_invalid_color_count():
    image = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        quantize_lab(image, 1)


def test_quantize_rejects_non_rgb_array():
    image = np.zeros((4, 4), dtype=np.uint8)
    with pytest.raises(ValueError):
        quantize_lab(image, 2)
