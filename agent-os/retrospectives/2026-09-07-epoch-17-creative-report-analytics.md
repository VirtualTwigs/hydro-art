# Retrospective — Epoch 17: Creative report analytics (#69–#76)

_Closed 2026-09-07. **No pre-registered watch-list** — as with Epochs 16 and Generation 1,
the `2026-09-07-creative-report-analytics` spec folder carries only `planning/requirements.md`,
no `planning/pre-analysis.md`. This is a narrative closeout rather than a graded one; the
missing pre-analysis is again a process observation (see Lessons). Fourth epoch in a row
without the Epoch 8/9/12/14 pre-analysis step._

## What the epoch was

Deepen the Epoch 12 watershed **report** from seven figures into a richer, more *engaging*
climate story — "is my river snowmelt- or rain-driven, and is that shifting?" — drawing
**almost entirely on statistics the engine already computes** (`src/flow_metrics.py`,
`src/monthly_flow.py`) and data already staged (`{year:[n,12]}` monthly flow back to 1895,
USGS gauges, ONI/PDO indices). No new data source, no new Rights gate, nothing in
`PIPELINE_STAGES`, 2D default output byte-for-byte identical. It mirrored the Epoch 12/14
precedent exactly: promote pure, numpy-only stats into `src/` (offline-tested), keep heavy
external reads and figures in `tools/`, surface panels in `web/report.html` on the shared
`web/shared/*` foundation.

The shape of the epoch: **items #69–#75 are seven pure numpy-only statistics** added to
`src/flow_metrics.py` (with one refactor in `src/monthly_flow.py`), each shipped
one-at-a-time TDD (tests first, run only the relevant module, full suite at the end); then
**#76 is the assembly/surfacing item** touching `tools/` (matplotlib figures, outside the
suite) and `web/` (node-testable pure helpers). Eight items, eight commits (#72 and #73
shared one commit). The epoch closed on #76.

## What shipped

### #69 — Snow-vs-rain regime signature (`8cf3784`)

The disaggregation model already splits monthly precip into rain vs. snow and releases a
snowpack as melt, but `snow_available_water` only returned the *combined* available water.
`src/monthly_flow.py` gained `snow_available_components(precip_mm, temp_c) -> (rain[n,12],
melt[n,12])` — the two buckets that previously summed inside `snow_available_water`, same
temperature-index physics, same 3-cycle spin-up (pack carried across cycles). Crucially,
`snow_available_water` now `return`s `rain + melt` from the new function and stays
**byte-identical**: the existing `test_snow_bucket_accumulates_cold_and_releases_warm`
passes unchanged, and a new test asserts `rain + melt == snow_available_water(...)` exactly
via `np.array_equal`. `src/flow_metrics.py` gained (numpy-only, **no `monthly_flow` import**
— callers pass arrays): `snow_fraction(rain, melt)` (annual `Σmelt / Σ(rain+melt)`,
all-zero → `0.0` guarded), `REGIME_SNOW_MIN=0.4` / `REGIME_RAIN_MAX=0.2` +
`classify_regime` (`snowmelt`/`transitional`/`rain`, validates `0<=rain_max<snow_min<=1`),
`SnowRegime` + `snow_regime` (fraction, label, melt-pulse center-of-timing), and
`MeltTimingTrend` + `melt_timing_trend` (Sen's slope + Mann-Kendall on per-year melt CT →
`days_per_decade`; negative = "your river is becoming a rain river"). Tests +3 in
`test_monthly_flow.py`, +8 in `test_flow_metrics.py`. **Suite 861 passing.**

### #70 — Center-of-timing drift as a hero metric (`08c7be5`)

`TimingTrend` + `center_of_timing_trend(yearly_flow, years=None)` — per-year
whole-hydrograph CT → Sen's slope + Mann-Kendall → `days_per_decade` (negative = peak
arriving earlier, "the peak arrives N days earlier per decade" — one of the most legible
western-hydrology climate signals). Accepts a `{year:[12]}` mapping *or* a `[years,12]`
matrix. The clean move here: extracted `_coerce_year_rows` (mapping/matrix → `(years,
rows)`) and had **#69's `melt_timing_trend` delegate to `center_of_timing_trend`** and
repackage — #69's public API and tests unchanged, with a test asserting the two agree on
the same input. Tests +4. **Suite 865 passing.**

### #71 — Analog-year finder (`0fdb998`)

`AnalogYear` + `analog_years(series, target, *, n=None)` — ranks every year in a
`{year:[12]}` series by Pearson correlation (`pearson_r`) of its 12-month vector to the
target's. Correlation removes mean/scale, so a wet year and a dry year with the same
seasonal *shape* still read as analogs ("2015 looked most like 1934"). Constant year →
`nan` similarity, sorts last; ties break by ascending year (deterministic). Tests +4.
**Suite 869 passing.**

### #72 — Drought/flood record book + #73 decade FDC (`261b99a`, one commit)

