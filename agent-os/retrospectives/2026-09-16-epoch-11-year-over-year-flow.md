# Retrospective — Epoch 11: Year-over-year historical flow (#44--#46 shipped, #47 deferred)

_Partially closed 2026-09-16. **No pre-registered watch-list** — neither the
`2026-08-12-monthly-flow-option` nor `2026-08-27-year-over-year-flow` spec folder
carries a `planning/pre-analysis.md` (only `planning/requirements.md`). This is a
narrative closeout for the three shipped items; #47 (Utah) remains explicitly open,
gated on the Epoch 11.5 revenue experiment._

## What the epoch was

Add a **year-over-year axis** to the monthly-flow animation: instead of one synthetic
"average year" from NHDPlus HR climate normals, run the same disaggregation engine
against **real per-year monthly climate** (PRISM record starting 1895, later swapped to
nClimGrid in Epoch 14) for a chosen historical year or span of years across
OR / WA / CA / ID. Follows the Option C decision: reuse the existing rainfall-runoff
model and swap only the climate input, getting the deepest history for the least new
architecture — no NHDPlus-V2-to-HR crosswalk, no cloud-scale NWM reads.

The epoch also promoted the monthly-flow disaggregation math from ad-hoc `tools/` into
tested, offline `src/` code (#25, later renumbered #44 in the year-over-year scope),
mirroring the #23 precedent of "promote pure algorithms + option surface, keep GDAL
reads in `tools/`."

## What shipped

### Item #44 — Monthly-flow disaggregation (`6c18a0d`)

`src/monthly_flow.py` (new, numpy-only, offline) — promoted verbatim from
`tools/monthly_flow.py` minus the pyogrio reads: `snow_available_water`,
`normalize_shape`, `accumulate_downstream`, `disaggregate_monthly`, plus constants
(`MONTH_ABBR`, temperature thresholds, `SPINUP_CYCLES`). Conserves each reach's annual
mean. `src/rendering.py` gained `fixed_flow_span` / `widths_on_span` /
`monthly_width_frames` — the fixed year-max log-scale width mapping so seasonal
swell/retreat is visible (per-month renormalization would hide it). Config/CLI:
`Settings.months` (`tuple[int, ...]`, empty = annual); `parse_months` handles
single/name/range/wrapping tokens (`may-sep`, `nov-feb`); `--months` CLI flag.
Pipeline: `_generate_svg_stage` fails fast with `ConfigError` on non-annual months
(same pattern as `color_by=elevation`), pointing at `tools/render_monthly.py`. Tool
refactor: `tools/monthly_flow.py` and `tools/render_monthly.py` now delegate math to
`src/`. Suite: **345 passing** (was 310 at #24 close; +35).

Tests: `tests/test_monthly_flow.py` (6), `tests/test_rendering.py` (+5),
`tests/test_config.py` (+3 incl. parametrized), `tests/test_cli.py` (+2),
`tests/test_monthly_pipeline.py` (2).

### Item #44 (engine) — Historical-flow engine (`6909293`)

`src/historical_flow.py` (new, numpy-only, offline) — `PRISM_FIRST_YEAR = 1895`,
`HistoricalFlowError`, frozen `YearlyClimate` (`[n,12]` precip/temp with shape
validation), `ClimateProvider` protocol (injectable seam), `normalize_years`
(dedup/sort, boundary checks), `year_span`, `yearly_flow_series` (runs
`disaggregate_monthly` per year against a provider, once per distinct year),
`annual_mean_series`, `peak_month_series`. Imports only numpy + `src.monthly_flow` —
no GDAL, no clock (`latest` is passed in, never `datetime.now`). Spec + engine shipped
in one planning commit with **17 passing tests** (`tests/test_historical_flow.py`)
injecting a fake `ClimateProvider` over a 3-reach chain.

### Item #45 — PRISM climate ingestion (`08a07e1`)

`tools/historical_flow.py` — `PrismClimateProvider(prism_root, ...)` reads 12 monthly
PRISM `ppt` + `tmean` grids per year, samples each catchment centroid in EPSG:4269,
returns `YearlyClimate` aligned to the reach order. Eager GIS imports live here only.
`tools/prism_fetch.py` — idempotent/resumable PRISM download/stage helper (NACSE web
service, archives under `<root>/prism/<var>/`). Smoke: staged all of 2014--2023 (240
grids); WA render disaggregated every HUC4 with **147,908 / 147,908 reaches** carrying
real PRISM flow (no fallbacks).

**Post-epoch update (Epoch 14, `5342931`):** the default climate source was later
swapped from PRISM to NOAA NCEI nClimGrid-Monthly (public domain, sellable with
attribution) via `--climate-source {nclimgrid,prism}`. The `ClimateProvider` seam built
in this epoch is exactly what made that swap a same-signature sibling addition. PRISM
remains selectable for A/B comparison only; never sell a PRISM-derived asset.

### Item #46 — Year-over-year renderer (`08a07e1`)

`tools/render_state_yoy.py` — drives frames from `yearly_flow_series` for a year walk
(real per-year `disaggregate_monthly` per HUC4, merged by `NHDPlusID`). Fixed
cross-series width span across all rendered years (reuses
`src.rendering.fixed_flow_span` / `widths_on_span`) so inter-year drought/flood
difference is visible. Smoke: WA 2014--2023 GIF — summed peak-month (May) flow ranges
from **76M cfs (2016 drought) to 211M cfs (2023)**; channel widths visibly differ
year-to-year.

## Real-data findings

The significant numbers from the WA 2014--2023 smoke render:

- **147,908 / 147,908** reaches carried real PRISM climate — zero fallbacks, full
  coverage.
- **Peak-month summed flow:** 2016 drought 76M cfs vs. 2023 wet year 211M cfs — a 2.8x
  range. The fixed cross-year width span makes this physically visible in the GIF;
  per-year renormalization would have hidden it.
- **nClimGrid A/B (Epoch 14 follow-up):** Dec-2017 Salmon Creek precip agrees to
  **0.6%** (254.4 vs 255.8 mm) between nClimGrid and PRISM. Full engine peak-flow
  ratios 0.987 (2017) / 1.091 (2015). The seam design made this A/B trivial.

No "bug the real run surfaced that offline fakes could not" emerged from this epoch's
own smoke runs. The major seam-validation bugs surfaced later when the seam was
exercised by Epoch 14's nClimGrid swap (silent HTTP truncation of the 1.47 GB NetCDF,
nClimGrid carrying no CRS tag via GDAL). The #44 engine itself is pure numpy over
injected climate — the real-world surface area is in the provider, not the model. This
is arguably the design working as intended: the injectable seam pushed the failure
surface into the `tools/` caller where it belongs.

## Invariants held

- **Offline suite:** 28 Epoch 11-specific tests passing (6 `test_monthly_flow` + 5
  `test_rendering` additions + 2 `test_monthly_pipeline` + 3 `test_config` additions +
  2 `test_cli` additions + 17 `test_historical_flow` = 35 new tests; some are additions
  to existing files, net 28 in the core epoch files). Current total suite: 1027 passing
  (6 unrelated `test_min_order` failures from a not-yet-implemented Epoch 26 feature).
- **2D default output byte-identical:** yes. `months` defaults to `()` (annual), which
  leaves `_generate_svg_stage` unchanged. `src/historical_flow.py` is not wired into
  `PIPELINE_STAGES` at all. No default-path code touched.
- **`PIPELINE_STAGES` untouched:** yes. The only pipeline change was a fail-fast
  `ConfigError` guard in `_generate_svg_stage` for non-annual months — the stage list
  itself was not modified.
- **Rights gate:** the PRISM climate source used for smoke renders is not public domain;
  **no PRISM-derived asset is sellable**. This was flagged at epoch time and was the
  direct motivation for Epoch 14's nClimGrid swap. After Epoch 14, the default
  `--climate-source nclimgrid` path is commercially clear (public domain + attribution).
  `fulfillment.assert_sellable` enforces the guard.

## Item #47 — Utah (explicitly deferred)

`tools/derive_state_huc4.py` to UT HUC4s, wire `SUPPORTED_REGIONS` /
`datasets.REGION_HUC4` / `counties.STATE_FIPS` / `render_common.STATE_HUC4`, download
UT NHDPlus HR GDBs. All four task-group steps (`4.1`--`4.3` in `tasks.md`) remain
`[ ]`.

**Deferred per the 2026-08-30 revenue amendment:** do not start until the Epoch 11.5
revenue gate passes — the existing four-state scope (OR / WA / CA / ID) is enough to
validate demand. This is an honest scope cut, not a slip: the decision was made
deliberately after the initial market review. If the revenue gate passes, Utah is the
well-trodden Idaho path (`fbb8960`) and should be an `S`-sized item.

Spec `tasks.md` Group 5 (close-out tasks 5.1--5.2) also remain `[ ]` because the epoch
is partially complete. The full-suite regression check was not formally recorded at
epoch close, though the items shipped clean at their individual commit points.

## What went well

- **The injectable-seam precedent paid off twice.** The `ClimateProvider` protocol built
  in #44 made the PRISM provider (#45) a same-signature implementation, and later made
  the nClimGrid swap (Epoch 14) a same-shape sibling addition. No engine changes for
  either — the seam absorbed the variation exactly as designed.
- **The fixed-span width mapping was the right call.** `fixed_flow_span` across all
  years keeps inter-year drought/flood physically visible in the animation. Per-year
  renormalization would have hidden the 2.8x flow range between 2016 and 2023 — the
  same trap documented in the #25 spec for months.
- **Clock-free engine.** `latest` is passed in, never `datetime.now` — the engine is
  deterministic for identical inputs. This was a deliberate design choice documented in
  the spec and it has held through every downstream consumer.
- **Option C (reuse existing model, swap climate) delivered the deepest record for the
  least architecture.** Back to 1895 without NWM reads or a crosswalk — exactly the
  trade-off the spec's research thread predicted.

## Carry-forward

- **#47 (Utah) is open**, gated on the Epoch 11.5 revenue gate (#59). Not started, not
  failed — deliberately deferred.
- **Spec `tasks.md` Group 5 (close-out) is open** — full-suite regression + formal
  `implementation/report.md` for the year-over-year spec were not completed. The
  monthly-flow spec has its report (`agent-os/specs/2026-08-12-monthly-flow-option/
  implementation/report.md`); the year-over-year spec
  (`agent-os/specs/2026-08-27-year-over-year-flow/`) does not.
- **Byte-identical full `build.py` render compare** still needs a GDAL host (shared
  carry-forward since Epoch 9/10). This epoch's invariant is satisfied structurally
  (no `PIPELINE_STAGES` code touched, default months empty).
- **Live `build.py --months` end-to-end** remains deferred — the 2D pipeline fails fast
  on non-annual months by design; real renders come from `tools/render_monthly.py` and
  `tools/render_state_yoy.py`.

## Lessons

- **Design the seam before the first consumer, not after.** The `ClimateProvider`
  protocol was built in #44 with only the PRISM provider in mind, but because it was a
  clean injectable boundary (not a PRISM-specific API), the nClimGrid swap in Epoch 14
  was a zero-engine-change addition. The lesson is that even when you only see one
  consumer, building the seam pays off when the second arrives.
- **Fixed normalization across a series is load-bearing for visual honesty.** A
  per-frame or per-year renormalization hides the signal the animation exists to show.
  This was predicted in the spec and confirmed by the 76M-to-211M cfs range. Encode
  the invariant in the function signature (`fixed_flow_span` returns one span for all
  data) so it cannot be accidentally per-frame'd.
- **Revenue gating works.** Deferring #47 (Utah) until demand is proven avoids building
  a fifth-state surface nobody has asked to buy. The code path is proven (Idaho
  precedent); the decision to wait is a product decision, not a technical one.
- **Restore the pre-analysis/watch-list step.** Neither Epoch 11 spec carried a
  `pre-analysis.md`. Epochs 12 and 14, which did carry one, both caught their
  highest-risk item (validation framing, band off-by-one) via the pre-registered
  watch-list. The practice should not be optional.
