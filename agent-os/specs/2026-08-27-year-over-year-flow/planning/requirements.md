# Requirements — Year-over-year historical flow (Option C)

## Problem

The "year in motion" render animates twelve months of streamflow, but those
twelve months are a **synthetic average year**: `tools/monthly_flow.py`
disaggregates NHDPlus HR's mean-annual flow (`QAMA`) using the GDB's *long-term
climate normals*. There is no calendar year, so you cannot see how a wet year
(e.g. 2017) differs from a drought year (e.g. 1977), and you cannot watch a river
network change across decades.

## Goal

Add a **year-over-year** axis alongside the existing one-year-monthly view: render
the same network's monthly flow for a **chosen historical calendar year**, and
step across a **span of years**, for California, Washington, Oregon, Utah, and
Idaho.

## Chosen approach — Option C (PRISM-driven synthetic history)

Decided in the research thread. Keep the existing rainfall-runoff disaggregation
engine and swap only its climate input: from the GDB's normals to **PRISM real
per-year monthly precip + mean temperature** (monthly record from **1895**).

Rationale vs. the alternatives:

- **A. NWM retrospective** (real modeled per-reach flow, 1979–2023) — highest
  fidelity but needs an NHDPlus-V2↔HR crosswalk (or a base-geometry switch) and
  hundreds of GB of cloud-scale reads. Deferred.
- **B. USGS NWIS gauges** — observed, back to the early 1900s, but point gauges
  only, not a full network. Useful later for validation, not for painting reaches.
- **C. PRISM-driven synthetic** — reuses the engine, deepest history (1895), a few
  GB of HTTP-downloadable rasters, no crosswalk. **Selected.** Honestly a model,
  not observed flow.

## Functional requirements

1. Produce per-reach **monthly flow `[n, 12]`** for any requested historical year
   ≥ 1895 (subject to staged PRISM data), using the shared
   `src.monthly_flow.disaggregate_monthly`.
2. Accept a **set or span of years**, validated and de-duplicated; fail fast on
   out-of-range/malformed requests.
3. Provide **cross-year reductions** (per-reach annual mean, peak-flow month) so a
   render can compare years.
4. Render **(a)** a single historical year's 12-month animation and **(b)** a walk
   across years, with a **fixed cross-series width scale** so inter-year
   swell/drought is visible (not renormalized away).
5. Cover all five states — add **Utah** as a supported region (it is not in
   `SUPPORTED_REGIONS` today).

## Non-functional / invariants

- **Offline discipline preserved.** The engine (`src/historical_flow.py`) is
  numpy-only and imports no GDAL; PRISM raster reads live in a `tools/` executor
  behind an injectable `ClimateProvider` seam. Tests inject a fake provider.
- **Deterministic & clock-free.** No `datetime.now`; the newest available year is
  an explicit `latest` argument. Identical inputs → identical flow.
- **Default byte-identical.** With no year requested, the existing synthetic-year
  render is unchanged.
- **Large data on the NAS.** PRISM archives stage on the NAS Pro drive like the
  GDBs (mount-aware), never bulking up local disk.

## Effort / volume notes (for the five states, all years)

- PRISM monthly precip+tmean, ~4 km: each grid a few MB; five states × 130 years ×
  12 months × 2 vars ≈ a few GB total, HTTP-downloadable, no cloud compute.
- The kept product (per-reach monthly flow) is small; the cost is the per-year
  raster sampling, done offline on the NAS-staged archive.

## Out of scope

- Live `build.py` year rendering in the 2D pipeline (fails fast, like `--months`).
- Web control-surface year-over-year UX.
- The NWM (Option A) and NWIS (Option B) routes.
