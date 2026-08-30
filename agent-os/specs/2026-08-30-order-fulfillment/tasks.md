# Tasks — Order fulfillment tooling (#56–#57, Epoch 11.5)

Legend: `[x]` done · `[ ]` todo. Offline groups ship **tests-first** (write 2–8
tests per group, run ONLY those, then implement). `tools/` group is non-offline
(closeout = smoke-run + note). Hard invariant at closeout: full suite green + 2D
default output byte-identical.

## Group 1 — Order model & validation (#56/#57) · offline

- [x] 1.1 Write `tests/test_fulfillment.py` first (see spec "Unit test design" G1):
  valid OR/WA/CA/ID payloads → frozen `Order`; parametrized rejections (bad region /
  empty county / missing `order_id` / empty or bad `formats` / unknown style / size /
  add-on) → `OrderError`; title/subtitle capping; payload not mutated; `Order` frozen;
  **Rights gate** — injected `uses_prism=True` style → `OrderError` via `build_order`
  and `assert_sellable`.
- [x] 1.2 Implement `src/fulfillment.py` catalogs + value objects + `build_order` +
  `assert_sellable` (stdlib only; import `SUPPORTED_REGIONS` from `src.config`;
  `__all__`; `from __future__ import annotations`).
- [x] 1.3 Run only these tests.

## Group 2 — Title block & attribution (#57) · offline

- [x] 2.1 Extend `tests/test_fulfillment.py` (G2): `attribution_line` exact default
  string + versioned + sort-stable + non-empty; `title_block` explicit vs. defaulted
  (county+region), whitespace-collapse + cap; credit == attribution; determinism.
- [x] 2.2 Implement `attribution_line`, `default_title`/`default_subtitle`,
  `title_block` in `src/fulfillment.py`.
- [x] 2.3 Run only these tests.

## Group 3 — Deliverable plan (#56/#57) · offline

- [x] 3.1 Extend `tests/test_fulfillment.py` (G3): png+pdf @ `18x24` → 2 print items
  with `(5400,7200)` px + deterministic filenames; `svg` add-on flags editable SVG;
  `commercial_license` add-on flags license doc; add-on input-order-independence.
- [x] 3.2 Implement `Size.px`, `Deliverable`, `DeliverablePlan`, `deliverable_plan`.
- [x] 3.3 Run only these tests.

## Group 4 — Fulfillment manifest (#57) · offline

- [x] 4.1 Extend `tests/test_fulfillment.py` (G4): manifest carries order + title
  block + attribution + per-deliverable sha256; `sources[]` provenance; `sort_keys`
  byte-identical for equal inputs; checksum coverage mismatch → `OrderError`.
- [x] 4.2 Implement `fulfillment_manifest` (stdlib `json`, sorted, injected
  `checksums`).
- [x] 4.3 Run only these tests.

## Group 5 — Non-offline executor (#56/#57) · outside the suite

- [x] 5.1 `tools/fulfill_order.py`: `--order order.json`/flags → `build_order` →
  dispatch on `StyleSpec.renderer` (`pipeline` → county `Settings`+`Pipeline`/
  `render_county_clip`; `mono` → hypsometric path) → stamp `title_block` → export
  each `deliverable_plan` item at `Size.px` (reuse `src.export`/`rasterize_layered`)
  → write `license.txt` for the license add-on → sha256 → `fulfillment_manifest` →
  `<order_id>.manifest.json`. Imports GIS libs eagerly; not in the suite.
- [x] 5.2 Smoke: fulfill a sample Clark County, WA order (`neon-basin`, `18x24`,
  png+pdf, +svg +license) end-to-end; eyeball the stamped title/subtitle/credit;
  confirm the manifest re-runs byte-identical (reproducible re-order). _Byte-identical
  after pinning `SOURCE_DATE_EPOCH` on the `rsvg-convert` PDF export (cairo was stamping
  a wall-clock CreationDate)._
- [x] 5.3 Add the two approved order presets to the fulfillment pack docs; drop a
  filled sample `order.json` next to the tool.

## Group 6 — Close out · offline

- [x] 6.1 Run the full suite (regression) + `node tests/test_recipe_roundtrip.cjs`;
  confirm the 2D default output byte-identical (no `PIPELINE_STAGES` touched).
- [x] 6.2 `ruff check src tests` on the new module + tests.
- [x] 6.3 `implementation/report.md`; add `src/fulfillment.py` to the CLAUDE.md
  module map + `tools/fulfill_order.py` to the ad-hoc tools section; tick roadmap
  #56/#57 (code core; listing/ops stay in the ledger); update `HANDOFF.md`.
