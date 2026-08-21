from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import importlib.util
import json
import math
from typing import Iterable


@dataclass(frozen=True, slots=True)
class ReferenceProfile:
    sample_id: str
    category: str
    megapixels: float
    target_colors: int
    min_region_area: int
    detail_score: float
    edge_density: float
    notes: str = ""


@dataclass(frozen=True, slots=True)
class RecommendedParameters:
    target_colors: int
    min_region_area: int
    source_sample_ids: tuple[str, ...]
    confidence: float


class ReferenceLibrary:
    """Small deterministic reference-profile library for controlled learning.

    Profiles represent approved designer examples. Recommendations are nearest-
    neighbour parameter hints only; they never mutate production pixels/paths.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[ReferenceProfile]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return [ReferenceProfile(**item) for item in payload]

    def save(self, profiles: Iterable[ReferenceProfile]) -> None:
        data = [asdict(item) for item in profiles]
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def add(self, profile: ReferenceProfile) -> None:
        profiles = [item for item in self.load() if item.sample_id != profile.sample_id]
        profiles.append(profile)
        self.save(profiles)

    def recommend(
        self,
        *,
        megapixels: float,
        detail_score: float,
        edge_density: float,
        category: str = "",
        neighbours: int = 3,
    ) -> RecommendedParameters | None:
        profiles = self.load()
        if not profiles:
            return None
        ranked: list[tuple[float, ReferenceProfile]] = []
        for profile in profiles:
            category_penalty = 0.0 if not category or profile.category == category else 0.6
            distance = math.sqrt(
                ((profile.megapixels - megapixels) / max(megapixels, 1.0)) ** 2
                + (profile.detail_score - detail_score) ** 2
                + (profile.edge_density - edge_density) ** 2
                + category_penalty**2
            )
            ranked.append((distance, profile))
        selected = sorted(ranked, key=lambda item: item[0])[: max(1, neighbours)]
        weights = [1.0 / max(distance, 0.05) for distance, _ in selected]
        total = sum(weights)
        target_colors = round(sum(w * p.target_colors for w, (_, p) in zip(weights, selected, strict=False)) / total)
        min_area = round(sum(w * p.min_region_area for w, (_, p) in zip(weights, selected, strict=False)) / total)
        mean_distance = sum(distance for distance, _ in selected) / len(selected)
        confidence = max(0.0, min(1.0, 1.0 / (1.0 + mean_distance)))
        return RecommendedParameters(
            target_colors=max(2, min(256, int(target_colors))),
            min_region_area=max(1, int(min_area)),
            source_sample_ids=tuple(profile.sample_id for _, profile in selected),
            confidence=confidence,
        )


def available_acceleration_providers() -> tuple[str, ...]:
    """Report optional local acceleration without making it a hard dependency."""
    providers: list[str] = ["CPU"]
    if importlib.util.find_spec("onnxruntime") is not None:
        providers.append("ONNX Runtime")
    if importlib.util.find_spec("onnxruntime_directml") is not None:
        providers.append("DirectML")
    if importlib.util.find_spec("cupy") is not None:
        providers.append("CUDA/CuPy")
    return tuple(providers)
