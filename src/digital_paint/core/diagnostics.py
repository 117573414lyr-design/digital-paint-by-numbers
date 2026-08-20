from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import os
import platform
import sys
import time
import traceback
from typing import Any


@dataclass(slots=True)
class EnvironmentReport:
    python: str
    platform: str
    machine: str
    processor: str
    executable: str
    cwd: str


def environment_report() -> EnvironmentReport:
    return EnvironmentReport(
        python=sys.version.replace("\n", " "),
        platform=platform.platform(),
        machine=platform.machine(),
        processor=platform.processor(),
        executable=sys.executable,
        cwd=os.getcwd(),
    )


def write_crash_report(folder: str | Path, exc: BaseException, context: dict[str, Any] | None = None) -> Path:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = folder / f"crash-{stamp}.json"
    payload = {
        "time": time.time(),
        "exception_type": type(exc).__name__,
        "message": str(exc),
        "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        "environment": asdict(environment_report()),
        "context": context or {},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
