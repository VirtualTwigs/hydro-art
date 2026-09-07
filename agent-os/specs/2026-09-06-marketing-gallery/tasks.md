# Task Breakdown: High-resolution marketing gallery (Epoch 22, #88–90)

## Overview
Total: 4 task groups. A curated, rights-clean gallery: a pure/offline rights-ledger core over
the curated matrix, an opt-in high-res render harness (deferred real run), a self-contained web
surface, and a render-independent golden. Adds no art feature and no `PIPELINE_STAGES` change;
the default 2D build stays BYTE-FOR-BYTE identical; public-domain sources only.

## Cross-cutting constraints (apply to every relevant group)
- **TDD:** 2–8 focused tests FIRST per group; run ONLY those until green.
- **Offline discipline:** `src/gallery.py` + tests import ONLY stdlib + `src.endpoints` +
  `src.fulfillment`; NO GDAL/numpy/network/`web`/`tools`. `tools/render_gallery.py` lives
  OUTSIDE the suite; `web/gallery.html` has no build step.
- **Reuse, don't fork:** build each selection via `src.endpoints.build_endpoint_request`
  (Rights gate) + `endpoint_plan`; reuse `attribution_line`/`DEFAULT_SOURCES`; reuse the real
  renderer factories in `tools/render_endpoint.py`.
- **Byte-identical default:** no pipeline/renderer bytes change; verify before closing.

---

## Task List

### Task Group 1: Curated matrix + rights ledger — `src/gallery.py` (#88/#90)
**Dependencies:** Epoch 19 (`src/endpoints.py`)

- [x] 1.0 `GallerySelection` + `GALLERY_MATRIX` + `selection_request` + `gallery_ledger` + tests
  - [x] 1.1 Write tests FIRST in `tests/test_gallery.py`:
    - `GALLERY_MATRIX` spans all four regions, both styles, all four endpoints; unique item_ids.
    - every selection → a valid, sellable `EndpointRequest` via `selection_request`.
    - `gallery_ledger()` skeleton: schema `hydro-art/gallery-ledger@1`, one asset per selection
      (sorted by item_id), each with rationale + `sellable` True + planned deliverables + null
      sha256; byte-identical under `sort_keys`.
    - `gallery_ledger(checksums=...)` stamps sha256 and enforces exact per-asset coverage
      (missing/extra → `EndpointError`).
    - Run ONLY these tests.
  - [x] 1.2 Implement the dataclass, matrix, `selection_request`, `gallery_ledger`, schema,
    `__all__`.
  - [x] 1.3 Run ONLY the 1.1 tests until green.

**Acceptance:** matrix spans the range; every entry sellable; ledger byte-identical + coverage-
checked + Rights-gated; offline; green.

---

### Task Group 2: High-res render harness (opt-in, non-suite) — #89
**Dependencies:** Task Group 1

- [x] 2.0 `tools/render_gallery.py`
  - [x] 2.1 Author the CLI: `sys.path` insert → argparse (`--item`, `--out-dir`) → for each
    selection inject the real renderer factories from `tools/render_endpoint.py`, render full-res
    + a web-optimized derivative, sha256 both, stamp `gallery_ledger(..., checksums=...)`, write
    the ledger sidecar. Exit: `EndpointError`→1, render→2. Imports only `src/` +
    `tools.render_endpoint`.
  - [x] 2.2 Compile + import-check offline; real run deferred to GDAL+NAS (documented).

**Acceptance:** harness authored, imports clean, compiles, runs `--help`; outside the suite.

---

### Task Group 3: Web gallery surface — `web/gallery.html` (#90)
**Dependencies:** Task Group 1

- [x] 3.0 Self-contained gallery page
  - [x] 3.1 Build `web/gallery.html`: embedded sample ledger (+ optional `?ledger=` fetch),
    responsive card grid (region · style · endpoint, rationale, sellable badge, attribution,
    deliverables). `file://`-safe; DOM access inside function bodies only.
  - [x] 3.2 Structural sanity check (tag balance; JSON parses); note manual browser check.

**Acceptance:** page renders the ledger offline; no build step; no shared-JS breakage.

---

### Task Group 4: Golden fixture + regression gate (#90)
**Dependencies:** TG1–TG3

- [x] 4.0 Golden + gate + report
  - [x] 4.1 Generate `tests/fixtures/golden/gallery/ledger.json` from `gallery_ledger()`
    (render-independent) and commit it; add an in-suite test asserting the recomputed ledger
    equals the committed golden.
  - [x] 4.2 Run the FULL offline suite; confirm no new GDAL/network import in `src/`/`tests/`;
    default 2D build byte-identical.
  - [x] 4.3 Write `implementation/report.md`.

**Acceptance:** golden committed + match test green; full offline suite green; default build
byte-for-byte identical. Item gate: a rights-clean, high-res-ready gallery covering all four
endpoints is defined + provenance-ledgered + published on the web surface, each asset traceable
to a public-domain source — ready for Epoch 23 (release gate).

---

## Execution Order
1. Curated matrix + rights ledger (TG1).
2. High-res render harness (TG2).
3. Web gallery surface (TG3).
4. Golden fixture + regression gate (TG4).
