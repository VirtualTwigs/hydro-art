# Requirements: Multi-format Export & Reproducibility Hardening (Roadmap #10)

## Source
- Roadmap item #10: "Export optional PDF/PNG (with tiled rendering up to 65536px)/TIFF/EPS
  from the SVG and verify the full single-command workflow produces byte-identical
  results from identical inputs."
- PRD §22 (Output Formats: required SVG; optional PDF/PNG/TIFF/EPS), §23 (PNG sizes
  4096–65536px, tile rendering), §7 (`output/` dir), §2 ("Be reproducible").

## Functional requirements
1. The `export` pipeline stage (currently the last stub in `_STAGE_FUNCS`) writes the
   optimized SVG (`artifacts["optimized_svg"]`) to a real file under an output directory.
2. SVG is always producible with **no external tool** (pure stdlib write) — it is the
   one required format.
3. PDF / PNG / TIFF / EPS are optional and produced by converting the SVG through an
   **injectable converter seam** (mirroring `Downloader` / `LayerLoader` / `SvgOptimizer`).
   The real converter shells out to a CLI (`rsvg-convert` by default) and **degrades
   gracefully** — a missing/failing tool warns and skips that format instead of crashing.
4. Output format selection continues to flow from `settings.outputs`; extend the config
   allowlist to include `tiff` and `eps` (svg/pdf/png already supported).
5. PNG/raster size is configurable via a validated `png_size` setting (PRD §23 sizes:
   4096/8192/16384/32768/65536), default 4096; exposed as `--png-size`.
6. The stage records which files were written in `artifacts["export_paths"]` (a
   `{format: Path}` map) and a stable `artifacts["svg_sha256"]` digest of the SVG.
7. Reproducibility: identical inputs produce a **byte-identical** SVG file on disk (and an
   identical `svg_sha256`) across runs.

## Non-functional / constraints
- No new heavy runtime dependency for the required path; conversion tools are optional and
  injected, so the full test suite stays **offline and deterministic** (fake exporter +
  `tmp_path`; the real converter is never invoked in tests).
- Preserve the existing architecture: DI via `RunContext`, results through `artifacts`,
  validation at the boundary in `build_settings` raising `ConfigError`, config precedence
  defaults < YAML < CLI with unset flags never clobbering YAML.

## Out of scope
- Real rasterization/tiling implementation for 65536px (delegated to the external
  converter; the seam only passes the requested size). No bundling of librsvg/cairo.
- Interactive/animated/web outputs, GeoJSON, vector tiles (PRD §33 future work).
- Provenance manifest files beyond the in-memory `svg_sha256` digest.
