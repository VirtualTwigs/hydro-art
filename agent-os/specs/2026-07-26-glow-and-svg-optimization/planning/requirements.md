# Requirements: Optional Glow & SVG Optimization

## Raw Idea (from roadmap item #9)

Add pure-vector or Gaussian-blur glow modes with configurable radius, then run SVGO to optimize duplicate paths, unused defs, style repetition, coordinate precision, and grouping.

## Source Requirements (from docs/PRD.md)

- **§8 GIS Pipeline:** the `Optimize SVG` stage sits between `Generate SVG` and `Export`.
- **§20 Optional Glow:** Mode A pure vector; Mode B SVG Gaussian blur. Configurable radius.
- **§21 SVG Optimization:** run SVGO automatically; optimize duplicate paths, unused defs, style repetition, coordinate precision, grouping.
- **§27 Logging:** rich terminal output; report statistics.
- **§30 Code Quality:** type hints, docstrings, DI, no global state, unit tests, pure/offline-testable.

## Design Notes / Decisions

- **Glow is a render-time concern, threaded through `generate_svg`.** The item #8 report/HANDOFF already noted the renderer "emits a bare `<defs/>` for glow filters to populate." `render_svg` gains optional `glow`/`glow_mode`/`glow_radius` params; `generate_svg` passes `settings.glow`/`glow_mode`/`glow_radius`. Glow-off produces byte-identical output to item #8 (backward compatible — existing tests unchanged). This is cleaner than re-parsing the serialized string in `optimize_svg`, and keeps both glow modes trivial to emit from the structured data.
- **Blur mode (§20 Mode B):** add one `<filter id="hydro-glow">` to `<defs>` with `feGaussianBlur stdDeviation="<radius>"` merged over `SourceGraphic`, and set `filter="url(#hydro-glow)"` on each river `<g>` so the neon strokes bloom.
- **Vector mode (§20 Mode A):** no filter; emit a wider, semi-transparent "halo" `<g>` (same paths, `stroke-width = line_width + 2*radius`, reduced `stroke-opacity`) beneath each sharp river group. Pure vector, editor-friendly, no filter primitives.
- **`optimize_svg` = SVGO only, behind an injectable seam.** SVGO is a Node CLI; running it is network/host-dependent, so it sits behind a `SvgOptimizer` protocol (mirroring the `Downloader`/`LayerLoader` DI pattern). The real `SvgoOptimizer` shells out to `svgo` and **degrades gracefully** (returns the input unchanged + warns) when `svgo`/Node is absent, so `build.py` never crashes on a machine without it. Tests inject a fake optimizer and stay fully offline — no Node, no subprocess.
- **Config surface:** add `glow_mode` (allowlist `("vector", "blur")`, default `"blur"`) and `glow_radius` (positive float, default `2.0`) to `DEFAULTS`/`Settings`, validated in `build_settings` (reusing the `SUPPORTED_*` + `ConfigError` pattern). Add `--glow-mode`/`--glow-radius` CLI flags (default `None` so unset flags never clobber YAML). The existing `glow` bool is the on/off switch.
- **Pipeline wiring:** `optimize_svg` reads `artifacts["svg"]`, runs it through `ctx.optimizer`, stores `artifacts["optimized_svg"]`, logs before/after sizes. Add an `optimizer` field to `RunContext` + `Pipeline.__init__` (default real `SvgoOptimizer`), like `downloader`/`loader`. `export` remains a stub.
- **Determinism preserved.** Glow defs/halos are emitted deterministically; SVGO output is deterministic for a given SVGO version but is a host tool, so byte-identical reproducibility (item #10) is asserted on the *pre-SVGO* SVG; the optimize step is validated via the injected seam.
- **Pure & testable.** Glow is a pure function of structured inputs; the optimizer is injected. No GDAL, no Node, no network in tests.

## Open Questions (resolve during implementation)

- `glow_radius` units are SVG user units (same space as coordinates/`line_width`); visual tuning vs. the large projected viewBox is a coordinate-normalization concern deferred to item #10. Default `2.0` is a reasonable placeholder.
- Vector-mode halo opacity: use a fixed sensible constant (e.g. `0.4`); a configurable multi-layer halo is out of scope.
- When `glow` is off, `glow_mode`/`glow_radius` are still validated but unused — fine (consistent with other always-validated settings).
