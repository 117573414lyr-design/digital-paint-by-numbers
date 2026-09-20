import numpy as np

from core.image.color import lab_to_rgb, rgb_to_lab


def test_rgb_lab_round_trip_primary_and_neutral_colors() -> None:
    rgb = np.array(
        [[0, 0, 0], [255, 255, 255], [255, 0, 0], [0, 255, 0], [0, 0, 255], [127, 80, 220]],
        dtype=np.uint8,
    )
    restored = lab_to_rgb(rgb_to_lab(rgb))
    assert np.max(np.abs(restored.astype(int) - rgb.astype(int))) <= 1


def test_known_white_lab_value() -> None:
    lab = rgb_to_lab(np.array([255, 255, 255], dtype=np.uint8))
    np.testing.assert_allclose(lab, [100, 0, 0], atol=2e-3)
