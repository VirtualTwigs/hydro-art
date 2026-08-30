# Implementation report — Order fulfillment tooling (#56–#57, Epoch 11.5)

_Date: 2026-08-30. Spec: `agent-os/specs/2026-08-30-order-fulfillment/`._

## What shipped

The reproducible, rights-compliant **fulfillment core** for made-to-order county
watershed prints — the codeable/testable substrate of Epoch 11.5's Revenue Validation
gate. No new rendering capability; nothing enters `PIPELINE_STAGES`; the 2D default
output stays byte-identical.

- **`src/fulfillment.py`** (new, stdlib-only, imports only stdlib + `src.config`
  `SUPPORTED_REGIONS`) — offline core:
  - Value objects (frozen): `StyleSpec`, `Size` (`.px` at DPI), `DataSource`, `Order`,
    `Deliverable`, `DeliverablePlan`; `OrderError` boundary type.
  - Catalogs (injectable via `styles=`/`sizes=`): `ORDER_STYLES` (the two approved
    PRISM-free directions `neon-basin`/`elevation-tint`), `SIZES` (12x16/18x24/24x36 @
    300 DPI), `PRINT_FORMATS`, `ADD_ONS`, `DEFAULT_SOURCES` (USGS NHDPlus HR/NHD/WBD).
  - `build_order` — validate-at-boundary/fail-fast against the allowlists, does not
    mutate the payload, returns a frozen `Order`, then `assert_sellable`.
  - `assert_sellable` — **Rights gate**: refuses any `StyleSpec.uses_prism` style.
  - `attribution_line` / `default_title` / `default_subtitle` / `title_block` — the
    deterministic stamped text block + name-sorted USGS source credit.
  - `deliverable_plan` — deterministic, add-on-order-independent file plan.
  - `fulfillment_manifest` — provenance manifest; checksums must cover the plan exactly
    (else `OrderError`); `json.dumps(sort_keys=True)` byte-identical for equal inputs
    (a re-order regenerates identically).

- **`tools/fulfill_order.py`** (new, non-offline executor, outside the suite) — thin CLI
  (`--order order.json` or flags) → `build_order` → dispatch on `StyleSpec.renderer`
  (`pipeline` → neon-basin county clip via `tools/render_common`; `mono` fails fast with
  a clear "use neon-basin" message pending a future slice) → stamp `title_block` into the
  SVG → export each `deliverable_plan` item at `Size.px` (PNG via `rasterize`, PDF via
  `rsvg-convert`, SVG add-on, license doc) → sha256 → `fulfillment_manifest` →
  `output/orders/<order_id>/<order_id>.manifest.json`. Imports GIS libs eagerly.

- **Docs / samples:** `sample_order.json` + `presets.md` (the two approved order presets,
  ready-to-run) in the spec folder.

## TDD — `tests/test_fulfillment.py` (29 tests, fully offline)

Four groups matching the spec's unit-test design, tests-first per group:
1. Order model & validation — supported regions → frozen `Order`; parametrized rejections
   → `OrderError`; title/subtitle cap+strip; payload not mutated; frozen; **Rights gate**
   (injected `uses_prism=True` style → `OrderError` via `build_order` and `assert_sellable`).
2. Title block & attribution — exact default attribution string, versioned, sort-stable,
   non-empty; `title_block` explicit vs. county/region defaults; determinism.
3. Deliverable plan — png+pdf @ 18x24 → 2 prints at (5400,7200) + deterministic names;
   svg/license add-ons flag correctly; add-on input-order-independence.
4. Manifest — carries order + title block + attribution + per-deliverable sha256 +
   `sources[]`; byte-identical `sort_keys`; checksum coverage mismatch → `OrderError`.

## Verification

- **Group closeout (offline):** the 29 `test_fulfillment.py` tests pass.
- **6.1 regression:** full suite **573 passed** (544 baseline + 29 new), no regressions;
  `node tests/test_recipe_roundtrip.cjs` → 11 passed. No `PIPELINE_STAGES` touched, so 2D
  default output is byte-identical by construction (the new module is a parallel,
  offline-only subsystem that no stage imports).
- **6.2 lint:** `ruff` is unpinned/absent by default (CLAUDE.md gotcha); installed it and
  checked the new files. The only findings are pre-existing **repo conventions**, not new
  issues: `RUF022` (`__all__` ordered by logical grouping, not alphabetically — 34 existing
  `src/` modules do the same) and `B017` (`pytest.raises(Exception)  # FrozenInstanceError`
  — identical to `tests/test_pipeline.py:94`). No new lint categories introduced.
- **5.2 smoke (real, non-offline):** fulfilled the sample Clark County, WA order
  (`neon-basin`, `18x24`, png+pdf, +svg +license) end-to-end against the real HUC4 1708
  GDB — clipped 11,374 flowlines, rendered a 3.3 MB master SVG, and wrote all 4
  deliverables + `ORD-1001.manifest.json`. The stamped title block reads correctly
  (`Clark County Watersheds` / `Washington · Hydrographic river network` /
  `Source: USGS NHD · USGS NHDPlus HR · USGS WBD`). Required staging the public Census
  cartographic-boundary county/state shapefiles that `render_common` expects under
  `/tmp/{counties,states}_shp` (not repo-tracked).
  - **Reproducible re-order:** the first re-run's manifest differed in exactly one line —
    the PDF's sha256 — because `rsvg-convert` (cairo) stamps a wall-clock PDF
    CreationDate. Fixed in `tools/fulfill_order.py` by pinning `SOURCE_DATE_EPOCH=0` on
    the `rsvg-convert` subprocess; two subsequent full runs now produce a **byte-identical
    manifest** (`ed669ae0…`), i.e. PNG/PDF/SVG/license all reproduce byte-for-byte.

## Notes / deferred

- The `elevation-tint` (`mono` renderer) executor dispatch is not yet wired — the core
  (order → plan → manifest) is fully tested, but `tools/fulfill_order.py` fails fast and
  points at `neon-basin`. A future slice can enable it without a catalog change.
- Listing (#56), the customer intake form, and funnel/ops tracking (#58) are operational
  work in `agent-os/product/revenue-ledger.md`, not code — #56/#57 stay `[ ]` on the
  roadmap with a status note recording that the code core landed.
