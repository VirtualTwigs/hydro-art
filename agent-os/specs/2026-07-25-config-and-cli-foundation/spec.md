# Specification: Configuration & CLI Foundation

## Goal
Establish a validated, typed settings object—built by merging built-in defaults, a YAML config file, and CLI flags—that drives every downstream pipeline stage, with `python build.py` runnable end-to-end as a no-op pipeline.

## User Stories
- As a user, I want to run `python build.py` with sensible defaults so that I get a valid Oregon+Washington configuration without writing any config.
- As a user, I want to override config via `config.yaml` and CLI flags so that I can change region, palette, glow, and outputs without editing code.
- As a developer, I want a single typed settings object injected into each stage so that no module reads global state or parses config on its own.

## Specific Requirements

**Settings model**
- Define an immutable, typed settings object (e.g. frozen dataclass) covering: `regions` (list[str]), `projection` (str, default `EPSG:5070`), `stream_order` (str, default `all`), `background` (str hex, default `#000000`), `line_width` (float, default `0.35`), `palette` (str, default `neon`), `glow` (bool, default `false`), and `outputs` (set/flags for svg/pdf/png).
- No global state; the object is constructed once and passed by dependency injection into downstream stages.
- Include type hints and docstrings on all public fields and constructors.

**Built-in defaults**
- Provide a defaults source reflecting PRD §19/§25: regions `[Oregon, Washington]`, projection `EPSG:5070`, stream_order `all`, background `#000000`, line_width `0.35`, palette `neon`, glow `false`, outputs `{svg: true, png: false, pdf: false}`.
- Defaults must produce a fully valid settings object when no YAML and no flags are supplied.

**YAML config loading**
- Load `config.yaml` (default path, overridable) via PyYAML into a plain mapping.
- Missing file is allowed (fall back to defaults); malformed YAML raises a clear, actionable error.
- Unknown keys are rejected or warned (decide during implementation) to catch typos early.

**CLI parsing**
- Support the PRD §24 invocations: bare `build.py`, `--region <name...>`, `--palette <name>`, `--glow`, `--output <fmt...>` (one or more of `svg pdf png`).
- Add `--config <path>` to point at an alternate YAML file.
- `--glow` is a boolean flag; `--region` and `--output` accept one or more values.

**Precedence & merge**
- Merge order (lowest to highest): built-in defaults → YAML values → CLI flags.
- Only explicitly provided CLI flags override YAML; unspecified flags do not clobber YAML values.
- Produce one final settings object from the merged result.

**Validation**
- Validate at the boundary: region names normalized case-insensitively and checked against the supported set (Oregon, Washington) for this release; unsupported regions raise a clear error listing valid options.
- Validate projection is one of the supported EPSG codes (5070/4326/3857), background is a valid hex color, line_width is a positive float, and outputs contains only known formats.
- Validation failures produce human-readable messages and a non-zero exit code.

**build.py no-op pipeline**
- `build.py` is the single entry point: parse CLI → load YAML → merge → validate → construct settings → log the resolved settings, then invoke a pipeline skeleton whose stages are ordered per PRD §8 but implemented as no-ops/stubs.
- Exit 0 on success; exit non-zero with a clear message on any config/validation error.

**Logging**
- Use `rich` to print the resolved settings and a summary of the (stubbed) pipeline stages, per PRD §27; no bare prints for user-facing output.

**Extensibility seam**
- Structure the supported-regions set and defaults so adding a future region (California, Idaho, etc.) requires changing one registry, not multiple modules (PRD §5.1 / §34).

## Existing Code to Leverage

**No existing application code**
- This is the first feature in a freshly scaffolded repo; there is no prior config/CLI code to reuse.
- Follow the module layout in PRD §31 (`build.py`, plus a config/utils module) and the project standards in `agent-os/standards/global/` (coding-style, conventions, error-handling, validation).
- Reuse the YAML shape defined in PRD §25 and styling defaults in PRD §19 verbatim as the defaults source of truth.

## Out of Scope
- Actual dataset download, extraction, or caching (roadmap item #2).
- Any GIS processing: geometry validation/repair, reprojection, clipping (items #3–#4).
- Graph construction, stream ordering, watershed grouping (items #5–#6).
- Basin coloring logic beyond storing the palette name (item #7).
- SVG rendering, glow implementation, SVGO optimization (items #8–#9).
- PDF/PNG/TIFF/EPS export and tiled rendering (item #10).
- Multi-region support beyond Oregon and Washington (future).
- A web viewer, interactivity, or any output beyond the no-op pipeline skeleton.
