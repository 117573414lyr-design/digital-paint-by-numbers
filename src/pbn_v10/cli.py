from __future__ import annotations

import argparse
from pathlib import Path

from .exporters import export_effect, export_lineart_svg, export_manifest, export_palette, export_qa
from .pdf_export import export_production_pdf
from .pipeline import PaintByNumbersPipeline, V10Config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pbn-v10", description="Digital Paint-by-Numbers V10")
    parser.add_argument("image", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("output"))
    parser.add_argument("--colors", type=int, default=24)
    parser.add_argument("--min-region-area", type=int, default=120)
    parser.add_argument("--smooth-epsilon", type=float, default=1.2)
    parser.add_argument("--smooth-iterations", type=int, default=2)
    parser.add_argument("--label-min-radius", type=float, default=5.0)
    parser.add_argument("--color-library", type=Path, default=None, help="CSV: number,r,g,b")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = V10Config(
        colors=args.colors,
        min_region_area=args.min_region_area,
        smooth_epsilon=args.smooth_epsilon,
        smooth_iterations=args.smooth_iterations,
        label_min_radius=args.label_min_radius,
        color_library=args.color_library,
    )
    out = args.output
    out.mkdir(parents=True, exist_ok=True)

    result = PaintByNumbersPipeline(config).run(args.image)
    export_effect(result, out / "effect.png")
    export_lineart_svg(result, out / "lineart.svg", config)
    export_palette(result, out / "palette.csv")
    export_production_pdf(result, out / "production.pdf", config)
    report = export_qa(result, out / "qa_report.json", config)
    export_manifest(out, args.image, config, report)

    status = "PASS" if report["pass"] else "REVIEW"
    print(f"V10 complete: {status} -> {out.resolve()}")


if __name__ == "__main__":
    main()
