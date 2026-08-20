from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Callable, TypeVar

import numpy as np

T = TypeVar("T")


@dataclass(slots=True)
class StageTiming:
    name: str
    seconds: float


@dataclass(slots=True)
class PerformanceReport:
    width: int
    height: int
    megapixels: float
    stages: list[StageTiming] = field(default_factory=list)

    @property
    def total_seconds(self) -> float:
        return sum(stage.seconds for stage in self.stages)

    def as_dict(self) -> dict[str, object]:
        return {
            "width": self.width,
            "height": self.height,
            "megapixels": round(self.megapixels, 3),
            "total_seconds": round(self.total_seconds, 4),
            "stages": [
                {"name": stage.name, "seconds": round(stage.seconds, 4)}
                for stage in self.stages
            ],
        }


class StageProfiler:
    """Low-overhead stage profiler used by production and benchmark paths."""

    def __init__(self, image_rgb: np.ndarray) -> None:
        h, w = image_rgb.shape[:2]
        self.report = PerformanceReport(width=w, height=h, megapixels=(w * h) / 1_000_000.0)

    def run(self, name: str, func: Callable[..., T], *args, **kwargs) -> T:
        start = perf_counter()
        result = func(*args, **kwargs)
        self.report.stages.append(StageTiming(name=name, seconds=perf_counter() - start))
        return result


def recommended_sample_limit(image_rgb: np.ndarray, colors: int) -> int:
    """Choose a bounded KMeans fit sample size without scaling linearly with image size."""
    pixels = int(image_rgb.shape[0] * image_rgb.shape[1])
    # Enough samples to represent each cluster while preventing huge images from exploding fit cost.
    target = max(30_000, colors * 3_000)
    return min(pixels, min(target, 180_000))


def estimated_working_set_mb(image_rgb: np.ndarray) -> float:
    """Conservative working-set estimate for RGB + Lab + label/region arrays."""
    pixels = int(image_rgb.shape[0] * image_rgb.shape[1])
    # RGB uint8 3B + Lab float32 12B + several int32 maps and temporary buffers.
    return pixels * 40 / (1024 * 1024)


def should_downscale_for_interactive_preview(
    image_rgb: np.ndarray,
    *,
    max_megapixels: float = 12.0,
) -> bool:
    pixels = image_rgb.shape[0] * image_rgb.shape[1]
    return pixels > max_megapixels * 1_000_000
