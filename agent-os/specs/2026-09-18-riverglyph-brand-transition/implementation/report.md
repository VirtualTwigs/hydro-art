# Implementation Report — Riverglyph Brand Transition (Epoch 31)

_Completed: 2026-09-18_

## Summary

Migrated the public product identity from Hydro-Art to Riverglyph across the
entire presentation surface. This is presentation-only — no pipeline changes, no
`Settings` shape changes, no rendered artifact byte changes. Suite 1151 green,
recipe roundtrip green, `PIPELINE_STAGES` untouched.

## What shipped

### #137 Brand foundation

- **8 brand asset files** under `web/brand/`: wordmark, lockup, icon, print
  (single-color black), reversed (Field Paper on Watershed Ink), favicon SVG,
  social-preview PNG (1200×630), plus `web/favicon.ico` (multi-size ICO).
- **`web/shared/brand.css`** — canonical `:root` tokens: River Teal `#176C70`,
  Watershed Ink `#142923`, Field Paper `#F4F2E9`.
- **Token migration** in `editorial.css` (4 variables: `--accent`, `--ink`,
  `--panel`, `--ok`) and `ux.css` (4 variables: `--accent`, `--accent-dim`,
  `--bg`; `--accent-2` removed). Both files import `brand.css`.
- Legibility verified: River Teal on Watershed Ink dark background passes for
  interactive elements. An `--accent-light` was introduced for focus rings.

### #138 Public customer-surface pages (6 pages)

`start.html`, `order.html`, `proof.html`, `delivery.html`, `gallery.html`,
`report.html` — all titles, nav wordmarks, headings, favicon/OG meta migrated.
Footer "Produced by Runde Strategies" preserved. Technical schema strings
(`hydro-art/gallery-ledger@1`) unchanged. Recipe roundtrip green.

### #139 Studio, operations, and prototypes (4 pages)

`studio.html`, `ops.html`, `proto-b-guided.html`, `proto-c-canvas.html` —
titles and headings migrated. Dark theme legibility confirmed.

### #140 Email + test assertions (only `src/` change)

- `src/email_delivery.py`: subjects and HTML bodies updated from `Hydro-Art` /
  `Hydro◇Art` to `Riverglyph`. Footer "produced by Runde Strategies" preserved.
- `tests/test_email_delivery.py`: assertion strings updated to match.
- `tests/e2e/tests/01-landing.spec.js`: title regex updated, visual smoke check
  added for wordmark at 1280px and 375px widths.

### #141 Launch gate (implementation portion)

- `fulfillment-pack/listing.md` already uses Riverglyph brand name.
- Suite: 1151 tests passing. Recipe roundtrip green.
- `PIPELINE_STAGES` untouched — 2D default build byte-identical.
- Technical identifiers stable: `HYDRO_ART_*`, `hydro-art/*`, `HydroUX`.

## What's deferred

All deferred items are business clearance, not code:

- **Domain registration** (`riverglyph.com`) — external action.
- **Trademark clearance** (Class 16 / Class 9) — external action.
- **Full public-path walkthrough** — needs running server with GIS stack.
- **Go-live date recording** in `revenue-ledger.md` — blocked on listing
  publication, which is blocked on business clearance above. This starts the
  Epoch 11.5 #59 60-day measurement window.

## Invariants verified

1. **Byte-identical renders** — no `PIPELINE_STAGES`, `Settings`, or rendering
   changes.
2. **Offline suite green** — 1151 tests, only `test_email_delivery.py` changed.
3. **Recipe roundtrip green** — `hydro-ux.js` untouched, `HydroUX` namespace
   stable.
4. **Historical data intact** — no order JSON or event log rewriting.
5. **Technical identifiers stable** — `HYDRO_ART_*` env vars, `hydro-art/*`
   schemas, Docker names unchanged.

## Files changed

| Category | Files |
|---|---|
| New brand assets | `web/brand/` (8 files), `web/favicon.ico` |
| New CSS | `web/shared/brand.css` |
| CSS migration | `web/shared/editorial.css`, `web/shared/ux.css` |
| Public pages | `web/start.html`, `web/order.html`, `web/proof.html`, `web/delivery.html`, `web/gallery.html`, `web/report.html` |
| Internal pages | `web/studio.html`, `web/ops.html`, `web/proto-b-guided.html`, `web/proto-c-canvas.html` |
| Email copy | `src/email_delivery.py` |
| Tests | `tests/test_email_delivery.py`, `tests/e2e/tests/01-landing.spec.js` |
| Listing | `agent-os/specs/.../fulfillment-pack/listing.md` |
| Docs | `HANDOFF.md`, `agent-os/product/roadmap.md` |

## TDD sequence

TG5 followed the spec's TDD discipline:
1. Updated test assertions to expect `Riverglyph` → tests failed (expected).
2. Updated `src/email_delivery.py` → tests passed.
3. Updated e2e title regex.
4. Full suite: 1151 green, no regressions.
