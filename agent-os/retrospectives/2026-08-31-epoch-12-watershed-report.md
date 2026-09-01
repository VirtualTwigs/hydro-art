# Retrospective — Epoch 12: Watershed report analytics (#48–#55)

_Closed 2026-08-31. Graded against the pre-registered watch-list in
`agent-os/specs/2026-08-30-watershed-report-analytics/planning/pre-analysis.md`
(written before implementation, per the Epoch 8/9 practice)._

## What the epoch was

Promote the one-off `notebooks/salmon_creek_yoy.ipynb` (real PRISM year-over-year
flow for a HUC12 group) into a reusable, **credible** watershed report: deeper
temporal record, honest model-vs-gauge validation, climate-driver attribution,
spatial decomposition, a parametrized report builder, and a web report view.
Mirrors the #23/#25/#44 precedent — pure statistics into offline numpy-only `src/`
modules, heavy external reads in `tools/` behind injectable provider seams. Hard
invariant: the 2D pipeline and its byte-identical default output are untouched
(these modules are not in `PIPELINE_STAGES`). Held.

## What shipped

- **#48/#49/#53** — `src/flow_metrics.py` (numpy-only, offline): per-year peak /
  summer-low, center-of-timing, Richards-Baker flashiness, seasonal ratio, monthly
  flow-duration percentiles (#48); Mann-Kendall + Sen's slope, percentile rank,
  anomaly, rolling 30-yr normals (#49); `subset_series` / `outlet_index` /
  `longitudinal_profile` spatial helpers (#53). Tested in `tests/test_flow_metrics.py`.
- **#50/#51** — folded into the combined `src/flow_metrics.py` (numpy-only, offline):
  bias / Pearson r / Nash-Sutcliffe / RMSE / per-month seasonal skill (nan months
  skipped, never zero-filled — mirrors `src/accuracy.py`) + `validate`→`ValidationReport`
  verdict (#50); `align_index` / `correlate` (+ lag) teleconnection helpers (#51). Tested
  in `tests/test_flow_metrics.py`. Non-offline providers behind the seam:
  `tools/nwis_gauge.py` `GaugeProvider` (USGS NWIS monthly means + site location,
  NAS-snapshotted) and `tools/climate_index.py` `ClimateIndexProvider` (ENSO ONI /
  PDO, snapshotted).
- **#52** — PRISM back-catalog: `tools/prism_fetch.py --start/--end` span (idempotent,
  resumable, mount-aware); no engine change. Staged the gauge-era 1944–1989 span for
  HUC4 1708 alongside the existing 1990–2023.
- **#54** — `tools/report_common.py` (shared load + reach selection + 7-panel
  matplotlib recipe) + `tools/build_watershed_report.py` CLI; `notebooks/
  salmon_creek_yoy.ipynb` refactored to consume `report_common` (no forked stats or
  plotting).
- **#55** — Web report view: `.metric-tile`/`.report-grid`/`.validation-badge`/
  `.chart-card`/`.sparkline` added to `web/shared/ux.css`; report data/formatting
  helpers in `web/shared/hydro-ux.js` (Node-loadable); `web/report.html`; headless
  `tests/test_report_helpers.cjs`.

## Grading the watch-list

1. **Validation is the credibility hinge (#50).** *Graded — the headline finding.*
   Thresholds were fixed up front (moderate = NSE≥0.5 & r≥0.7). The first run scored
   the **basin outlet** against the gauge → r=0.80 but NSE=−9.86, bias=+166.9 cfs:
   the outlet is the basin mouth ~23 km downstream, a ~3.7× larger drainage than the
   mid-watershed Battle Ground gauge — never apples-to-apples. **Fix:** snap the
   comparison to the model reach *at the gauge* (`gauge_reach_index` via the NWIS site
   location, idx 597, 10.3 m away). Snapped: **r=0.78, NSE=+0.50, bias=+18.6 cfs,
   RMSE=44.9** — bias collapsed 9×. Verdict stays "weak" only because NSE=0.4993 misses
   the 0.50 cutoff by 0.0007. Honest framing recorded: the model reproduces gauge
   *timing and magnitude* at the gauge site; it was being scored at the wrong drainage
   point, not overpredicting. This is the epoch's most important lesson — a validation
   number is meaningless without matching the drainage area.
2. **External-data reproducibility.** *Held.* Every fetch (NWIS dv + site, PRISM grids,
   ONI/PDO tables) is snapshotted to the NAS with a manifest; the report rebuilds
   offline from snapshots. The notebook re-executes from the staged snapshots + caches.
3. **Statistical rigor on short, autocorrelated series (#49).** *Held.* Trends now run
   on the 46-yr gauge-era record (1944–1989), not 10 points; the OLS-on-10-points
   "5-year projection" was removed. Long-record annual-mean trend: "none" (τ=−0.02,
   p=0.87); summer-low: "none" — reported honestly as no significant trend.
4. **PRISM back-catalog volume & staging (#52).** *Held.* 816 grids for the 1990–2023
   span (34 yr × 12 mo × 2 vars) staged under `<root>/prism/<var>/`, NAS, resumable;
   the 1944–1989 gauge-era span staged for validation.
5. **Offline fakes can't verify real external paths.** *Held.* The non-offline smokes
   (3.5, 4.4, 5.2, 7.4) all ran on real data and their real numbers are recorded in
   the spec `tasks.md`, not stood in for by offline-green.
6. **Spatial over-claim (#53).** *Held.* PRISM 4 km over 239 km² ≈ 15 cells — the
   intra-basin signal is weak; the report leads with the *temporal* story and the map
   carries the resolution caveat.
7. **Scope-creep / purity leak.** *Held.* the combined `src/flow_metrics.py`
   imports numpy only; the offline suite (630 tests) stays
   GDAL/network-free and the 2D default output is byte-identical (no `PIPELINE_STAGES`
   touched).

## What went well

- **Pre-registered validation thresholds paid off** exactly as the Epoch 8 retro
  predicted for its latitude bug: because good/moderate/weak were fixed *before* the
  numbers appeared, the outlet-vs-gauge mismatch surfaced as an obviously-wrong NSE
  rather than being quietly reframed. The reach-snapping fix followed the evidence.
- **The one-recipe rule held.** `report_common` is the single load+plot surface; the
  notebook is now a thin driver (its old hand-rolled load/plot code is gone), so the
  Epoch 9 copy-paste hazard was pre-empted, not cleaned up after the fact.

## Gotchas found

- **`report_common` uses repo-root-relative paths** (`output/…`, `notebooks/figures/`)
  because that's how `build_watershed_report.py` is invoked. A notebook executed by
  `jupyter nbconvert` runs with CWD = the notebook's directory, so the setup cell must
  `os.chdir(REPO)` or the clip/network caches miss and it falls through to a live WBD
  read. (Fixed in the refactored notebook's setup cell.)
- **No active gauge covers 2014–2023** for Salmon Creek — 14212000 was discontinued
  1990 — so the recent-art span (2014–2023) and the validation/deep-record span
  (1944–1989) are necessarily different windows.

## Carry-forward

- The report and every PRISM-derived animation are **not sellable** until the PRISM
  commercial-use arrangement is documented (roadmap Rights gate) — this epoch is
  research / product discovery, not near-term revenue.
- Byte-identical **full** `build.py` render compare still needs a GDAL host (shared
  carry-forward since Epoch 9/10); this epoch's invariant is satisfied structurally
  (no `PIPELINE_STAGES` code touched).
- Keep the retrospective + pre-analysis watch-list practice: the pre-registered list
  again caught the highest-risk item (validation framing) honestly.
