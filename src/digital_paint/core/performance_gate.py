from __future__ import annotations

from dataclasses import dataclass

from digital_paint.core.performance import PerformanceReport
from digital_paint.core.runtime import MemoryPlan


@dataclass(frozen=True, slots=True)
class PerformanceGateResult:
    status: str
    issues: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    @property
    def reasons(self) -> tuple[str, ...]:
        """Backward/GUI-friendly alias for issue messages."""
        return self.issues


def evaluate_performance_gate(
    report: PerformanceReport,
    memory_plan: MemoryPlan,
    *,
    max_seconds_per_mp: float = 8.0,
    max_estimated_memory_mb: float = 4096.0,
) -> PerformanceGateResult:
    issues: list[str] = []
    mp = max(report.megapixels, 0.001)
    seconds_per_mp = report.total_seconds / mp
    if seconds_per_mp > max_seconds_per_mp:
        issues.append(
            f"processing rate {seconds_per_mp:.2f}s/MP exceeds {max_seconds_per_mp:.2f}s/MP"
        )
    if memory_plan.estimated_mb > max_estimated_memory_mb and not memory_plan.use_tiles:
        issues.append(
            f"estimated memory {memory_plan.estimated_mb:.0f}MB requires tiled mode"
        )
    status = "PASS" if not issues else "WARN"
    return PerformanceGateResult(status=status, issues=tuple(issues))


def benchmark_targets() -> dict[str, int]:
    """Return deterministic megapixel targets used by CI/manual benchmark runs."""
    return {"12MP": 12_000_000, "24MP": 24_000_000, "48MP": 48_000_000}
