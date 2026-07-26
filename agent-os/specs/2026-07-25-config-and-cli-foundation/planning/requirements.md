# Requirements: Configuration & CLI Foundation

## Raw Idea (from roadmap item #1)

Load a YAML config and parse CLI flags (`--region`, `--palette`, `--glow`, `--output`) into a validated, typed settings object that drives every downstream stage, with `python build.py` runnable end-to-end as a no-op pipeline.

## Source Requirements (from docs/PRD.md)

- **§24 CLI:** Support `python build.py`, `python build.py --region washington`, `python build.py --palette neon`, `python build.py --glow`, `python build.py --output svg pdf png`.
- **§25 Configuration:** YAML config with keys `region` (list), `projection` (EPSG string), `stream_order`, `background` (hex), `line_width` (float), `palette`, `glow` (bool), and `output` (svg/png/pdf bools).
- **§5.1 Geographic Scope:** Initial regions Oregon and Washington; region selection must be configurable; architecture must extend to future regions.
- **§9 Coordinate Systems:** Internal EPSG:5070 default; optional EPSG:4326 / EPSG:3857.
- **§16/§19 Styling defaults:** neon palette, background `#000000`, line width `0.35`.
- **§30 Code Quality:** PEP8, type hints, docstrings, unit tests, modular architecture, dependency injection, no global state.
- **§27 Logging:** Rich terminal output with timing/warnings.
- **§31 Project Structure:** `config.yaml` and `build.py` at project root.

## Why This Is First

Every downstream pipeline stage (download, validate, project, graph, color, render, export) consumes configuration: region determines what to download and clip, projection drives reprojection, palette/line_width/background/glow drive rendering, and output flags drive export. A validated, typed settings object with no global state is the dependency-injection seam the rest of the pipeline plugs into. Establishing it first prevents ad-hoc config reads scattered across modules.

## Notes / Open Questions

- CLI flags override YAML values; YAML overrides built-in defaults (precedence to confirm during implementation).
- `--output` takes one or more of `svg pdf png` (and later tiff/eps); maps onto the YAML `output` booleans.
- Region names should be normalized (case-insensitive) and validated against a known set for the initial release.
