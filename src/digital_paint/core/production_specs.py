from __future__ import annotations

from dataclasses import dataclass

LINE_WIDTH_PT = 0.1
LINE_CMYK = (40, 100, 100, 100)
LABEL_SIZES_PT = (4.2, 6.0, 8.0)


@dataclass(slots=True)
class SpecCheck:
    passed: bool
    message: str


@dataclass(slots=True)
class ProductionSpecValidation:
    line_width_ok: bool
    cmyk_ok: bool
    label_sizes_ok: bool
    messages: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return self.line_width_ok and self.cmyk_ok and self.label_sizes_ok


def validate_line_width(width_pt: float, tolerance: float = 1e-6) -> SpecCheck:
    ok = abs(float(width_pt) - LINE_WIDTH_PT) <= tolerance
    return SpecCheck(ok, f"line width={width_pt:.4f}pt target={LINE_WIDTH_PT:.4f}pt")


def validate_line_cmyk(cmyk: tuple[int, int, int, int]) -> SpecCheck:
    values = tuple(int(v) for v in cmyk)
    ok = values == LINE_CMYK
    return SpecCheck(ok, f"line CMYK={values} target={LINE_CMYK}")


def validate_label_size(size_pt: float, tolerance: float = 1e-6) -> SpecCheck:
    ok = any(abs(float(size_pt) - target) <= tolerance for target in LABEL_SIZES_PT)
    return SpecCheck(ok, f"label={size_pt:.2f}pt allowed={LABEL_SIZES_PT}")


def validate_production_spec(
    *,
    line_width_pt: float = LINE_WIDTH_PT,
    line_cmyk: tuple[int, int, int, int] = LINE_CMYK,
    label_sizes: list[float] | tuple[float, ...] = LABEL_SIZES_PT,
) -> ProductionSpecValidation:
    """Validate the project's fixed production parameters in one reusable call."""
    width = validate_line_width(line_width_pt)
    cmyk = validate_line_cmyk(line_cmyk)
    label_checks = [validate_label_size(size) for size in label_sizes]
    labels_ok = all(check.passed for check in label_checks)
    messages = (width.message, cmyk.message, *(check.message for check in label_checks))
    return ProductionSpecValidation(
        line_width_ok=width.passed,
        cmyk_ok=cmyk.passed,
        label_sizes_ok=labels_ok,
        messages=messages,
    )
