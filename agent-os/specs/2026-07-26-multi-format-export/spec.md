# Specification: Multi-format Export & Reproducibility Hardening

## Goal
Turn the `export` stage from a stub into the real end of the pipeline: write the optimized
SVG to `output/`, optionally convert it to PDF/PNG/TIFF/EPS through an injectable converter
seam that degrades gracefully without the external tool, and guarantee byte-identical SVG
output from identical inputs. Completes the PRD §8 pipeline (no stages left stubbed).

## User Stories
- As a user, I want the final art written to `output/` in the formats I asked for
  (`--output svg pdf png`), so a single `python build.py` yields shippable files.
- As a user without a converter installed, I want SVG to still be written and other formats
  skipped with a clear warning, rather than a crash.
- As a user, I want identical inputs to yield byte-identical output, so my art is reproducible.
- As a developer, I want export behind an injected seam so the whole pipeline is testable
  offline with a fake exporter and `tmp_path`.

## Specific Requirements

**Config (`src/config.py`, `src/cli.py`, `build.py`)**
- Add `"tiff"`, `"eps"` to `SUPPORTED_OUTPUTS` → `("svg", "pdf", "png", "tiff", "eps")`.
- Add `SUPPORTED_PNG_SIZES = (4096, 8192, 16384, 32768, 65536)` (exported) and a `png_size`
  setting: default `4096`, validated in `build_settings` against the allowlist (raise
  `ConfigError` listing valid sizes). Extend `Settings` with `png_size: int` and `DEFAULTS`.
- Add `--png-size` CLI flag (`type=int`, default `None`); map through `cli_overrides`. Show
  `png_size` in `build.py`'s resolved-settings table.

**Export seam (`src/export.py`, new)**
- `Exporter` protocol (runtime-checkable): `export(svg: str, dest: Path, fmt: str, *, png_size: int) -> Path | None`.
- `FileExporter` (real): `fmt == "svg"` writes the string to `dest` (utf-8) and returns it —
  no external tool. Other formats shell out to `rsvg-convert -f <fmt> -o <dest>` (SVG on
  stdin), passing `--width <png_size>` for raster formats (`png`, `tiff`). On
  `FileNotFoundError`/non-zero exit → warn and return `None` (skip). Injectable command
  (default `"rsvg-convert"`); no import-time subprocess.
- `RASTER_FORMATS = frozenset({"png", "tiff"})`.

**Pipeline integration (`src/pipeline.py`)**
- Add `output_dir: Path` and `exporter: Exporter` fields to `RunContext`; add `output_dir`
  (default `"output"`) and `exporter` (default `FileExporter()`) params to `Pipeline.__init__`
  and thread into `run()`, mirroring `cache_dir`/`optimizer`.
- Replace the `export` stub with `_export_stage`: read `artifacts["optimized_svg"]`; for each
  format in `sorted(settings.outputs)` build `output_dir / f"{stem}.{fmt}"` (stem = regions
  joined by `-`, lowercased) and call `ctx.exporter.export(...)`; collect non-`None` results
  into `artifacts["export_paths"]`. Compute `artifacts["svg_sha256"] = sha256(svg)`. Log the
  count/formats written and the short digest.

## Existing Code to Leverage
- **`src/optimize.py`:** `SvgoOptimizer` is the exact pattern for `FileExporter` (subprocess +
  `FileNotFoundError`/`CalledProcessError` graceful fallback + `warnings.warn`).
- **`src/pipeline.py`:** `RunContext`/`Pipeline` DI (`downloader`, `loader`, `optimizer`)
  extended with `exporter`; `cache_dir`/`datasets_dir` are the pattern for `output_dir`.
  `optimize_svg` already writes `artifacts["optimized_svg"]`.
- **`src/config.py` / `src/cli.py`:** `SUPPORTED_*` allowlists + `build_settings` validation,
  `_coerce_outputs`, `cli_overrides` precedence.
- **`tests/test_optimize_pipeline.py`:** the offline `FakeZipDownloader`/`NetworkLoader`
  fixture reused for an end-to-end pipeline test with a fake exporter and `tmp_path`.

## Out of Scope
- Actual raster tiling / 65536px rendering (delegated to the external converter).
- Bundling librsvg/cairo/Inkscape; testing against a real converter binary.
- Provenance/manifest files beyond `svg_sha256`; web/animated/GeoJSON outputs.

## Acceptance Criteria
- `export` writes the SVG file always; requested raster/vector formats go through the injected
  exporter into `artifacts["export_paths"]`; the real exporter degrades gracefully without the
  CLI tool.
- `tiff`/`eps` accepted by config; `png_size` validated (default 4096); `--png-size` overrides
  YAML, unset never clobbers.
- Running the full pipeline twice on identical inputs yields a byte-identical SVG file and
  identical `svg_sha256`.
- No pipeline stage remains a stub; full existing suite passes with no regressions; ≤10
  additional strategic tests in TG3.
