# Retrospective — Epoch 13: Web watershed-report view (#55)

_Closed 2026-09-16. Graded against the pre-registered watch-list in
`agent-os/specs/2026-08-30-watershed-report-analytics/planning/pre-analysis.md`
section C (the CSS/JS rules for the web view). Epoch 13 was carved out of the
Epoch 12 spec (`9b41806`) as a single-item epoch for the web report surface._

## What the epoch was

Item #55: build `web/report.html` — a browser-native watershed report view over
the shared `web/shared/*` foundation (CSS design tokens + JS helpers). Metric
tiles, a model-vs-gauge validation badge, a long-record sparkline, an ENSO overlay
toggle, and a typical-year band chart — all driven by a deterministic sample report
document exported from `hydro-ux.js`, not by live computation. No `src/` change, no
`PIPELINE_STAGES` touch, no GIS dependency. The page opens over `file://` like
every other `web/` page.

Originally Group 8 of the Epoch 12 watershed-report spec, #55 was split into its
own epoch in the `9b41806` refactor (2026-09-01) that also merged
`flow_validation.py` into the combined `flow_metrics.py`. The implementation
shipped earlier in `3838539` (2026-08-30), then the roadmap was restructured to
recognize it as a standalone epoch.

## What shipped

- **`web/report.html`** (276 lines) — the full report page: brand header with
  watershed name + date range, a `.report-grid` of four `.metric-tile` cards (peak
  flow, summer low, center-of-timing, flashiness), a `.validation-badge` showing the
  model-vs-gauge verdict with r/NSE, a `.chart-card` long-record sparkline with
  trend arrow, a typical-year mean-plus/minus-sigma band chart, and an ENSO scatter
  overlay toggle. All data sourced from `HydroUX.sampleReport()` — a fixed,
  deterministic sample document so the page renders identically every load.
  Commit `3838539`.

- **`web/shared/ux.css`** (+42 lines) — five shared report components added to the
  existing shared stylesheet, not duplicated per page:
  `.report-grid` (responsive card grid), `.metric-tile` (headline number with
  eyebrow label + unit), `.validation-badge` (verdict pill using `--ok`/`--warn`/
  `--danger` status tokens), `.chart-card` (framed chart container), `.sparkline`
  (inline trend mark). All colors from existing design tokens, no hard-coded hexes.
  Commit `3838539`.

- **`web/shared/hydro-ux.js`** (+115 lines) — six pure, Node-loadable report
  helpers: `ordinal(n)` (1st/2nd/3rd/4th), `trendArrow(slope)` (up/down/flat
  glyph), `fmtNum(v, decimals)` (trailing-zero trim, non-finite to em-dash),
  `verdictClass(verdict)`/`verdictLabel(verdict)` (map good/moderate/weak to
  ok/warn/danger CSS tokens), `sparklinePoints(values, w, h, pad)` (normalize into
  an SVG box, y-inverted, NaN dropped not zero-filled, flat series centered),
  `buildSparkline(values, opts)` (self-contained `<svg>` string with path + last-point
  dot), `sampleReport()`/`REPORT_SAMPLE` (deterministic fixed-seed sample document:
  34 years of peak/low/COT/flashiness, validation verdict, typical-year band, ENSO
  scatter data). All stay Node-loadable — no top-level `document` or `window`.
  Commit `3838539`.

- **`tests/test_report_helpers.cjs`** (94 lines, 8 tests) — headless Node test
  harness covering `ordinal`, `trendArrow`, `fmtNum`, `verdictClass`/`verdictLabel`,
  `sparklinePoints` (normalization, NaN dropping, flat/empty), `buildSparkline`
  (SVG structure, empty-series safety), `REPORT_SAMPLE` (determinism, shape
  assertions — 34 years, 12 months, valid verdict). Stdlib `node` only, no deps.
  Commit `3838539`.

- **Roadmap/bookkeeping:** `9b41806` restructured the roadmap to create Epoch 13 as
  a standalone epoch for #55, updated HANDOFF.md, and amended the Epoch 12
  retrospective to reference the split.

### Commit log

| Hash | Description |
|------|-------------|
| `3838539` | `feat(#55): web watershed-report view over the shared foundation (Epoch 12)` |
| `9b41806` | `refactor(#48-#55): merge flow_validation into flow_metrics; split web view to Epoch 13` |

Later extended by Epoch 17 (`ae59bd3`, +5 panels, +5 node tests in
`test_report_web.cjs`) — that work belongs to Epoch 17's retrospective, not this
one.

## Real-data findings

Epoch 13 is a pure view-layer epoch — no GIS, no network, no real datasets. The
"real data" surface is the deterministic sample document (`REPORT_SAMPLE`) that
populates the page. There was no real-run bug to surface because the page has no
external I/O; the riskiest path (sparkline normalization on degenerate inputs —
empty, flat, NaN-heavy) was covered by the headless Node tests.

