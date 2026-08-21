from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path
from typing import Callable

import numpy as np

from digital_paint.core.export_quality import vector_quality_from_region_map
from digital_paint.core.labels import LabelPlacement
from digital_paint.core.regions import RegionResult

CancelCheck = Callable[[], None]
ProgressCallback = Callable[[str, int], None]


@dataclass(slots=True)
class QCItem:
    code: str
    status: str
    message: str
    region_ids: list[int]
    locations: list[tuple[float, float]] | None = None


@dataclass(slots=True)
class QCReport:
    items: list[QCItem]

    @property
    def passed(self) -> bool:
        return not any(item.status == "FAIL" for item in self.items)

    def counts(self) -> dict[str, int]:
        result = {"PASS": 0, "WARN": 0, "FAIL": 0}
        for item in self.items:
            result[item.status] = result.get(item.status, 0) + 1
        return result

    def save_json(self, path: str | Path) -> None:
        payload = {"passed": self.passed, "counts": self.counts(), "items": [asdict(i) for i in self.items]}
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _emit(callback: ProgressCallback | None, stage: str, percent: int) -> None:
    if callback is not None:
        callback(stage, max(0, min(100, int(percent))))


def _region_centers(region_result: RegionResult, ids: list[int]) -> list[tuple[float, float]]:
    by_id = {r.region_id: r for r in region_result.regions}
    out: list[tuple[float, float]] = []
    for rid in ids:
        region = by_id.get(rid)
        if region is not None:
            y, x = region.centroid
            out.append((float(x), float(y)))
    return out


def run_qc(
    region_result: RegionResult,
    placements: list[LabelPlacement],
    *,
    min_area: int = 40,
    palette_size: int | None = None,
    cancel_check: CancelCheck | None = None,
    progress_callback: ProgressCallback | None = None,
) -> QCReport:
    """Run deterministic production checks with cancellable, visible substages."""
    items: list[QCItem] = []
    region_ids = region_result.region_id
    colors = region_result.color_id

    _emit(progress_callback, "区域覆盖检查", 4)
    unassigned_mask = region_ids < 0
    unassigned = int(np.count_nonzero(unassigned_mask))
    unassigned_locations = [(float(x), float(y)) for y, x in np.argwhere(unassigned_mask)[:50]]
    items.append(QCItem(
        code="REGION_COVERAGE",
        status="FAIL" if unassigned else "PASS",
        message=f"未归属像素: {unassigned}" if unassigned else "所有像素均已归属封闭区域",
        region_ids=[],
        locations=unassigned_locations,
    ))
    if cancel_check is not None:
        cancel_check()

    _emit(progress_callback, "碎块阈值检查", 10)
    tiny = [r.region_id for r in region_result.regions if r.area < min_area]
    items.append(QCItem(
        code="TINY_REGIONS",
        status="WARN" if tiny else "PASS",
        message=f"仍有 {len(tiny)} 个小于 {min_area}px 的碎块" if tiny else "未发现低于阈值的碎块",
        region_ids=tiny,
        locations=_region_centers(region_result, tiny),
    ))

    _emit(progress_callback, "编号容量检查", 16)
    no_fit = [p.region_id for p in placements if not p.fits]
    items.append(QCItem(
        code="LABEL_FIT",
        status="WARN" if no_fit else "PASS",
        message=f"{len(no_fit)} 个区域无法稳定容纳约 5pt 编号" if no_fit else "所有区域均可容纳生产编号",
        region_ids=no_fit,
        locations=[(p.x, p.y) for p in placements if not p.fits],
    ))

    _emit(progress_callback, "编号覆盖检查", 22)
    expected_ids = {r.region_id for r in region_result.regions}
    placed_ids = {p.region_id for p in placements}
    missing = sorted(expected_ids - placed_ids)
    items.append(QCItem(
        code="LABEL_COVERAGE",
        status="FAIL" if missing else "PASS",
        message=f"{len(missing)} 个区域缺少编号" if missing else "每个区域均有编号位置",
        region_ids=missing,
        locations=_region_centers(region_result, missing),
    ))
    if cancel_check is not None:
        cancel_check()

    _emit(progress_callback, "编号越界检查", 30)
    label_outside: list[int] = []
    outside_locations: list[tuple[float, float]] = []
    h, w = region_ids.shape
    for index, p in enumerate(placements):
        xi, yi = int(round(p.x)), int(round(p.y))
        if not (0 <= yi < h and 0 <= xi < w) or int(region_ids[yi, xi]) != p.region_id:
            label_outside.append(p.region_id)
            outside_locations.append((p.x, p.y))
        if cancel_check is not None and index % 1024 == 0:
            cancel_check()
    items.append(QCItem(
        code="LABEL_INSIDE_REGION",
        status="FAIL" if label_outside else "PASS",
        message=f"{len(label_outside)} 个编号越出自己的色块" if label_outside else "所有编号中心均位于自己的色块内",
        region_ids=label_outside,
        locations=outside_locations,
    ))

    _emit(progress_callback, "颜色映射检查", 36)
    if palette_size is not None:
        bad_colors = sorted(int(v) for v in np.unique(colors) if int(v) < 0 or int(v) >= palette_size)
        items.append(QCItem(
            code="PALETTE_MAPPING",
            status="FAIL" if bad_colors else "PASS",
            message=f"无效颜色索引: {bad_colors}" if bad_colors else "全部区域均映射到有效颜色",
            region_ids=[],
            locations=[],
        ))

    _emit(progress_callback, "邻接拓扑检查", 42)
    asymmetric: list[int] = []
    for rid, neighbours in region_result.adjacency.items():
        for n in neighbours:
            if rid not in region_result.adjacency.get(n, set()):
                asymmetric.extend([rid, n])
    asymmetric_unique = sorted(set(asymmetric))
    items.append(QCItem(
        code="ADJACENCY_TOPOLOGY",
        status="FAIL" if asymmetric_unique else "PASS",
        message="区域邻接图存在非对称关系" if asymmetric_unique else "区域邻接拓扑一致",
        region_ids=asymmetric_unique,
        locations=_region_centers(region_result, asymmetric_unique),
    ))
    if cancel_check is not None:
        cancel_check()

    def vector_progress(stage: str, percent: int) -> None:
        _emit(progress_callback, stage, 45 + int(percent * 0.54))

    _emit(progress_callback, "矢量边界质检", 45)
    vector = vector_quality_from_region_map(
        region_result.region_id,
        [p.font_pt for p in placements],
        cancel_check=cancel_check,
        progress_callback=vector_progress,
    )
    items.append(QCItem(
        code="DUPLICATE_BOUNDARIES",
        status="FAIL" if vector.duplicate_segments else "PASS",
        message=f"发现 {vector.duplicate_segments} 条重复边界" if vector.duplicate_segments else "共享边界无重复描边",
        region_ids=[],
        locations=[],
    ))
    items.append(QCItem(
        code="CROSSING_BOUNDARIES",
        status="FAIL" if vector.crossing_segments else "PASS",
        message=f"发现 {vector.crossing_segments} 处边界交叉" if vector.crossing_segments else "未发现边界交叉",
        region_ids=[],
        locations=[],
    ))
    items.append(QCItem(
        code="PRODUCTION_SPEC",
        status="FAIL" if not vector.passed else "PASS",
        message=(
            "0.1pt / CMYK 40,100,100,100 / 4.2,6,8pt 生产参数异常"
            if not vector.passed else "生产线宽、CMYK 与编号字号参数通过"
        ),
        region_ids=[],
        locations=[],
    ))

    _emit(progress_callback, "QC 完成", 100)
    return QCReport(items=items)
