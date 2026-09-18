# Epoch 31 — Riverglyph Brand Transition retrospective (2026-09-18)

_Closed 2026-09-18. **No pre-registered watch-list** — the spec folder
(`2026-09-18-riverglyph-brand-transition`) carries `planning/requirements.md`,
`spec.md`, `tasks.md`, and `implementation/report.md`, but no
`planning/pre-analysis.md`. This is a narrative closeout. All five roadmap items
(#137--#141) shipped their code deliverables; #141 business-clearance items
(domain, trademark, public-path walkthrough, go-live date) are deferred and
honestly labeled below._

## What the epoch was

Migrate the public product identity from **Hydro-Art** to **Riverglyph** --
name, mark, color tokens, page titles, nav, headings, email copy, favicon, OG
meta -- across the entire presentation surface. Presentation-only by design: no
`PIPELINE_STAGES` edit, no `Settings` shape change, no rendered artifact byte
change, no new `src/` modules. The only `src/` file touched is
`src/email_delivery.py` (copy strings). All technical identifiers
(`HYDRO_ART_*`, `hydro-art/*`, `HydroUX`) remain stable until a separately
planned versioned migration.

## What shipped

### #137 -- Brand foundation

- **8 brand asset files** created under `web/brand/`: `riverglyph-wordmark.svg`,
  `riverglyph-lockup.svg`, `riverglyph-icon.svg`, `riverglyph-print.svg`
  (single-color black for physical print attribution),
  `riverglyph-reversed.svg` (Field Paper on Watershed Ink), `favicon.svg`,
  `social-preview.png` (1200x630 OG image).
- **`web/favicon.ico`** -- multi-size ICO (16/32/48).
- **`web/shared/brand.css`** -- canonical `:root` tokens: River Teal `#176C70`,
  Watershed Ink `#142923`, Field Paper `#F4F2E9`. Single source of truth;
  imported by both theme files.
- **Token migration in `editorial.css`** -- 4 variables (`--accent`, `--ink`,
  `--panel`, `--ok`) moved from hardcoded hex to `var(--brand-teal)` /
  `var(--brand-ink)` / `var(--brand-paper)`.
- **Token migration in `ux.css`** -- `--accent` from `#00ffff` to `#176C70`,
  `--accent-dim` derived from River Teal (`#0f4f52`), `--bg` from `#07080c` to
  `#142923` (Watershed Ink), `--accent-2` removed (no secondary accent in
  Riverglyph palette).
- **`--accent-light` introduced** in `ux.css` for interactive elements on dark
  fields -- River Teal on Watershed Ink was too low-contrast for focus rings
  without it. This is the epoch's "real surface finding": the spec predicted
  this risk explicitly (task 2.4) and it confirmed.

### #138 -- Public customer-surface pages (6 pages)

`start.html`, `order.html`, `proof.html`, `delivery.html`, `gallery.html`,
`report.html` -- all titles, nav wordmarks, headings, footer references
migrated. Favicon `<link>` (SVG + ICO) and OG meta (`og:title`,
`og:description`, `og:image`) added to all six. Footer "Produced by Runde
Strategies" preserved (legal entity, not product brand). Technical schema
strings (`hydro-art/gallery-ledger@1`) unchanged. Recipe roundtrip green after
each page.

### #139 -- Studio, operations, and prototypes (4 pages)

`studio.html`, `ops.html`, `proto-b-guided.html`, `proto-c-canvas.html` --
titles and headings migrated. Decision: migrate prototypes rather than archive
(minimal effort -- title + heading text only). Dark theme legibility confirmed
with the `--accent-light` token from #137.

### #140 -- Email + test assertions (TDD, only `src/` change)

- `src/email_delivery.py`: two subject lines updated (`Your Hydro-Art order` to
  `Your Riverglyph order`, `We received your Hydro-Art request` to `We received
  your Riverglyph request`). HTML body wordmark spans updated from
  `Hydro&#9671;Art` to `Riverglyph`. Footer "produced by Runde Strategies"
  preserved.
- `tests/test_email_delivery.py`: assertion strings updated to match Riverglyph.
  TDD discipline followed -- tests updated first, confirmed failure, then
  implementation, confirmed green.
- `tests/e2e/tests/01-landing.spec.js`: title regex `/Hydro-Art/i` to
  `/Riverglyph/i`; visual smoke check added for wordmark at 1280px and 375px.

### #141 -- Launch gate (code portion complete)

- `fulfillment-pack/listing.md` already uses Riverglyph brand name (updated
  during Epoch 11.5 fulfillment-pack work).
- Suite: 1151 tests passing, recipe roundtrip green.
- `PIPELINE_STAGES` untouched, 2D default build byte-identical.
- Technical identifiers stable: `HYDRO_ART_*`, `hydro-art/*`, `HydroUX`.
- HANDOFF.md and roadmap updated.

### Files changed

| Category | Files |
|---|---|
| New brand assets | `web/brand/` (8 files), `web/favicon.ico` |
| New CSS | `web/shared/brand.css` |
| CSS migration | `web/shared/editorial.css`, `web/shared/ux.css` |
| Public pages (6) | `start`, `order`, `proof`, `delivery`, `gallery`, `report` |
| Internal pages (4) | `studio`, `ops`, `proto-b-guided`, `proto-c-canvas` |
| Email copy | `src/email_delivery.py` |
| Tests | `tests/test_email_delivery.py`, `tests/e2e/tests/01-landing.spec.js` |
| Docs | `HANDOFF.md`, `agent-os/product/roadmap.md`, `fulfillment-pack/listing.md` |

_Not yet committed -- changes are staged in the working tree._

## Real-data findings

No real-data render run in this epoch by design -- this is a presentation
migration, not a pipeline change, so no GIS data or `build.py` invocation was
needed.

The one finding the implementation surfaced that the spec correctly predicted:
**River Teal (`#176C70`) on Watershed Ink (`#142923`) fails WCAG contrast for
small interactive elements** (buttons, focus rings) in the dark `ux.css` theme.
The spec (task 2.4) flagged this as a watch item and prescribed introducing
`--accent-light` if needed. It was needed. The fix is a lighter River Teal
derivative for interactive highlights on dark fields, introduced in `ux.css`
alongside the token migration. This is a presentation concern only -- no
pipeline or rendering impact.

## Invariants held

- **Offline suite:** 1151 passing (was 1151 -- no new tests added, only
  assertion strings updated in `test_email_delivery.py`). Zero regressions.
- **2D default output byte-identical:** yes. No `PIPELINE_STAGES` change, no
  `Settings` shape change, no renderer change, no `config.py` allowlist change.
- **`PIPELINE_STAGES` untouched:** yes. The only `src/` file touched is
  `email_delivery.py` (copy strings), which is outside the pipeline.
- **Recipe roundtrip:** green. `hydro-ux.js` untouched; `HydroUX` namespace
  stable.
- **Rights gate:** N/A (no new rendered assets, no new data sources). Existing
  `fulfillment.assert_sellable` enforcement unchanged.
- **Technical identifiers stable:** `HYDRO_ART_*` env vars, `hydro-art/*`
  manifest schemas, Docker/image names, `HydroUX` JS namespace -- all
  unchanged.
- **Historical data intact:** no order JSON, event log, or manifest rewriting.

## Graded against pre-analysis

No `planning/pre-analysis.md` exists for this spec, so there is no
pre-registered watch-list to grade against. The spec itself (section on #137
token migration) served as an informal watch-list by flagging the River Teal /
Watershed Ink contrast risk for dark themes. That prediction confirmed -- the
`--accent-light` mitigation was applied as prescribed.

Had a pre-analysis existed, the predictions would likely have been:

1. "CSS token migration will be mechanical and low-risk" -- **confirmed**. The
   migration was straightforward; both theme files reference `brand.css` tokens
   with no functional side effects.
2. "The only `src/` test impact is email assertion strings" -- **confirmed**.
   No other `tests/test_*.py` files needed changes.
3. "Dark-theme contrast may need a lighter accent" -- **confirmed and fixed**.

## Carry-forwards (honestly open, not passed)

- **Domain registration (`riverglyph.com`).** Business clearance, not code.
  Open.
- **Trademark clearance (Class 16 / Class 9).** Business clearance, not code.
  Open.
- **Full public-path walkthrough.** Landing to order to proof to payment to
  delivery with the Riverglyph identity visible at every step. Needs a running
  server with GIS stack -- not run in this session. Open.
- **Go-live date recording in `revenue-ledger.md`.** Blocked on listing
  publication, which is blocked on business clearance above. This starts the
  Epoch 11.5 #59 60-day measurement window. Open.
- **Technical identifier migration (`HydroUX` to `RiverglyphUX`, `HYDRO_ART_*`
  to `RIVERGLYPH_*`, repo/package rename).** Explicitly out of scope -- a
  separate versioned epoch. Open.
- **Physical print attribution layout.** The `riverglyph-print.svg` asset is
  provided; integrating it into the render pipeline's print export is a
  renderer concern, deferred.
- **No live byte-identical `verify_determinism.py` double-render was run.**
  Byte-identity rests on the "no renderer change" invariant -- same standing
  carry-forward inherited since Epoch 9/14/18.

## Lessons

- **Presentation-only epochs are fast and clean when the scope boundary is
  sharp.** The spec's "unchanged" list (env vars, schemas, Docker names,
  `HydroUX`, `PIPELINE_STAGES`, rendered bytes) made every implementation
  decision unambiguous. Zero scope creep.
- **Predicting the contrast risk in the spec paid off.** Task 2.4 explicitly
  called out River Teal on Watershed Ink and prescribed the `--accent-light`
  escape hatch. When the prediction confirmed, the fix was already designed --
  no improvisation needed.
- **Separating brand identity from technical identity was the right call.** The
  temptation to rename `HydroUX` or `HYDRO_ART_*` alongside the brand
  migration would have turned a zero-risk presentation epoch into a breaking
  change across every env var, every test, every config file. Deferring that to
  a versioned migration keeps this epoch risk-free.
- **TDD for copy changes is lightweight but valuable.** Updating
  `test_email_delivery.py` assertions first and watching them fail confirmed
  that the tests actually exercised the brand strings. Two minutes of work;
  full confidence the implementation matched.
- **Prototypes are worth migrating, not archiving.** `proto-b-guided.html` and
  `proto-c-canvas.html` are still referenced from alpha navigation. Migrating
  titles/headings (two lines each) was faster than reasoning about whether to
  remove nav links, and keeps the entire surface consistent.
