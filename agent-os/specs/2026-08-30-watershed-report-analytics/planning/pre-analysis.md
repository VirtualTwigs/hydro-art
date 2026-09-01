# Pre-analysis — Epoch 12 watch-list, common code, common CSS

Written *before* implementation (the ask), so the retrospective at close has a
pre-registered list to grade against — the discipline the Epoch 8 retro credited
for catching the latitude-drift bug ("the spec predicted the exact risk").

## A. Retrospective watch-list / risk register

Ordered by risk. Each names what to record so the closeout retro can grade it.

1. **Validation is the credibility hinge (#50).** The whole report's authority
   rests on the model-vs-gauge comparison. The disaggregation conserves NHDPlus
   *mean-annual* flow and shapes it with a simple temperature-index bucket — it may
   only *moderately* track the observed gauge.
   - **Decide the framing thresholds up front** (documented r/NSE → good/moderate/
     weak) so the verdict is honest, not retrofitted to whatever number appears.
   - **Record** the real bias/r/NSE/seasonal-skill for Salmon Creek and which
     framing fired. If weak: reframe "validated" → "climatology-consistent" and
     surface the metrics rather than burying them. This is the #1 thing the retro
     must report.

2. **External-data reproducibility (#50/#51/#52).** NWIS, PRISM, and the ENSO/PDO
   tables are live, queryable, revisable sources. The repo's determinism discipline
   (manifests, byte-identical output) is violated the moment a report depends on a
   live call.
   - **Snapshot every fetch** (raw response + a small manifest, mirroring
     `src/manifest.py`) to the NAS; the report must rebuild **offline from
     snapshots**. **Record** whether a second run from snapshots reproduces the
     figures.

3. **Statistical rigor on short, autocorrelated series (#49).** Mann-Kendall and
   Sen's slope assume independence; annual peak flow is autocorrelated, and on 10
   years any trend is noise. This is *why* #52 (backfill toward 1895) should land
   before #49 trends are headlined.
   - **Report bands, not point estimates.** **Record** the record length behind
     every trend claim and whether uncertainty is shown. Guard against re-shipping
     the notebook's "OLS-on-10-points 5-year projection" as if it were a forecast.

4. **PRISM back-catalog volume & staging (#52).** ~130 yrs × 12 mo × 2 vars ×
   basin cohort is many GB. Must stay on the NAS, mount-aware, resumable (the
   `feedback_large_file_storage` rule).
   - **Record** staged size + grid count + that an unmounted NAS degrades cleanly.

5. **Offline fakes can't verify the real external paths** (carried from the Epoch 8
   & Epoch 10 retros). The gauge/index correlations only *mean* something on real
   data; the NWIS parser and PRISM sampler have branches fakes never fire.
   - Keep the **non-offline smoke items** (3.5, 4.4, 5.2, 7.4) and **record the real
     numbers** — do not let "offline-green" stand in for the real run.

6. **Spatial over-claim (#53).** PRISM 4 km over a 239 km² basin ≈ 15 cells — the
   intra-basin signal is weak; the honest story is *temporal*.
   - **Record** that sub-watershed figures carry the resolution caveat and don't
     imply spatial structure the grid can't resolve.

7. **Scope-creep / purity leak.** The temptation is to let matplotlib, `requests`,
   or pandas creep into `src/`.
   - **Invariant to grade:** the combined `src/flow_metrics.py` imports **numpy
     only**; the offline suite stays GDAL/network-free and the 2D default output
     byte-identical.

## B. Common code (reuse map — avoid the Epoch 9 copy-paste drift)

The single biggest maintainability lesson in this repo (Epoch 9) was killing three
copies of `clip_flowlines`. This epoch pre-commits to shared surfaces:

- **One offline statistics layer.** the single combined `src/flow_metrics.py`
  is the *only* place hydrograph math lives. The notebook, the CLI report builder,
  and any web export consume it — **no stats logic in `notebooks/` or `tools/`.**
- **The injectable-provider pattern, reused.** `GaugeProvider` (NWIS) and the
  climate-index fetch follow the existing `ClimateProvider` seam (#44/#45): pure
  `src/` consumer, heavy read in `tools/`, fake in tests. Do not invent a new I/O
  shape.
- **One report recipe.** `tools/report_common.py` mirrors `render_common.py`: the
  shared data-loading + matplotlib recipe both the notebook and
  `tools/build_watershed_report.py` call. This is the pre-emptive fix for the exact
  hazard Epoch 9 #33 cleaned up — two report consumers must not fork the plotting.
- **Reuse existing infra, don't rebuild:** `src.historical_flow.yearly_flow_series`
  (the flow series), `src.rendering.fixed_flow_span`/`widths_on_span` (art widths),
  the `output/_yoy_net_<huc4>.pkl` network cache and the `render_common` clip cache,
  and `src/manifest.py`'s snapshot/verify pattern for the new external snapshots.
- **Every `src/<name>.py` gets `tests/test_<name>.py`** (the repo rule):
  `flow_metrics` → `test_flow_metrics.py` (the single combined module carries the
  #48/#49/#53 metrics and the #50/#51 validation tests together).

## C. Common CSS (web report view #55 — reuse `ux.css`, don't fork)

`web/shared/ux.css` already owns the design tokens (`--bg/--panel/--accent/--ok/
--warn/--danger/--radius/--mono` …) and shared components (`.badge .btn .chip
.legend .seg .swatches .timeline .stage` …). The report view **reuses these tokens
and layout primitives** and adds a small set of *shared* report components — placed
in `ux.css`, **not** duplicated per page (the Epoch 9 #36 view-helper rule):

- `.report-grid` — responsive card grid for the report body.
- `.metric-tile` — a single headline number (peak / summer-low / center-of-timing /
  percentile) with eyebrow label + unit; built on `--panel-2`/`--radius`.
- `.validation-badge` — model-vs-gauge verdict pill using the existing status
  tokens (`--ok` good / `--warn` moderate / `--danger` weak) so the honest framing
  is visible at a glance.
- `.chart-card` — framed container for an embedded chart (SVG/canvas) with a title
  row, matching `fieldset`/`legend` styling.
- `.sparkline` — inline long-record trend mark (minimal, token-colored).

Rules to hold (grade in the retro):
- New report components live in `web/shared/ux.css`; pages only *use* classes.
- Any report data/formatting helper (number/unit formatting, metric derivation,
  ENSO overlay toggle state) lives in `web/shared/hydro-ux.js` and stays
  **Node-loadable** (no top-level `document`/`window`), so
  `tests/test_recipe_roundtrip.cjs`-style headless tests keep running.
- Colors come from tokens, never hard-coded hexes — one product look across
  `studio.html`, the prototypes, and the new report page.
