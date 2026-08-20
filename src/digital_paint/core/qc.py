from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path

import numpy as np

from digital_paint.core.labels import LabelPlacement
from digital_paint.core.regions import RegionResult


@dataclass(slots=True)
class QCItem:
    code: str
    status: str
    message: str
    region_ids: list[int]


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


def run_qc(
    region_result: RegionResult,
    placements: list[LabelPlacement],
    *,
    min_area: int = 40,
    palette_size: int | None = None,
) -> QCReport:
    """Run deterministic production checks on the shared region model."""
    items: list[QCItem] = []
    region_ids = region_result.region_id
    colors = region_result.color_id

    unassigned = int(np.count_nonzero(region_ids < 0))
    items.append(QCItem(
        code="REGION_COVERAGE",
        status="FAIL" if unassigned else "PASS",
        message=f"未归属像素: {unassigned}" if unassigned else "所有像素均已归属封闭区域",
        region_ids=[],
    ))

    tiny = [r.region_id for r in region_result.regions if r.area < min_area]
    items.append(QCItem(
        code="TINY_REGIONS",
        status="WARN" if tiny else "PASS",
        message=f"仍有 {len(tiny)} 个小于 {min_area}px 的碎块" if tiny else "未发现低于阈值的碎块",
        region_ids=tiny,
    ))

    no_fit = [p.region_id for p in placements if not p.fits]
    items.append(QCItem(
        code="LABEL_FIT",
        status="WARN" if no_fit else "PASS",
        message=f"{len(no_fit)} 个区域无法稳定容纳约 5pt 编号" if no_fit else "所有区域均可容纳生产编号",
        region_ids=no_fit,
    ))

    expected_ids = {r.region_id for r in region_result.regions}
    placed_ids = {p.region_id for p in placements}
    missing = sorted(expected_ids - placed_ids)
    items.append(QCItem(
        code="LABEL_COVERAGE",
        status="FAIL" if missing else "PASS",
        message=f"{len(missing)} 个区域缺少编号" if missing else "每个区域均有编号位置",
        region_ids=missing,
    ))

    if palette_size is not None:
        bad_colors = sorted(int(v) for v in np.unique(colors) if int(v) < 0 or int(v) >= palette_size)
        items.append(QCItem(
            code="PALETTE_MAPPING",
            status="FAIL" if bad_colors else "PASS",
            message=f"无效颜色索引: {bad_colors}" if bad_colors else "全部区域均映射到有效颜色",
            region_ids=[],
        ))

    # Each adjacency relation must be symmetric. This protects shared-boundary construction.
    asymmetric: list[int] = []
    for rid, neighbours in region_result.adjacency.items():
        for n in neighbours:
            if rid not in region_result.adjacency.get(n, set()):
                asymmetric.extend([rid, n])
    items.append(QCItem(
        code="ADJACENCY_TOPOLOGY",
        status="FAIL" if asymmetric else "PASS",
        message="区域邻接图存在非对称关系" if asymmetric else "区域邻接拓扑一致",
        region_ids=sorted(set(asymmetric)),
    ))

    return QCReport(items=items)
