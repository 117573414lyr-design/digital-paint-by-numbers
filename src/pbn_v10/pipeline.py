from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage

from .palette import load_color_library, match_palette_to_library


@dataclass(slots=True)
class V10Config:
    colors: int = 24
    min_region_area: int = 120
    smooth_epsilon: float = 1.2
    smooth_iterations: int = 2
    label_min_radius: float = 5.0
    line_width_pt: float = 0.1
    line_cmyk: tuple[int, int, int, int] = (40, 100, 100, 100)
    font_sizes_pt: tuple[float, float, float] = (4.2, 6.0, 8.0)
    color_library: Path | None = None


@dataclass(slots=True)
class Region:
    color_id: int
    region_index: int
    area: int
    contour: np.ndarray
    label_x: float
    label_y: float
    label_radius: float


@dataclass(slots=True)
class PipelineResult:
    rgb: np.ndarray
    indexed: np.ndarray
    palette: np.ndarray
    palette_numbers: list[str]
    regions: list[Region]


class PaintByNumbersPipeline:
    def __init__(self, config: V10Config | None = None) -> None:
        self.config = config or V10Config()

    def run(self, image_path: str | Path) -> PipelineResult:
        rgb = np.asarray(Image.open(image_path).convert("RGB"))
        indexed, palette = self._quantize(rgb, self.config.colors)
        indexed = self._merge_small_regions(indexed, palette)
        indexed = self._merge_unnumberable(indexed, palette)
        palette_numbers = [str(i + 1) for i in range(len(palette))]
        if self.config.color_library:
            library = load_color_library(self.config.color_library)
            palette, palette_numbers = match_palette_to_library(palette, library)
        regions = self._extract_regions(indexed)
        return PipelineResult(rgb, indexed, palette, palette_numbers, regions)

    @staticmethod
    def _quantize(rgb: np.ndarray, colors: int) -> tuple[np.ndarray, np.ndarray]:
        pixels = rgb.reshape(-1, 3).astype(np.float32)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 60, 0.35)
        _, labels, centers = cv2.kmeans(pixels, colors, None, criteria, 5, cv2.KMEANS_PP_CENTERS)
        return labels.reshape(rgb.shape[:2]).astype(np.int32), np.clip(np.rint(centers), 0, 255).astype(np.uint8)

    def _best_neighbor(self, out: np.ndarray, component: np.ndarray, color_id: int, palette: np.ndarray) -> int | None:
        border = ndimage.binary_dilation(component, iterations=1) & ~component
        neighbors = out[border]
        neighbors = neighbors[neighbors != color_id]
        if neighbors.size == 0:
            return None
        values, counts = np.unique(neighbors, return_counts=True)
        src = palette[color_id].astype(float)
        dist = np.linalg.norm(palette[values].astype(float) - src, axis=1)
        score = counts / (1.0 + dist)
        return int(values[np.argmax(score)])

    def _merge_small_regions(self, indexed: np.ndarray, palette: np.ndarray) -> np.ndarray:
        out = indexed.copy()
        for _ in range(8):
            changed = False
            for color_id in np.unique(out):
                labels, count = ndimage.label(out == color_id)
                for component_id in range(1, count + 1):
                    component = labels == component_id
                    if int(component.sum()) >= self.config.min_region_area:
                        continue
                    target = self._best_neighbor(out, component, int(color_id), palette)
                    if target is not None:
                        out[component] = target
                        changed = True
            if not changed:
                break
        return out

    def _merge_unnumberable(self, indexed: np.ndarray, palette: np.ndarray) -> np.ndarray:
        out = indexed.copy()
        h, w = out.shape
        for _ in range(6):
            changed = False
            for color_id in np.unique(out):
                labels, count = ndimage.label(out == color_id)
                for component_id in range(1, count + 1):
                    component = labels == component_id
                    mask = component.astype(np.uint8) * 255
                    distance = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
                    if float(distance.max()) >= self.config.label_min_radius:
                        continue
                    target = self._best_neighbor(out, component, int(color_id), palette)
                    if target is not None:
                        out[component] = target
                        changed = True
            if not changed:
                break
        return out

    def _extract_regions(self, indexed: np.ndarray) -> list[Region]:
        regions: list[Region] = []
        h, w = indexed.shape
        for color_id in np.unique(indexed):
            mask = (indexed == color_id).astype(np.uint8) * 255
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            region_index = 0
            for contour in contours:
                area = int(round(abs(cv2.contourArea(contour))))
                if area < self.config.min_region_area:
                    continue
                region_index += 1
                contour = cv2.approxPolyDP(contour, self.config.smooth_epsilon, True)
                filled = np.zeros((h, w), dtype=np.uint8)
                cv2.drawContours(filled, [contour], -1, 255, cv2.FILLED)
                distance = cv2.distanceTransform(filled, cv2.DIST_L2, 5)
                _, maxv, _, maxloc = cv2.minMaxLoc(distance)
                regions.append(Region(int(color_id), region_index, area, contour, float(maxloc[0]), float(maxloc[1]), float(maxv)))
        return regions

    @staticmethod
    def render_effect(result: PipelineResult) -> Image.Image:
        return Image.fromarray(result.palette[result.indexed].astype(np.uint8), "RGB")

    @staticmethod
    def iter_region_ids(regions: Iterable[Region]) -> Iterable[str]:
        for r in regions:
            yield f"c{r.color_id + 1:02d}-r{r.region_index:03d}"
