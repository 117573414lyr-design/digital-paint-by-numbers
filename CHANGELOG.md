# Changelog

## 0.6.0 - 2026-08-20

### V6 production integration

- Unified CPU pipeline: quantize → regions → fragment merge → labels → optional custom palette → QC.
- V6 Windows UI with source/effect previews, minimum-region control, custom palette import and production exports.
- PNG effect export, editable SVG linework, three-page vector PDF and JSON QC report.
- Single-pass shared-boundary extraction so internal borders are emitted once instead of double-stroked.
- Expanded automated tests across regions, palette matching, shared boundaries and the full pipeline.

### V5 vector + QC

- Vector SVG export with editable text labels.
- Three-page PDF: vector effect regions, numbered linework and palette page.
- Production line target: 0.1 pt; CMYK target 40/100/100/100.
- QC framework with PASS/WARN/FAIL for region coverage, tiny regions, label capacity, label coverage, palette mapping and adjacency topology.

### V4 custom palette

- JSON import/export schema for user color libraries.
- CIE Lab nearest-color matching with Delta E 1976 distance.
- Formal color codes separated from temporary KMeans cluster indexes.

### V3 linework + labels

- Deep-interior label placement via distance transform.
- Adaptive 4.2 / 6 / 8 pt number sizing.
- Detection of regions unable to hold an approximately 5 pt production number.
- Vector contour extraction foundation.

### V2 production regions

- Connected-component region analysis with stable `region_id` values.
- Symmetric region adjacency graph.
- Small-fragment merge using shared-border strength plus color-distance tie breaking.
- Region model shared by effect, labels, palette and vector output.

## 0.1.0 - 2026-08-20

### Added

- Windows PySide6 desktop application foundation.
- Image import and preview.
- Configurable paint color count.
- CIE Lab + KMeans image quantization.
- Background processing worker.
- PNG export.
- Initial production data contract with `color_id` and `region_id`.
- Core unit tests.
- Windows installation and usage documentation.
