import numpy as np

from digital_paint.core.boundaries import shared_boundary_segments
from digital_paint.core.palette import PaletteColor, match_palette
from digital_paint.core.pipeline import build_production_result
from digital_paint.core.regions import build_regions, merge_small_regions


def test_regions_are_connected_and_cover_every_pixel():
    colors = np.array([
        [0, 0, 1, 1],
        [0, 0, 1, 1],
        [2, 2, 1, 1],
        [2, 2, 1, 1],
    ], dtype=np.int32)
    result = build_regions(colors)
    assert np.all(result.region_id >= 0)
    assert len(result.regions) == 3
    for rid, neighbours in result.adjacency.items():
        for neighbour in neighbours:
            assert rid in result.adjacency[neighbour]


def test_small_fragment_merges_into_touching_region():
    colors = np.zeros((7, 7), dtype=np.int32)
    colors[3, 3] = 1
    palette = np.array([[100, 100, 100], [110, 110, 110]], dtype=np.uint8)
    merged = merge_small_regions(colors, palette, min_area=2)
    assert int(merged[3, 3]) == 0


def test_shared_boundary_is_emitted_once():
    regions = np.array([[0, 1], [0, 1]], dtype=np.int32)
    segments = shared_boundary_segments(regions)
    internal = [s for s in segments if s[0] == 1.0 and s[2] == 1.0]
    assert len(internal) == 2
    assert len(set(internal)) == len(internal)


def test_custom_palette_matches_lab_nearest_color():
    source = np.array([[250, 10, 10], [10, 10, 250]], dtype=np.uint8)
    target = [PaletteColor("R1", (255, 0, 0)), PaletteColor("B1", (0, 0, 255))]
    matches = match_palette(source, target)
    assert [m.code for m in matches] == ["R1", "B1"]


def test_v6_pipeline_produces_qc_ready_result():
    image = np.zeros((24, 24, 3), dtype=np.uint8)
    image[:, :12] = [230, 40, 40]
    image[:, 12:] = [40, 60, 230]
    result = build_production_result(image, 2, min_region_area=4)
    assert result.effect_rgb.shape == image.shape
    assert result.region_id.shape == image.shape[:2]
    assert len(result.regions.regions) >= 2
    assert len(result.labels) == len(result.regions.regions)
    assert result.qc.counts()["FAIL"] == 0
