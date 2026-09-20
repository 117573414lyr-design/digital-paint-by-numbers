from pathlib import Path

import numpy as np
from PIL import Image

from core.export.png import export_png
from core.pipeline import PaintByNumbersPipeline, PipelineConfig


def sample_image() -> np.ndarray:
    y, x = np.mgrid[:36, :48]
    return np.stack(((x * 5) % 256, (y * 7) % 256, ((x + y) * 3) % 256), axis=-1).astype(np.uint8)


def test_pipeline_preserves_complete_region_color_mapping() -> None:
    source = sample_image()
    result = PaintByNumbersPipeline(
        PipelineConfig(target_colors=6, min_region_area=4, max_samples=10_000)
    ).run(source)
    result.validate()
    assert result.rendered_rgb.shape == source.shape
    assert len(result.palette) == 6
    assert set(np.unique(result.region_id_map)) == {r.region_id for r in result.regions}
    assert np.all(result.region_id_map >= 0)


def test_pipeline_is_reproducible() -> None:
    source = sample_image()
    config = PipelineConfig(target_colors=5, min_region_area=3, random_state=7)
    first = PaintByNumbersPipeline(config).run(source)
    second = PaintByNumbersPipeline(config).run(source)
    np.testing.assert_array_equal(first.color_id_map, second.color_id_map)
    assert first.palette == second.palette


def test_png_export_round_trip(tmp_path: Path) -> None:
    source = sample_image()
    path = export_png(source, tmp_path / "result")
    with Image.open(path) as exported:
        np.testing.assert_array_equal(np.asarray(exported.convert("RGB")), source)