The one integration finding came later when Epoch 17 extended the report: the
flow-only sample document could not supply precip/temp arrays for the snow-regime
badge (#69), so that panel rendered as a synthetic mock. This confirmed the
pre-analysis section C rule that `sampleReport()` must carry every field a panel
reads — a constraint Epoch 13's original five panels satisfied but Epoch 17's
regime badge could not without a richer data model.

## Invariants held

- **Offline suite:** 1027 passing (as of today's run; 630 at Epoch 12/13 close).
  No regressions attributable to Epoch 13 — it touched no `src/` code.
- **Node harnesses:** `test_report_helpers.cjs` 8 passing,
  `test_recipe_roundtrip.cjs` 11 passing.
- **2D default output byte-identical:** yes. Epoch 13 added no `src/` module, no
  pipeline stage, no config change. The page is a standalone `web/` artifact.
- **`PIPELINE_STAGES` untouched:** yes — not even adjacent.
- **Rights gate:** N/A. The web report view displays a synthetic sample document; it
  does not derive from PRISM, NHD, or any data source requiring attribution.
- **`hydro-ux.js` Node-loadable:** yes — no top-level `document`/`window`;
  `test_report_helpers.cjs` loads it headlessly via `require()` and passes.

## Graded against pre-analysis

The pre-analysis (`planning/pre-analysis.md` section C) set three rules for the web
report view. All held:

1. **"New report components live in `web/shared/ux.css`; pages only use classes."**
   Held. All five components (`.report-grid`, `.metric-tile`, `.validation-badge`,
   `.chart-card`, `.sparkline`) are in `ux.css`. `report.html` applies classes, does
   not define new styling.

2. **"Any report data/formatting helper lives in `web/shared/hydro-ux.js` and stays
   Node-loadable."** Held. Six helpers exported on `HydroUX`; all tested headlessly
   in `test_report_helpers.cjs` (8 tests). No browser globals at module scope.

3. **"Colors come from tokens, never hard-coded hexes."** Held. The validation badge
   uses `--ok`/`--warn`/`--danger`; metric tiles use `--panel-2`/`--accent`; the
   sparkline stroke inherits `--accent`. No hex literal in the report CSS or JS.

The broader watch-list items (1-7) are graded in the Epoch 12 retrospective
(`2026-08-31-epoch-12-watershed-report.md`), which covers the full #48-#55 scope.
Epoch 13's scope is narrow enough that only section C applies directly.

## What went well

- **The shared-foundation investment paid off.** Because `ux.css` already had design
  tokens and `hydro-ux.js` already had the recipe/preset/CLI-mapping architecture,
  the report view was a clean extension — 42 lines of CSS, 115 lines of JS, 177
  lines of HTML. No framework, no build step, no new dependencies.

- **Node-testable by design.** The decision to keep all report logic as pure
  functions (no DOM manipulation at module scope) meant every helper was testable
  headlessly the moment it landed. The 8-test harness runs in under a second with
  stdlib `node`.

- **The `sampleReport()` pattern.** Shipping a deterministic, fixed-seed sample
  document means the page renders identically on every load and is testable without
  a server or real data. This pattern was later reused by Epoch 17 for its five
  additional panels.

- **Single-item epoch kept scope honest.** Carving #55 out of Epoch 12 into its own
  epoch avoided the temptation to bundle unrelated follow-on work (multi-watershed
  comparison, live re-computation) into the same close.

## Carry-forwards

- **No live browser render check** was performed during the original implementation
  session — no Chrome extension was connected. The page was verified structurally
  (inline script parses under `node --check`; all `doc.*` fields panels read are
  present in `sampleReport()`) but not visually rendered. The Epoch 24 Playwright
  harness (`f01a0c3`) later exercised `web/report.html` as part of the alpha
  customer-journey gate and confirmed it loads and renders, partially closing this
  gap.

- **The report view renders from a synthetic sample document**, not from a real
  watershed's metrics. Wiring a real `flow_metrics` export (JSON) into the page so
  it can display an actual watershed is deferred — the page is currently a
  deterministic demo/proof-of-concept.

- **Multi-watershed comparison / picker UI** is explicitly out of scope (per
  `planning/ux.md` section 4) and remains deferred.

## Lessons

- **View-layer epochs are fast when the foundation exists.** The entire epoch was
  one commit (plus bookkeeping). The shared `ux.css` tokens and `hydro-ux.js`
  architecture — established in Epochs 6 and 9 — made the report view a composable
  assembly rather than a ground-up build. This validates the Epoch 9 investment in
  extracting shared helpers proactively.

- **Carve single-concern items into their own epochs** when they have a clean
  boundary. #55 had zero `src/` dependency and zero interaction with the rest of
  Epoch 12's analytics work. Making it a separate epoch gave it a clean close
  without blocking on (or being blocked by) the heavier #48-#54 items.

- **Test the sample document's shape, not just the helpers.** The
  `REPORT_SAMPLE is deterministic and well-shaped` test (asserting year count,
  month count, valid verdict) caught a potential drift hazard: if a panel reads a
  field that `sampleReport()` does not produce, the test fails before the browser
  does. This discipline was validated when Epoch 17 added panels that needed fields
  the original sample did not carry.

---

_Bookkeeping reminder for the orchestrator: confirm `HANDOFF.md` and
`agent-os/product/roadmap.md` reflect the same Epoch 13 close — #55 is `[x]` in
the roadmap with the epoch marked complete._
