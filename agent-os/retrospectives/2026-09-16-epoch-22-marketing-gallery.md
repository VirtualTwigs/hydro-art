# Retrospective — Epoch 22: High-resolution marketing gallery (#88-90)

_Closed 2026-09-06 (single commit `db42655`); retro written 2026-09-16. **No
pre-registered watch-list** — the spec folder
(`2026-09-06-marketing-gallery`) carries `planning/raw-idea.md`,
`planning/requirements.md`, `spec.md`, `tasks.md`, and
`implementation/report.md`, but no `planning/pre-analysis.md`. This is a
narrative closeout rather than a graded one. Fourth epoch of Generation 1
(Epochs 19-23, #79-93)._

## What the epoch was

Define a curated, rights-clean **marketing gallery** — a small set of examples
spanning every region, both public-domain styles, and all four production
endpoints — and a pure/deterministic **rights ledger** describing each asset's
provenance (source, attribution, planned deliverables, per-file checksum slot,
sellable flag). Reuses the Epoch 19 endpoint contract layer and the Rights gate
rather than forking render logic; the real high-res bytes are an opt-in harness
deferred to the GDAL+NAS machine. Adds no art feature and no `PIPELINE_STAGES`
change — the default 2D build stays byte-for-byte identical.

All three planned items (#88-90) shipped and the epoch closed on #90.

## What shipped (`db42655`)

### `src/gallery.py` (NEW, pure/offline, 179 lines)

- **`GallerySelection`** frozen dataclass (identity + per-endpoint params +
  `rationale`).
- **`GALLERY_MATRIX`** — five curated selections spanning all four regions, both
  public-domain styles, and all four endpoints:

  | item_id | region | county | style | endpoint |
  |---|---|---|---|---|
  | `or-neon-digital` | Oregon | Deschutes | neon-basin | digital_image |
  | `wa-elev-print` | Washington | Wahkiakum | elevation-tint | print_image (24x36) |
  | `ca-neon-animation` | California | Shasta | neon-basin | animation (year 2015) |
  | `id-elev-digital` | Idaho | Blaine | elevation-tint | digital_image |
  | `wa-neon-report` | Washington | Wahkiakum | neon-basin | report (HUC 17080003) |

- **`selection_request(sel)`** builds a payload and delegates to
  `src.endpoints.build_endpoint_request`, which enforces the Rights gate — so
  constructing the ledger fails fast on any non-sellable or invalid selection.
- **`GALLERY_SCHEMA = "hydro-art/gallery-ledger@1"`**;
  **`gallery_ledger(selections, *, checksums, sources)`** emits a per-asset
  provenance ledger: `{schema, attribution, sources, assets:[{item_id, region,
  county, style, endpoint, rationale, sellable, deliverables:[{filename, kind,
  fmt, width_px, height_px, sha256?}]}]}`. Assets sorted by `item_id`.
  `checksums` (optional) enforces exact per-asset coverage (missing/extra ->
  `EndpointError`); when absent, `sha256` is `None` (the render-independent
  skeleton). Byte-identical under `json.dumps(sort_keys=True)`.

### `tools/render_gallery.py` (NEW, non-offline, 122 lines)

Thin CLI: `--item` (subset), `--out-dir`, `--web-variants`. For each curated
selection, injects the four real renderer factories from
`tools/render_endpoint._renderers` into `dispatch_endpoint`, renders at
marketing/full resolution, optionally emits web-optimized derivatives (svg via
`SvgoOptimizer`, rasters downscaled via Pillow), sha256s all outputs, stamps
`gallery_ledger(..., checksums=...)`, and writes the ledger sidecar. Exit codes:
`EndpointError` -> 1, render failure -> 2. Compiles, imports clean, runs
`--help`. Real run deferred.

### `web/gallery.html` (NEW, self-contained, 233 lines)

`file://`-safe page: embedded sample ledger (the real `gallery_ledger()`
skeleton) with an optional `?ledger=<url>` fetch. Responsive card grid: region
and county, style/endpoint tags, rationale, "public-domain / sellable" badge,
attribution + schema line, and per-deliverable filename/dimensions. All DOM
access inside function bodies; no build step; no shared-JS breakage.

### `tests/fixtures/golden/gallery/ledger.json` (NEW, 163 lines)

The committed render-independent skeleton. Five assets, 11 deliverable
files total (2+2+2+3+2). Print-image asset carries pixel dims (7200x10800
for the 24x36 size); all others null. All `sha256` null (render-independent).

### `tests/test_gallery.py` (NEW, 91 lines, 6 test functions)

- `test_matrix_spans_regions_styles_endpoints` — 4 regions, 2 styles, 4
  endpoints, unique item_ids.
- `test_every_selection_is_valid_and_sellable` — every selection validates
  through `build_endpoint_request` + Rights gate.
- `test_ledger_skeleton_is_deterministic_and_byte_identical` — sorted assets,
  null sha256, `sort_keys` equality regardless of input order.
- `test_ledger_stamps_checksums_with_exact_coverage` — checksums flow through.
- `test_ledger_rejects_incomplete_checksum_coverage` — missing file raises
  `EndpointError`.
- `test_ledger_matches_committed_golden` — recomputed ledger equals the
  committed `ledger.json` byte-for-byte.

### Commit totals

11 files changed, 1112 insertions. Full offline suite at commit time: **839
passed** (+6 new gallery tests, no regressions).

## Real-data findings

No real-data run in this epoch by design. The spec explicitly scoped this as
"author offline, run later" — the real five-asset render of
`tools/render_gallery.py` against NHDPlus HR + 3DEP + nClimGrid data was
deferred to the GDAL+NAS machine. No bug-the-real-run-surfaced to report here;
the expected pattern (resolution drift, silent truncation, wall-clock PDF dates,
SMB chflags) would apply to the renderers injected at the harness level, not to
the pure gallery/ledger layer.

## Invariants held

- **Offline suite:** 839 passed (6 new), no regressions.
- **2D default output byte-identical:** yes. No `PIPELINE_STAGES` change, no
  renderer change — the epoch only curates and describes.
- **`PIPELINE_STAGES` untouched:** yes. The commit adds `src/gallery.py` and
  `tools/render_gallery.py` but touches no pipeline module.
- **Rights gate:** enforced. Every `GALLERY_MATRIX` selection routes through
  `build_endpoint_request` -> `assert_sellable`; both styles (neon-basin,
  elevation-tint) are PRISM-free, all five selections are `sellable: true`.
  Tested by `test_every_selection_is_valid_and_sellable`.

## Graded against pre-analysis

No `planning/pre-analysis.md` exists for this spec, so there is no
pre-registered watch-list to grade against. The spec's "Discipline / invariants"
section named three constraints:

1. **`src/gallery.py` offline (stdlib + `src.endpoints` + `src.fulfillment`).**
   Confirmed held — the module imports exactly those two `src` dependencies plus
   `dataclasses`/stdlib. No GDAL, no network.
2. **Nothing enters `PIPELINE_STAGES`.** Confirmed held — all 11 files are
   net-new and parallel to the pipeline.
3. **`tools/render_gallery.py` outside the suite; `web/gallery.html` no build
   step.** Confirmed held — neither is imported by `src/` or `tests/`.

## The reuse story

This epoch is a direct consumer of Epoch 19's `src/endpoints.py` — it calls
`build_endpoint_request` (validation + Rights gate) and `endpoint_plan`
(deterministic deliverable list) without re-implementing either. The ledger's
checksum-coverage enforcement mirrors the exact-coverage discipline from
`endpoint_manifest`. `attribution_line` and `DEFAULT_SOURCES` are imported from
`src/fulfillment.py`, not shadowed. The render harness delegates to the same
`dispatch_endpoint` + renderer factory pattern from `tools/render_endpoint.py`.
No new machinery was invented; the gallery is a thin curation layer over
existing contracts.

## Carry-forwards (honestly open, not passed)

- **No real five-asset render.** `tools/render_gallery.py` is authored, compiles,
  and runs `--help`, but has not been exercised against real NHDPlus HR / 3DEP /
  nClimGrid data on the GDAL+NAS machine. The child-tool CLI flags in the four
  renderer bodies need verification during a real run. The web-variants path
  (Pillow downscaling, svgo optimization) is similarly unexercised.
- **No live browser check of `web/gallery.html`.** Structural sanity was checked
  (tag balance, embedded JSON parses, filenames match the real ledger), but the
  page was not opened in a browser during this epoch. The Epoch 24 Playwright
  harness covers the landing and report pages but not the gallery page.
- **No live byte-identical `verify_determinism.py` double-render was run for
  this epoch.** Byte-identity rests on the "no renderer change" invariant, not a
  fresh double-render — matching the standing carry-forward.
- **Lint baseline.** `RUF022` (unsorted `__all__`) left consistent with the
  `src/fulfillment.py` and `src/endpoints.py` convention; the repo's ruff config
  does not enforce default RUF rules. Not a regression.

## Lessons

- **Thin curation layers ship fast and clean.** Because `src/gallery.py` is a
  pure consumer of two existing contract modules (endpoints + fulfillment), it
  was authored, tested, and committed in a single pass with no rework. The
  frozen-dataclass + Rights-gate-at-construction pattern means the gallery
  cannot drift from the endpoint contracts — if a contract changes, the gallery
  tests fail.
- **Golden fixtures are cheap insurance.** The committed `ledger.json` + the
  `test_ledger_matches_committed_golden` test means any inadvertent change to
  the curated matrix, the endpoint contracts, or the deliverable plan naming
  convention is caught immediately. The golden is render-independent (null
  sha256), so it never needs a GDAL host to regenerate.
- **"Author offline, run later" continues to work for contract/curation
  epochs.** As with Epochs 19 and 20, deferring the real render to the GDAL+NAS
  machine kept this epoch fast (one commit, 6 tests, no rework). The discipline
  is that the deferred work is named and documented, not silently dropped.
- **Consider adding a pre-analysis even for curation epochs.** No
  `pre-analysis.md` was written. The constraints were small and all held, but a
  pre-analysis would have made this retrospective a graded one rather than a
  narrative one — a recurring observation across Generation 1 epochs.
