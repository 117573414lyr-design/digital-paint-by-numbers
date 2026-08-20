from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage


@dataclass(slots=True)
class V10Config:
    colors: int = 24
    min_region_area: int = 120
    smooth_epsilon: float = 1.2
    label_min_radius: float = 5.0
    line_width_pt: float = 0.1
    line_cmyk: tuple[int, int, int, int] = (40, 100, 100, 100)
    font_sizes_pt: tuple[float, float, float] = (4.2, 6.0, 8.0)


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
    regions: list[Region]


class PaintByNumbersPipeline:
    """V10 production core.

    Invariants:
    - one integer color id per pixel;
    - connected regions are closed and uniquely owned;
    - tiny regions are merged before vector tracing;
    - numbering points are chosen from an interior distance transform.
    """

    def __init__(self, config: V10Config | None = None) -> None:
        self.config = config or V10Config()

    def run(self, image_path: str | Path) -> PipelineResult:
        rgb = np.asarray(Image.open(image_path).convert("RGB"))
        indexed, palette = self._quantize(rgb, self.config.colors)
        indexed = self._merge_small_regions(indexed)
        regions = self._extract_regions(indexed)
        return PipelineResult(rgb=rgb, indexed=indexed, palette=palette, regions=regions)

    @staticmethod
    def _quantize(rgb: np.ndarray, colors: int) -> tuple[np.ndarray, np.ndarray]:
        pixels = rgb.reshape(-1, 3).astype(np.float32)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 60, 0.35)
        _compactness, labels, centers = cv2.kmeans(
            pixels,
            colors,
            None,
            criteria,
            5,
            cv2.KMEANS_PP_CENTERS,
        )
        indexed = labels.reshape(rgb.shape[:2]).astype(np.int32)
        palette = np.clip(np.rint(centers), 0, 255).astype(np.uint8)
        return indexed, palette

    def _merge_small_regions(self, indexed: np.ndarray) -> np.ndarray:
        out = indexed.copy()
        changed = True
        rounds = 0
        while changed and rounds < 8:
            changed = False
            rounds += 1
            for color_id in np.unique(out):
                mask = out == color_id
                labels, count = ndimage.label(mask)
                for component_id in range(1, count + 1):
                    component = labels == component_id
                    area = int(component.sum())
                    if area >= self.config.min_region_area:
                        continue
                    dilated = ndimage.binary_dilation(component, iterations=1)
                    border = dilated & ~component
                    neighbors = out[border]
                    neighbors = neighbors[neighbors != color_id]
                    if neighbors.size == 0:
                        continue
                    values, counts = np.unique(neighbors, return_counts=True)
                    target = int(values[np.argmax(counts)])
                    out[component] = target
                    changed = True
        return out

    def _extract_regions(self, indexed: np.ndarray) -> list[Region]:
        regions: list[Region] = []
        h, w = indexed.shape
        for color_id in np.unique(indexed):
            mask = (indexed == color_id).astype(np.uint8) * 255
            contours, _hierarchy = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            region_index = 0
            for contour in contours:
                area = int(round(abs(cv2.contourArea(contour))))
                if area < self.config.min_region_area:
                    continue
                region_index += 1
                epsilon = self.config.smooth_epsilon
                contour = cv2.approxPolyDP(contour, epsilon, True)
                filled = np.zeros((h, w), dtype=np.uint8)
                cv2.drawContours(filled, [contour], -1, 255, thickness=cv2.FILLED)
                distance = cv2.distanceTransform(filled, cv2.DIST_L2, 5)
                _minv, maxv, _minloc, maxloc = cv2.minMaxLoc(distance)
                regions.append(
                    Region(
                        color_id=int(color_id),
                        region_index=region_index,
                        area=area,
                        contour=contour,
                        label_x=float(maxloc[0]),
                        label_y=float(maxloc[1]),
                        label_radius=float(maxv),
                    )
                )
        return regions

    @staticmethod
    def render_effect(result: PipelineResult) -> Image.Image:
        effect = result.palette[result.indexed]
        return Image.fromarray(effect.astype(np.uint8), "RGB")

    @staticmethod
    def iter_region_ids(regions: Iterable[Region]) -> Iterable[str]:
        for r in regions:
            yield f"c{r.color_id + 1:02d}-r{r.region_index:03d}"
