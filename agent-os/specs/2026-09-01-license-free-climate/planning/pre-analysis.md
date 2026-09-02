# Pre-analysis — Epoch 14 watch-list (#60)

Written *before* implementation (the standing practice from Epochs 8/9/12), so the
closeout retrospective has a pre-registered list to grade against rather than a
story retrofitted to whatever happened.

## A. Retrospective watch-list / risk register

Ordered by risk. Each names what the closeout retro must record.

1. **Rights is the whole point — verify nClimGrid is actually free to sell.** The
   epoch's entire justification is "public domain, $0 to sell." If that's wrong the
   gate doesn't move.
   - **Record** the exact license/use terms as stated by NOAA/NCEI (federal public
     domain) + the attribution line to stamp on sold assets. Do not retire the PRISM
     gate until this is documented from the source, not assumed.

2. **Band off-by-one is the highest-risk *correctness* bug.** nClimGrid is one
   NetCDF with a monthly `time` axis addressed by band; `band = (year-1895)*12 +
   month` has two classic traps: the 1895 epoch origin and 0- vs 1-based bands
   (rasterio bands are 1-based). A silent off-by-one shifts every frame by a month
   or a year — plausible-looking but wrong.
   - **Mitigation, pre-registered:** the band-index math lives in pure
     `src/climate_grid.py` with unit tests pinning known `(year, month) → band`
     pairs (e.g. Jan 1895 → band 1; Dec 1895 → band 12; Jan 1896 → band 13).
   - **Record** a real cross-check: sample one known month/place and sanity-check
     the magnitude (a wet PNW winter vs a dry summer) against PRISM for the same
     month — they should be *close*, not identical (different grids).

3. **Offline coverage vs the "tests never import `tools/`" rule.** The valuable new
   logic (sampling) lives where GDAL does — `tools/`. Naively that's untestable
   offline.
   - **Invariant to grade:** the pure sampling logic was factored into numpy-only
     `src/climate_grid.py` (offline-tested), the rasterio I/O stayed in
     `tools/nclimgrid_flow.py` and lazy-imports rasterio, and the offline suite
     never imports `tools/`. Grade whether this split held or logic leaked into an
     untested tools-only path.

4. **"No `src/` change beyond docs" (roadmap wording) vs adding
   `src/climate_grid.py`.** The roadmap promised the *engine + default render* stay
   byte-identical; getting offline test coverage required a **new** pure module.
   - **Record** that `src.historical_flow` / `src.monthly_flow` / `PIPELINE_STAGES`
     were untouched and the default synthetic-year render is byte-identical — i.e.
     the promise's *intent* held even though a new (additive) `src/` module landed.
     Flag it honestly rather than pretending no `src/` file was added.

5. **nClimGrid CRS/units really match PRISM.** Assumed: prcp in mm, tavg in °C,
   EPSG:4326, datum offset sub-cell at 5 km so no reprojection. If prcp were in
   inches or tavg in °F, or the grid needed warping, every flow number is wrong.
   - **Record** the NetCDF's actual variable units + CRS as read from the file
     (rasterio `crs`/`tags`), not assumed — and that the fallback nodata (precip 0 /
     temp 10 °C) matches `monthly_flow.py`.

6. **Fetch volume & staging.** Two NetCDFs spanning 1895–present are large
   (hundreds of MB each). Must land on the NAS, mount-aware, resumable, atomic.
   - **Record** staged size of each file and that an unmounted NAS degrades cleanly
     (the `feedback_large_file_storage` rule).

7. **Offline fakes can't verify the real read path** (carried from Epochs 8/10/12).
   The fake-reader unit tests prove the band math and fallback wiring; they cannot
   prove rasterio opens the real NetCDF, that bands map to the months we think, or
   that the numbers are physical.
   - Keep a **non-offline smoke** that fetches + samples a real basin for a couple
     of years and **records the real numbers** (per-year reach hit-count, a
     wet-vs-dry-year width delta). Do not let "offline-green" stand in for it.

8. **Provider-selection scope-creep.** Adding `--climate-source` touches
   `render_state_yoy` / `report_common` / `build_watershed_report`. Risk: forking
   the flow path per source.
   - **Invariant to grade:** exactly **one** call site constructs the provider (a
     factory keyed by the flag); both providers share `(root, lon, lat)` +
     `climate_for_year`; no downstream flow/render code branches on source.

## B. Common code (reuse map — avoid drift)

- **The injectable-provider pattern, reused — do not invent a new I/O shape.**
  `NClimGridClimateProvider` implements the *existing* `src.historical_flow.
  ClimateProvider` seam with the *same* `(root, lon, lat)` constructor as
  `PrismClimateProvider`. The offline engine `yearly_flow_series` is reused verbatim.
- **Pure-in-`src/`, I/O-in-`tools/`, fake-in-tests** — the repo's core split. New
  pure module `src/climate_grid.py` (numpy-only) gets `tests/test_climate_grid.py`
  (the every-`src`-module-has-a-test rule); the rasterio read lives in
  `tools/nclimgrid_flow.py`.
- **One provider factory, one flag.** `--climate-source {nclimgrid,prism}` resolves
  to a provider class at a single call site in `render_state_yoy.yearly_flow_by_id`;
  `report_common` / `build_watershed_report` thread the flag, they don't re-implement
  selection.
- **Reuse staging conventions.** `tools/nclimgrid_fetch.py` mirrors
  `prism_fetch.py`'s `--root` / `<root>/<dataset>/…` staging, atomic `.part` rename,
  idempotent skip.

## C. Post-development cleanup (pre-registered — grade the sweep)

- **Retire the PRISM Rights gate** in `agent-os/product/roadmap.md` Notes (and the
  Epoch 12 retro carry-forward) once #2/#1 above are documented — nClimGrid is the
  resolution the gate itself points to.
- **Docs sweep:** CLAUDE.md (add `src/climate_grid.py` to the module map + the new
  tools to the ad-hoc tools section, note nClimGrid as the default climate source),
  `HANDOFF.md`, tick roadmap #60.
- **Retrospective** `agent-os/retrospectives/2026-09-01-epoch-14-license-free-climate.md`
  graded against this watch-list.
- **No dead code / honest deprecation:** PRISM provider + `prism_fetch.py` stay
  (reachable via `--climate-source prism`) but their docstrings/CLAUDE note that
  nClimGrid is the default license-free path — no orphaned "removed" comments, no
  half-deleted PRISM references.
