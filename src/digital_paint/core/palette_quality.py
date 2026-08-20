from __future__ import annotations

from dataclasses import dataclass
from collections import Counter

import numpy as np
from skimage.color import deltaE_ciede2000, rgb2lab

from digital_paint.core.palette import PaletteColor, PaletteMatch


@dataclass(frozen=True, slots=True)
class PaletteIssue:
    severity: str
    code: str
    message: str


@dataclass(slots=True)
class PaletteQualityReport:
    issues: list[PaletteIssue]
    duplicate_codes: list[str]
    duplicate_rgb: list[tuple[int, int, int]]
    collision_codes: dict[str, list[int]]
    missing_source_indices: list[int]
    max_delta_e00: float
    mean_delta_e00: float

    @property
    def ok(self) -> bool:
        return not any(i.severity == "FAIL" for i in self.issues)


def validate_palette(colors: list[PaletteColor]) -> list[PaletteIssue]:
    """Validate user color-library integrity before production matching."""
    issues: list[PaletteIssue] = []
    if not colors:
        return [PaletteIssue("FAIL", "EMPTY_PALETTE", "色库为空")]

    code_counts = Counter(c.code.strip() for c in colors)
    rgb_counts = Counter(c.rgb for c in colors)
    for code, count in sorted(code_counts.items()):
        if not code:
            issues.append(PaletteIssue("FAIL", "EMPTY_CODE", "色库存在空色号"))
        elif count > 1:
            issues.append(PaletteIssue("FAIL", "DUPLICATE_CODE", f"色号 {code} 重复 {count} 次"))
    for rgb, count in rgb_counts.items():
        if count > 1:
            issues.append(PaletteIssue("WARN", "DUPLICATE_RGB", f"RGB {rgb} 被 {count} 个色号重复使用"))
    return issues


def deduplicate_palette(colors: list[PaletteColor]) -> list[PaletteColor]:
    """Keep the first valid occurrence of each code+RGB pair without silently merging different codes."""
    seen: set[tuple[str, tuple[int, int, int]]] = set()
    result: list[PaletteColor] = []
    for color in colors:
        key = (color.code.strip(), color.rgb)
        if key in seen:
            continue
        seen.add(key)
        result.append(color)
    return result


def match_palette_ciede2000(
    source_rgb: np.ndarray,
    target: list[PaletteColor],
    *,
    protected_source_indices: set[int] | None = None,
    collision_penalty: float = 2.0,
) -> list[PaletteMatch]:
    """Match colors using CIEDE2000 with optional anti-collision protection.

    Important source colors can be marked protected. For protected colors, a target
    already used by another protected source receives a penalty so distinctive
    subject colors are less likely to collapse to one formal color code.
    """
    if source_rgb.ndim != 2 or source_rgb.shape[1] != 3:
        raise ValueError("source_rgb must have shape (N, 3)")
    if not target:
        raise ValueError("target palette is empty")

    src_lab = rgb2lab((source_rgb.astype(np.float32) / 255.0)[None, :, :])[0]
    dst_rgb = np.asarray([c.rgb for c in target], dtype=np.float32)
    dst_lab = rgb2lab((dst_rgb / 255.0)[None, :, :])[0]
    distances = deltaE_ciede2000(src_lab[:, None, :], dst_lab[None, :, :])

    protected = protected_source_indices or set()
    used_protected: set[int] = set()
    matches: list[PaletteMatch] = []
    for source_index in range(len(source_rgb)):
        row = distances[source_index].astype(np.float64, copy=True)
        if source_index in protected and used_protected:
            for target_index in used_protected:
                row[target_index] += collision_penalty
        best = int(np.argmin(row))
        if source_index in protected:
            used_protected.add(best)
        matches.append(
            PaletteMatch(
                source_index=source_index,
                code=target[best].code,
                rgb=target[best].rgb,
                delta_e76=float(distances[source_index, best]),
            )
        )
    return matches


def classify_sensitive_sources(source_rgb: np.ndarray) -> set[int]:
    """Return conservative color indices worth protecting from accidental collapse.

    This is deliberately only a color-space heuristic. Future semantic detectors can
    add eyes, mouths, text, faces and other subject-specific regions without changing
    the matching contract.
    """
    rgb = source_rgb.astype(np.float32) / 255.0
    lab = rgb2lab(rgb[None, :, :])[0]
    protected: set[int] = set()
    for idx, (l, a, b) in enumerate(lab):
        chroma = float(np.hypot(a, b))
        # Preserve very dark accents, bright highlights, and strongly chromatic colors.
        if l < 18.0 or l > 90.0 or chroma > 42.0:
            protected.add(idx)
    return protected


def palette_quality_report(
    colors: list[PaletteColor],
    matches: list[PaletteMatch],
    source_count: int,
    *,
    warn_delta_e00: float = 8.0,
    fail_delta_e00: float = 16.0,
) -> PaletteQualityReport:
    """Build production diagnostics for palette integrity, gaps and mapping collisions."""
    issues = list(validate_palette(colors))
    codes = Counter(c.code.strip() for c in colors)
    rgbs = Counter(c.rgb for c in colors)
    duplicate_codes = sorted([code for code, count in codes.items() if count > 1])
    duplicate_rgb = [rgb for rgb, count in rgbs.items() if count > 1]

    by_code: dict[str, list[int]] = {}
    for match in matches:
        by_code.setdefault(match.code, []).append(match.source_index)
    collision_codes = {code: indexes for code, indexes in by_code.items() if len(indexes) > 1}
    if collision_codes:
        issues.append(PaletteIssue("WARN", "COLOR_COLLISIONS", f"{len(collision_codes)} 个正式色号被多个聚类色共享"))

    seen_sources = {m.source_index for m in matches}
    missing = sorted(set(range(source_count)) - seen_sources)
    if missing:
        issues.append(PaletteIssue("FAIL", "MISSING_MATCH", f"存在 {len(missing)} 个聚类色未匹配到正式色号"))

    errors = np.asarray([m.delta_e76 for m in matches], dtype=float)
    max_error = float(errors.max(initial=0.0))
    mean_error = float(errors.mean()) if errors.size else 0.0
    if max_error >= fail_delta_e00:
        issues.append(PaletteIssue("FAIL", "COLOR_DISTANCE_HIGH", f"最大 CIEDE2000 色差 {max_error:.2f} 超过 {fail_delta_e00:.2f}"))
    elif max_error >= warn_delta_e00:
        issues.append(PaletteIssue("WARN", "COLOR_DISTANCE_WARN", f"最大 CIEDE2000 色差 {max_error:.2f}"))

    return PaletteQualityReport(
        issues=issues,
        duplicate_codes=duplicate_codes,
        duplicate_rgb=duplicate_rgb,
        collision_codes=collision_codes,
        missing_source_indices=missing,
        max_delta_e00=max_error,
        mean_delta_e00=mean_error,
    )
