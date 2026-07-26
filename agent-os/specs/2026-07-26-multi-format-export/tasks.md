# Task Breakdown: Multi-format Export & Reproducibility Hardening

## Overview
Total Tasks: 3 task groups

## Task List

### Config Layer

#### Task Group 1: export format + png_size config surface
**Dependencies:** None

- [ ] 1.0 Add tiff/eps outputs and png_size to config + CLI
  - [x] 1.1 Write 2-8 focused tests
    - `output` accepts `tiff`/`eps` (mapping + list forms); unknown still raises `ConfigError`
    - `png_size` defaults to `4096`, validates against `SUPPORTED_PNG_SIZES`; unsupported raises `ConfigError`
    - `--png-size` overrides YAML; unset flag never clobbers YAML
  - [x] 1.2 Add `tiff`/`eps` to `SUPPORTED_OUTPUTS`; add `SUPPORTED_PNG_SIZES`, `png_size` to `DEFAULTS` + `Settings`; validate in `build_settings`
  - [x] 1.3 Add `--png-size` to the parser + `cli_overrides`; add a row to `build.py`'s table
  - [x] 1.4 Ensure the 2-8 tests from 1.1 pass (run ONLY those)

**Acceptance Criteria:**
- `tiff`/`eps` selectable; `png_size` validated against allowlist; default 4096; unset flag never clobbers YAML

### Export Layer

#### Task Group 2: export seam + export stage
**Dependencies:** Task Group 1

- [x] 2.0 Implement `src/export.py` and replace the `export` stub
  - [x] 2.1 Write 2-8 focused tests
    - `FileExporter` writes `svg` to disk with exact contents (no tool needed)
    - Missing converter command → non-svg format returns `None` + `UserWarning` (graceful)
    - `FileExporter` satisfies the `Exporter` protocol (`isinstance`)
    - Injected fake exporter wired through the stage populates `artifacts["export_paths"]`
  - [x] 2.2 Implement `Exporter` protocol + `FileExporter` (svg native write; subprocess `rsvg-convert` for others; graceful fallback; `RASTER_FORMATS` width)
  - [x] 2.3 Add `output_dir`/`exporter` to `RunContext` + `Pipeline`; replace `export` stub (`_export_stage`: write per-format, store `export_paths` + `svg_sha256`, log)
  - [x] 2.4 Ensure the 2-8 tests from 2.1 pass (run ONLY those)

**Acceptance Criteria:**
- SVG always written; other formats via injected exporter into `artifacts["export_paths"]`; real exporter degrades gracefully

### Reproducibility & Integration

#### Task Group 3: reproducibility + integration + report
**Dependencies:** Task Groups 1-2

- [x] 3.0 End-to-end + reproducibility tests, verify no stubs, report
  - [x] 3.1 Review TG1-2 tests, identify critical gaps for THIS feature only
  - [x] 3.2 Write up to 10 additional strategic tests (end-to-end pipeline with a fake exporter → SVG file on disk + `export_paths`; two runs byte-identical SVG + identical `svg_sha256`; default real `FileExporter` degrades without the CLI tool; no pipeline stage remains a stub)
  - [x] 3.3 Run ONLY this spec's tests plus the existing suite for regressions; verify the golden path via an offline smoke test
  - [x] 3.4 Write `implementation/report.md`; update `HANDOFF.md` (item #10 done, roadmap complete)

**Acceptance Criteria:**
- Pipeline runs end-to-end with no stubs; byte-identical SVG from identical inputs; full suite passes; ≤10 additional tests

## Execution Order
1. Config Layer (Task Group 1)
2. Export Layer (Task Group 2)
3. Reproducibility & Integration (Task Group 3)
