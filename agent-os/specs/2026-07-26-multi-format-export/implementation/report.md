# Implementation Report: Multi-format Export & Reproducibility Hardening

**Date:** 2026-07-26
**Status:** Complete — all 3 task groups done, 147/147 tests passing (13 new).
This completes the PRD §8 pipeline: **no stage remains a stub.**

## What was built

| File | Purpose |
|------|---------|
| `src/config.py` | `tiff`/`eps` added to `SUPPORTED_OUTPUTS`; new `SUPPORTED_PNG_SIZES = (4096, 8192, 16384, 32768, 65536)`; `png_size` (default `4096`) on `DEFAULTS` + `Settings`, validated against the allowlist in `build_settings` (raises `ConfigError`). |
| `src/cli.py` | `--png-size` flag (`type=int`, default `None`); added to `cli_overrides`. |
| `build.py` | `png_size` row in the settings table; dropped the stale "downstream stages are stubs" completion message. |
| `src/export.py` | `Exporter` `Protocol` seam + `FileExporter`: writes `svg` natively (no tool), shells out to `rsvg-convert` for other formats (`--width png_size` for `RASTER_FORMATS = {png, tiff}`), degrading gracefully (warn + return `None`) on `FileNotFoundError` / non-zero exit. |
| `src/pipeline.py` | `output_dir` + `exporter` on `RunContext` and `Pipeline`; real `_export_stage` replacing the last stub — writes each requested format to `output_dir/<regions>.<fmt>`, records `artifacts["export_paths"]` and a stable `artifacts["svg_sha256"]`, logs counts + digest. |
| `tests/test_export_config.py`, `test_export.py`, `test_export_pipeline.py` | 6 + 3 + 4 = 13 new tests. |

## Key decisions

- **Injectable `Exporter` seam** mirroring `SvgoOptimizer`: production injects `FileExporter`, tests inject a fake. SVG (the one required format) is written with pure stdlib, so the required path needs **no external tool** and the suite stays fully offline.
- **Graceful degradation** for PDF/PNG/TIFF/EPS: a host without `rsvg-convert` still gets the SVG; other formats are skipped with a warning (verified end-to-end — the golden-path smoke test wrote `oregon.svg` and skipped pdf/png).
- **Reproducibility** captured as `artifacts["svg_sha256"]`; a two-run test asserts byte-identical SVG files on disk and identical digests.
- **`png_size` as a validated allowlist** (PRD §23 sizes) passed to the converter; actual tiling/rasterization is delegated to the external tool, keeping the seam thin and testable.

## Acceptance criteria met

- `export` always writes the SVG; requested raster/vector formats go through the injected exporter into `artifacts["export_paths"]`; the real exporter degrades gracefully without the CLI tool.
- `tiff`/`eps` accepted; `png_size` validated (default 4096); `--png-size` overrides YAML, unset never clobbers.
- Full pipeline run twice on identical inputs → byte-identical SVG file + identical `svg_sha256`.
- No pipeline stage remains a stub; full existing suite passes with no regressions; 13 added tests (≤10 strategic in TG3).

## Regressions fixed

- Item #8/#9 pipeline tests asserted `export` was still a stub and omitted `output_dir` — they now (a) inject `output_dir=tmp_path/"output"` so runs don't write into the repo, and (b) assert the pipeline runs end-to-end (`test_generate_svg_feeds_downstream_stages`, `test_optimized_svg_feeds_export`).
- Six older `*_pipeline` / integration test helpers gained `output_dir=tmp_path/"output"` for the same isolation reason (export now runs as the final stage in every full-pipeline test).

## Notes — roadmap complete

- All 10 roadmap items are implemented; the PRD §8 pipeline runs end-to-end (`download → … → generate_svg → optimize_svg → export`) with no stubs.
- External tools remain optional and injected: `svgo` (optimization) and `rsvg-convert` (raster/vector export). Both degrade gracefully; installing them unlocks the optimized/rasterized outputs. Consider adding them (or a `cairosvg` fallback) to docs/requirements when packaging.
