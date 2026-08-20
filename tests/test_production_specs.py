from digital_paint.core.production_specs import (
    validate_label_size,
    validate_line_cmyk,
    validate_line_width,
)


def test_line_width_exact_target():
    assert validate_line_width(0.1).passed
    assert not validate_line_width(0.12).passed


def test_line_cmyk_exact_target():
    assert validate_line_cmyk((40, 100, 100, 100)).passed
    assert not validate_line_cmyk((0, 0, 0, 100)).passed


def test_label_sizes_are_project_standard():
    for value in (4.2, 6.0, 8.0):
        assert validate_label_size(value).passed
    assert not validate_label_size(5.0).passed
