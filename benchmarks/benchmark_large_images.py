from __future__ import annotations

import argparse
import json
import time

import numpy as np

from digital_paint.core.performance import adaptive_sample_limit
from digital_paint.core.quantize import quantize_lab
from digital_paint.core.tasking import estimate_working_set_bytes


SIZES = {
    "12mp": (4000, 3000),
    "24mp": (6000, 4000),
    "48mp": (8000, 6000),
}


def run_case(name: str, colors: int, seed: int) -> dict[str, float | int | str]:
    width, height = SIZES[name]
    rng = np.random.default_rng(seed)
    # Synthetic gradient/noise mixture keeps the benchmark deterministic while
    # avoiding a trivially compressible flat-color image.
    x = np.linspace(0, 255, width, dtype=np.uint8)
    y = np.linspace(0, 255, height, dtype=np.uint8)[:, None]
    image = np.empty((height, width, 3), dtype=np.uint8)
    image[..., 0] = x
    image[..., 1] = y
    image[..., 2] = rng.integers(0, 256, size=(height, width), dtype=np.uint8)
    sample_limit = adaptive_sample_limit(width * height, colors)
    estimate = estimate_working_set_bytes(width, height)
    start = time.perf_counter()
    result = quantize_lab(image, colors, sample_limit=sample_limit)
    elapsed = time.perf_counter() - start
    return {
        "case": name,
        "width": width,
        "height": height,
        "colors": colors,
        "sample_limit": sample_limit,
        "estimated_working_set_mb": round(estimate / 1024 / 1024, 1),
        "elapsed_s": round(elapsed, 3),
        "output_colors": int(len(np.unique(result.color_id))),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=list(SIZES), default="12mp")
    parser.add_argument("--colors", type=int, default=24)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(run_case(args.case, args.colors, args.seed), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
