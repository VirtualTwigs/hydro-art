# Requirements: Stream Ordering & Watershed Grouping

## Raw Idea (from roadmap item #6)

Compute selectable stream hierarchy (Strahler/Shreve/Hack/custom) and group segments into selectable HUC levels (HUC2–HUC12) for downstream coloring and SVG layering.

## Source Requirements (from docs/PRD.md)

- **§8 GIS Pipeline:** the `Compute watersheds` stage sits between `Build hydrography graph` and `Assign colors`.
- **§12 Stream Hierarchy:** support Strahler, Shreve, Hack, Custom weighting — **user selectable**.
- **§13 Watersheds:** support HUC2, HUC4, HUC6, HUC8, HUC10, HUC12 — **selectable**.
- **§27 Logging:** rich terminal output; report statistics.
- **§30 Code Quality:** type hints, docstrings, DI, no global state, unit tests.

## Design Notes / Decisions

- **Input seam:** `context.artifacts["hydro_graph"]` — the directed `MultiDiGraph` from item #5, with per-edge `segment_id`, `geometry`, `length` (and, added here, `huc4`).
- **Stream ordering is pure graph computation:** Strahler/Shreve/Hack computed by processing the DAG in topological order; fully testable with hand-built networks.
  - *Strahler:* source segments = 1; at a confluence, order increments only when the two highest incoming orders are equal.
  - *Shreve:* additive magnitude (sum of incoming; sources = 1).
  - *Hack:* main-stem = 1 growing outward to tributaries; main channel chosen by greatest cumulative upstream length (computed forward, assigned reverse).
  - *Custom:* a weight function over edge data (default: cumulative upstream length) — the extensibility hook for §12 "custom weighting".
- **Selectability via config:** add a `stream_method` field (allowlist strahler/shreve/hack/custom, default `strahler`) and a `huc_level` field (allowlist HUC2–HUC12, default `HUC4`), each with a CLI flag. This is the minimal, honest way to satisfy "user selectable".
- **Watershed grouping by HUC prefix:** HUC codes are hierarchical prefixes. Each segment inherits its source `huc4`; grouping truncates to the selected level's digit count. HUC2/HUC4 are fully supported from HUC4 data; **finer levels (HUC6–HUC12) require sub-HUC boundary polygons we do not yet load, so they degrade to HUC4 grouping with a warning** — the function is structured so finer data drops in later without API change.
- **Carry `huc4` on graph edges:** the grouping needs each segment's HUC; add `huc4` to edge attributes in `build_graph` so grouping reads it directly (no fragile re-derivation).

## Open Questions (resolve during implementation)

- Hack main-channel tie-breaking: use cumulative upstream length; ties broken deterministically (stable max).
- Whether `compute_watersheds` should also filter by the existing `stream_order` ("all") config — no: that filter is a *rendering* concern (item #8). This item only computes orders and groups.