**#72:** `YearRank`/`RecordBook` + `rank_years(metric_by_year, *, ascending, n)` (rank 1 =
smallest for drought or largest for flood, each stamped with `percentile_rank`) +
`record_book(series, *, summer_months=(6,7,8), n=5)` reducing a hydrograph series to a
summer-low and an annual-peak leaderboard. **#73:** `DecadeFDC` +
`decade_flow_duration(series, quantiles, *, decade_size=10)` — buckets the series into
decades, pools each decade's monthly flows, computes the exceedance curve via
`flow_duration`, so overlaying them shows the whole distribution shifting over time (not
just the mean). Tests +5 (#72) and +3 (#73). **Suite 874 passing (#72), 877 (#73).**

### #74 — ENSO/PDO composite hydrographs (`132a47e`)

`PhaseComposite` + `composite_hydrographs(series, index_by_year, *, warm_min=0.5,
cool_max=-0.5)` — over years common to the flow series and the climate index, classifies
each warm (El Niño / +PDO), cool (La Niña / −PDO), or neutral and averages the 12-month
hydrograph within each phase (standard ONI ±0.5 thresholds, reusable for PDO by sign; empty
phase → `None`). Tests +3. **Suite 880 passing.**

### #75 — Longitudinal flow-accumulation frames (`150c009`)

`ProfileFrame` + `longitudinal_frames(accum_flow, hydroseq, dnhydroseq, path)` — walks the
mouth-to-headwater `longitudinal_profile` one confluence at a time, emitting a `revealed`
accumulated-flow polyline (the reveal for a progressive draw) and a `fraction` monotone in
`[0,1]` ending at `1.0` per step. Zero-mouth network → all-`0` fractions (guarded divide);
`longitudinal_profile` validation propagates unchanged. Tests +4. **Suite 884 passing.**

### #76 — Report assembly & web surfacing (`ae59bd3`) — Epoch 17 close

The surfacing glue, **no `src/` change**. `tools/report_common.py` gained five matplotlib
figures over the outlet `{year:[12]}` series (+ climate index for composites), each driving
an already-tested `flow_metrics` function: `fig_timing_drift` (#70), `fig_analog_years`
(#71), `fig_record_book` (#72), `fig_decade_fdc` (#73), `fig_composites` (#74) — wired into
`build_report` behind a `creative=True` flag, with `--no-creative` on
`build_watershed_report.py`. `web/shared/hydro-ux.js` gained two **pure, node-loadable**
helpers — `classifyRegime(fraction, snowMin, rainMax)` (mirrors the Python
`REGIME_SNOW_MIN`/`REGIME_RAIN_MAX` thresholds and validation) and `centerOfTimingIndex(v)`
(0-based flow-weighted month, `NaN` on empty/all-zero) — plus new deterministic
`regime`/`analogs`/`recordBook`/`fdc`/`composites` sections on `sampleReport()` (existing
`REPORT_SAMPLE` fields untouched so prior panels render identically). `web/report.html`
added five panels reusing `buildSparkline` and existing tile styles. Node tests:
`test_report_web.cjs` **+5**; `test_recipe_roundtrip.cjs` **11** unchanged. **Python suite
884 (unchanged — no `src/` edit).**

## Real-data findings — and the honest scope note this epoch surfaced

Unlike a layer epoch, Epoch 17 produced no real-GDB smoke run; its "real" surface is the
report **assembly** at #76, and that is exactly where the epoch's genuine finding appeared.
The assembly item revealed **which of the seven stats the existing report data pipeline can
actually feed.** The report's series is **flow-only** (`{year:[12]}` per watershed), so
**#70–#74 wire directly** into real `tools/report_common.py` figures. But **#69** (snow
regime) needs precip/temp arrays and **#75** (longitudinal animation) needs network
topology (`hydroseq`/`dnhydroseq`/`accum_flow`) — neither derivable from the flow-only
outlet series — so both remain **render-tool territory**. The web report therefore shows
the regime only as a **synthetic mock badge**, honestly labeled, consistent with
`report.html` being a deterministic sample export. This is the recurring project lesson in a
new guise: the offline fakes (here, the pure `src/` stats with hand-built arrays) all pass,
but the thing they cannot verify is whether the *real assembled data product* can supply
each function's inputs. The assembly item is where that truth landed. Recorded as a
carry-forward, not papered over.

## Invariants held

- **Offline suite:** **884 passing** (grew monotonically across the epoch: 861 at #69, 865
  at #70, 869 at #71, 874 at #72, 877 at #73, 880 at #74, 884 at #75; unchanged at #76
  because #76 touched no `src/`). Plus **node 5** (`test_report_web.cjs`) **+ 11**
  (`test_recipe_roundtrip.cjs`) green. No network / GDAL / real datasets.
  `src/flow_metrics.py` and `src/monthly_flow.py` stayed **numpy-only** with no
  cross-import between them (callers pass arrays), and no `tools`/`web`/GDAL imports at
  module scope. `hydro-ux.js` stayed Node-loadable (no top-level `document`/`window`).
- **2D default output byte-identical:** yes. Nothing touched the render path or defaults;
  the seven stats are report analytics, not pipeline stages. The one refactor that *could*
  have drifted bytes — `snow_available_water` now returning `sum(snow_available_components())`
  — was pinned byte-identical by `np.array_equal` and the unchanged pre-existing snow test.
- **`PIPELINE_STAGES` untouched:** yes — no stage added, removed, or reordered. This was a
  hard non-goal and it held completely; every item's report and every task group re-asserts
  it.
- **Rights gate:** N/A — no new gate needed. Climate posture unchanged: default
  `--climate-source nclimgrid` is public-domain/sellable with attribution; PRISM stays
  A/B-only and non-sellable. `fulfillment.assert_sellable` unaffected.

## What went well

- **Reuse over reinvention, again.** Every new stat delegated to existing primitives:
  `melt_timing_trend`/`center_of_timing_trend` share `_coerce_year_rows` and Sen's
  slope/Mann-Kendall; `analog_years` rides `pearson_r`; `record_book` rides
  `percentile_rank`; `decade_flow_duration` rides `flow_duration`; `longitudinal_frames`
  rides `longitudinal_profile`; the web `classifyRegime` mirrors the Python thresholds
  exactly. The epoch was genuinely "seven small stats + one assembly," as planned, because
  the primitives already existed — the same lesson as Epochs 15/16 and Generation 1.
- **The `src/` (numpy-only, offline) vs. `tools/` (matplotlib, non-suite) vs. `web/`
  (node-testable pure JS) split scaled cleanly across all eight items.** Each stat was
  testable the moment it landed; #76's only *testable* surface was the pure node-loadable
  JS, and it was tested (+5) rather than left to a browser.
- **The #69 byte-identity refactor is a model.** Splitting a function into components while
  guaranteeing the sum is byte-identical — and locking it with `np.array_equal` plus the
  untouched original test — is exactly how to add a diagnostic without disturbing a
  numeric output.
- **Monotonic, honest test-count growth** with a full-suite regression gate at every group
  is the discipline working as intended.

## Gotchas found

- **A passing pure stat does not mean the data product can feed it.** #69 and #75 are
  fully implemented and offline-green, yet the flow-only report series cannot supply their
  inputs (precip/temp; network topology). Only the assembly item surfaced this — the
  offline unit tests, using hand-built arrays, structurally could not. (Detailed above.)
- **The web regime badge is a mock, not a live computation.** `report.html` shows the
  snow-vs-rain regime as a synthetic mock badge because the sample doc is flow-only; a
  reader must not mistake it for a real per-watershed classification until #69 is fed from
  the render tools' precip/temp path.
- **No pre-analysis / watch-list was written** for the spec (only `requirements.md`). The
  "which stats can the real data product actually feed?" risk is precisely the kind of
  "offline fakes can't verify the real path" item a pre-registered watch-list is meant to
  force — and it would have flagged #69/#75 before implementation rather than at assembly.

## Carry-forwards

- **#69 (snow regime) and #75 (longitudinal animation) are not wired into the assembled
  report** — they remain render-tool territory because the flow-only `{year:[12]}` series
  cannot supply precip/temp (#69) or network topology (#75). Feeding #69 from the render
  tools' precip/temp path, and #75 from the network, are open follow-ons. The web regime
  badge stays a mock until #69 is fed for real. Open, not passed.
- **No live browser render check** of `web/report.html` was possible this session — no
  Chrome extension was connected. The page was verified **statically** (inline script
  parses; all `doc.*` fields the panels read confirmed present in `sampleReport()`), not
  **visually**. A live render of the five new panels is deferred.
- **`tools/report_common.py` figures are outside every suite** (heavy GIS + matplotlib, like
  all `tools/`); verified via `py_compile` only. Producing the five real figures against an
  actual watershed report on a data host has not been done this session — the same standing
  "final artifact needs a real host" carry-forward inherited since Epoch 12.

## Lessons

- **Restore the pre-analysis/watch-list step** (now four epochs running without it —
  16, Generation 1's five specs, and 17). The one genuine surprise this epoch — #69/#75
  can't be fed from the flow-only report series — is textbook "offline fakes can't verify
  the real assembled path," exactly what a pre-registered watch-list exists to smoke for
  *before* seven items are built.
- **Implement the assembly item early enough to learn from it.** The data-reality
  constraint on #69/#75 only became visible at #76; discovering "which stats the pipeline
  can feed" *before* building all seven would have reframed #69/#75 as render-tool work
  from the start. Consider a lightweight "can the target data product feed this?" check per
  stat at spec time.
- **A green unit test guards the function, not the product.** Every stat passed on
  hand-built arrays; whether the shipped report can supply those arrays is a separate
  question the assembly answers. Validate the input-availability of each analytic against
  the real data product, not just its math against fixtures.
- **Byte-identical refactors are cheap when locked with an equality assertion.** #69's
  `snow_available_water` split is the pattern to repeat: change internals freely, pin the
  observable output with `np.array_equal` and the pre-existing test.

---

_Bookkeeping reminder for the orchestrator: confirm `HANDOFF.md` and
`agent-os/product/roadmap.md` reflect the same Epoch 17 close — all of #69–#76 are `[x]`
in the roadmap with the epoch marked complete; ensure any "commit pending" HANDOFF bullets
for this epoch are cleared so `tools/detect_unfinished.py` stays quiet._
