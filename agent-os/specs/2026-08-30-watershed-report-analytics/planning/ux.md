# Proposed UX — Watershed report

Two surfaces share one content model: the **printed/notebook report** (the primary
deliverable, #54) and an optional **web report view** (#55). Both are driven by the
same offline metrics (the single combined `src/flow_metrics.py`) so they never
disagree.

## 1. Report narrative (notebook + `build_watershed_report.py`, #54)

A fixed, credibility-first section order — each section answers one question and
most reuse figures the Salmon Creek notebook already has, plus the new ones:

1. **Header + watershed map** — what/where (existing §5 map).
2. **How good is this?** *(new — the credibility anchor, up front)* model-vs-gauge
   validation: overlay modeled vs. observed monthly means at the gauge, with the
   `ValidationReport` verdict and metrics (bias / r / NSE). If weak, the honest
   "climatology-consistent, not gauge-accurate" framing shows here.
3. **The long record** *(new — needs #52)* peak / summer-low over ~130 years with a
   Mann-Kendall + Sen's-slope trend and an uncertainty band — replaces the
   OLS-on-10-points projection.
4. **Seasonality & low flow** *(new)* center-of-timing trend (are peaks shifting
   earlier?) and the summer-minimum series framed ecologically (salmon habitat:
   low flow × stream temperature).
5. **Why — climate drivers** *(new)* ENSO/PDO scatter: wet/dry years vs. ocean
   state.
6. **Within the watershed** *(new)* Upper vs. Lower sub-hydrographs + longitudinal
   accumulation, carrying the PRISM-resolution caveat.
7. **The art** — the neon year-over-year render (existing §10), wet vs. dry still.

Every figure lands in `notebooks/figures/`; the section order is the same whether
rendered in the notebook or by the CLI builder.

## 2. Web report view (#55) — over the shared foundation

Layout mirrors `studio.html`'s dense, token-driven look; **all** color/spacing from
`ux.css` tokens; **all** new components shared (see `planning/pre-analysis.md §C`).

```
┌───────────────────────────────────────────────────────────────┐
│  ⬡ hydro·art  Salmon Creek — Clark County, WA   1990–2023 ▾   │  brand + range
├───────────────────────────────────────────────────────────────┤
│  ┌ metric-tile ┐ ┌ metric-tile ┐ ┌ metric-tile ┐ ┌ badge ───┐ │
│  │ PEAK        │ │ SUMMER LOW  │ │ CENTER-OF-  │ │ vs GAUGE │ │  report-grid
│  │ 665 cfs     │ │ 0.1 cfs     │ │ TIMING  Mar │ │ ● MODER. │ │  (validation-
│  │ 92nd pct ▲  │ │ 4th pct ▼   │ │ −0.3 mo/dec │ │ r=0.71   │ │   badge tokens)
│  └─────────────┘ └─────────────┘ └─────────────┘ └──────────┘ │
├───────────────────────────────────────────────────────────────┤
│  ┌ chart-card: long-record peak + trend ─────────────────────┐ │
│  │  ▁▂▃▂▄▃▅▄▆▅▇▆  sparkline / full chart  ── Sen slope band  │ │
│  └───────────────────────────────────────────────────────────┘ │
│  ┌ chart-card: typical-year band ┐ ┌ chart-card: ENSO scatter┐ │
│  │  ◠◡ mean ±1σ                   │ │  ● wet ● dry vs ONI  [x]│ │  ENSO toggle
│  └───────────────────────────────┘ └─────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

- **Metric tiles** — headline numbers with an eyebrow label + trend arrow; the
  percentile-rank badge colors from status tokens.
- **Validation badge** — the single most important element: `● GOOD` (`--ok`) /
  `● MODERATE` (`--warn`) / `● WEAK` (`--danger`) with the r/NSE, so a viewer sees
  the model's honesty immediately.
- **Chart cards** — embed SVG/canvas charts (the client can reuse `hydro-ux.js`'s
  existing procedural SVG builder pattern); no new charting dependency.
- **Range selector + ENSO toggle** — the only interactive controls; state lives in
  the page's mutable `state`, formatting helpers in `hydro-ux.js`.

## 3. Interaction & data flow

- **File-first, like the other web pages.** The report view can render from a
  static JSON export of the metrics (a `delivery.py`-style document) so it opens
  over `file://`; a served mode (later) could pull live from the report builder,
  but that is not required for #55.
- **Determinism.** The JSON export is produced from snapshotted external data, so
  the same watershed+range always renders the same report.

## 4. Explicitly out of scope for now

- Multi-watershed comparison / picker UI (single-watershed report first).
- Live re-computation in the browser (metrics are computed by `src/` + exported).
- Map interactivity beyond the static watershed figure.
