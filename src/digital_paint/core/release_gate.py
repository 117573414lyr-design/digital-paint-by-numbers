from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass(slots=True)
class GateCheck:
    name: str
    passed: bool
    detail: str


@dataclass(slots=True)
class ReleaseGateReport:
    target: str
    checks: list[GateCheck] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(check.passed for check in self.checks)

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [f"{self.target}: {status}"]
        lines.extend(f"- {'PASS' if c.passed else 'FAIL'} {c.name}: {c.detail}" for c in self.checks)
        return "\n".join(lines)


def check_required_files(root: str | Path, required: Iterable[str]) -> GateCheck:
    root = Path(root)
    missing = [name for name in required if not (root / name).exists()]
    return GateCheck(
        name="required_files",
        passed=not missing,
        detail="all present" if not missing else f"missing: {', '.join(missing)}",
    )


def v100_release_gate(
    *,
    exe_exists: bool,
    offline_launch_verified: bool,
    real_sample_regression_passed: bool,
    vector_pdf_verified: bool,
    qc_passed: bool,
    gui_nonblocking_verified: bool,
    large_image_benchmarks_passed: bool,
    palette_verified: bool,
) -> ReleaseGateReport:
    """Return the hard release gate for the V100 production-candidate label.

    This function intentionally requires external verification flags. Merely
    implementing code is not sufficient to claim V100 production readiness.
    """
    values = [
        ("windows_exe", exe_exists, "Windows EXE artifact exists"),
        ("offline_launch", offline_launch_verified, "EXE launches without network dependency"),
        ("real_sample_regression", real_sample_regression_passed, "approved production references pass"),
        ("vector_pdf", vector_pdf_verified, "PDF contains editable vector paths/text"),
        ("automatic_qc", qc_passed, "blocking QC checks pass"),
        ("gui_nonblocking", gui_nonblocking_verified, "heavy work stays off GUI thread"),
        ("large_image_benchmarks", large_image_benchmarks_passed, "12/24/48MP performance gates pass"),
        ("custom_palette", palette_verified, "project color library mapping verified"),
    ]
    return ReleaseGateReport("V100", [GateCheck(name, passed, detail) for name, passed, detail in values])
