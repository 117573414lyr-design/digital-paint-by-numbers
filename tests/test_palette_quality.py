import numpy as np

from digital_paint.core.palette import PaletteColor
from digital_paint.core.palette_quality import (
    classify_sensitive_sources,
    deduplicate_palette,
    match_palette_ciede2000,
    palette_quality_report,
    validate_palette,
)


def test_validate_palette_detects_duplicate_codes_and_rgb():
    colors = [
        PaletteColor("A1", (255, 0, 0)),
        PaletteColor("A1", (0, 255, 0)),
        PaletteColor("B1", (255, 0, 0)),
    ]
    issues = validate_palette(colors)
    codes = {issue.code for issue in issues}
    assert "DUPLICATE_CODE" in codes
    assert "DUPLICATE_RGB" in codes


def test_deduplicate_palette_removes_exact_duplicates_only():
    colors = [
        PaletteColor("A1", (10, 20, 30)),
        PaletteColor("A1", (10, 20, 30)),
        PaletteColor("B1", (10, 20, 30)),
    ]
    result = deduplicate_palette(colors)
    assert len(result) == 2
    assert [c.code for c in result] == ["A1", "B1"]


def test_ciede2000_matching_prefers_near_colors():
    source = np.asarray([[250, 5, 5], [5, 5, 245]], dtype=np.uint8)
    target = [
        PaletteColor("RED", (255, 0, 0)),
        PaletteColor("BLUE", (0, 0, 255)),
    ]
    matches = match_palette_ciede2000(source, target)
    assert [m.code for m in matches] == ["RED", "BLUE"]
    assert all(m.delta_e76 < 5 for m in matches)


def test_sensitive_source_classifier_marks_dark_and_chromatic_colors():
    source = np.asarray([[4, 4, 4], [128, 128, 128], [255, 0, 0]], dtype=np.uint8)
    protected = classify_sensitive_sources(source)
    assert 0 in protected
    assert 2 in protected
    assert 1 not in protected


def test_palette_quality_reports_collisions_and_missing_matches():
    source = np.asarray([[255, 0, 0], [250, 0, 0]], dtype=np.uint8)
    target = [PaletteColor("R", (255, 0, 0))]
    matches = match_palette_ciede2000(source, target)
    report = palette_quality_report(target, matches, source_count=3)
    assert "R" in report.collision_codes
    assert report.missing_source_indices == [2]
    assert report.ok is False
