# Corrections Roadmap

Remediation backlog distilled from the epoch retrospectives (Epochs 8, 9, 12, 14,
16, Generation-1 release, 17, 18). This is a **debt/correction** track that runs
alongside `roadmap.md` — it does not add product surface, it closes gaps the
closeouts flagged. Same rules apply: one item at a time, tests first, never touch
`PIPELINE_STAGES` (2D default stays byte-identical), `src/flow_metrics.py` and
`src/monthly_flow.py` stay numpy-only, committing is a separate explicit step.

Tracks are ordered by leverage: process fixes first (they prevent recurrence),
then cheap offline tooling, then offline-fixable feature gaps, then the host-gated
verification that can only close on a GDAL+NAS machine, then informational data
limits.

> Effort scale (mirrors `roadmap.md`): XS=1 day, S=2–3 days, M=1 week, L=2 weeks.
> Each item cites the retrospective(s) that raised it.

---

## Track C1 — Process discipline · proposed

The systemic root cause. Restoring one cheap step prevents most of the concrete
bugs the other tracks clean up. Flagged as a regression in **four consecutive**
closeouts (Epochs 16, Gen-1, 17, 18).

C1.1. [ ] Restore the pre-analysis / watch-list step — Before implementing any spec,
write a short "what could go wrong / what can only be verified on real data" note
into the spec's `planning/`. Present in Epochs 8/9/12/14, dropped for the last four.
Wire it into the spec-shaper/spec-writer flow so it can't be skipped. `XS`

C1.2. [ ] "Offline can't verify this" checklist per epoch — A standing template
listing the categories that offline fakes structurally cannot catch (warp/reproject
branches, drainage-area matching, truncated network fetches, real-adjacency geometry
metrics, direct-run `__main__` paths, stat input-availability). Every retro surfaced
one such bug; the checklist turns hindsight into a pre-flight. `XS`

C1.3. [ ] Roadmap-status reconciliation as a close-out gate — Epoch 17 & 18 headers
and #77/#78 checkboxes were stale against shipped code (reconciled 2026-09-07). Make
`tools/update_status.py` (or the close-out step) assert header/checkbox state matches
the committed reality. `S`

Track gate: a new spec cannot reach implementation without a watch-list note, and a
close-out cannot complete with a stale roadmap checkbox.

---

## Track C2 — Tooling debt · complete

Cheap, fully offline, high recurrence. Safe to knock out from any host.
**Done 2026-09-07** — spec `agent-os/specs/2026-09-07-tooling-debt-corrections/`; regression
guards in `tests/test_tools_direct_run.py` (suite 884 → 890).

C2.1. [x] Fix the direct-run `tools/` `sys.path` shim once, everywhere — Recurring
`ModuleNotFoundError: No module named 'src'` when running `.venv/bin/python
tools/<x>.py` as `__main__` (Gen-1: `release_gate.py`, `build_changelog.py`,
`render_gallery.py`, `render_endpoint.py`, `render_all_endpoints.py`; also hit on
`detect_unfinished.py`). Add the `sys.path.insert(0, str(REPO))` shim (or a shared
`tools/_bootstrap.py`) to every direct-runnable tool, and add a smoke test that
imports each as `__main__`. `S`

C2.2. [x] Pin `ruff` — Configured linter is absent from `.venv` and undeclared in
`pyproject.toml`/`requirements.txt` (Epoch 9). Pin it as a dev dependency so
`ruff check src tests` runs without a manual `pip install`. `XS`

C2.3. [x] Make `tools/report_common.py` CWD-independent — Repo-root-relative cache
paths miss (and fall through to a live WBD read) when run under `jupyter nbconvert`
with CWD = notebook dir (Epoch 12). Resolve paths from `__file__`/REPO, or document
the required `os.chdir(REPO)` and assert it. `XS`

Track gate: every tool in `tools/` runs as `__main__` from a clean shell, `ruff`
runs from the pinned env, and report caches resolve regardless of CWD.

---

## Track C3 — Offline-fixable feature gaps · proposed

Genuine roadmap gaps the closeouts deferred that can be built and tested offline
(fixtures + node/py-compile), leaving only real-data smoke for the host-gated track.

C3.1. [ ] #66 — engineered `NHDFlowline` styling — Never shipped (Epoch 16, still
`[ ]` in `roadmap.md`). Classify+style the CanalDitch / Pipeline / ArtificialPath /
Connector / UndergroundConduit flowline split and render distinctly. Mirror the
existing `hydro_structures` classification pattern; keep it disabled-by-default so
the render stays byte-identical. `M`

C3.2. [ ] #69 / #75 report wiring (or honest de-mock) — `web/report.html` shows the
snow regime as a **synthetic mock badge** (Epoch 17); #69 needs precip/temp and #75
needs network topology the flow-only `{year:[12]}` series lacks. Either (a) thread
the extra inputs through a report-data seam so the badge/animation are real, or (b)
formally scope them as render-tool-only and remove the mock from the web report. `M`

C3.3. [ ] Wire `--width-preset` into the real render path — Epoch 18 presets shape
only the offline stream-order proxy; wire `--width-preset` into
`tools/render_state_svg.py` over real QAMA/EROM discharge so state/basin/watershed
ramps act on true per-reach flow. Offline portion: the wiring + arg plumbing; the
live ~10:1 / Q^0.45 / √Q confirmation belongs to Track C4. `S`

Track gate: #66 renders engineered reaches (default-off, byte-identical default);
the web report contains no unlabeled mock; `--width-preset` reaches the real
renderer.

---

## Track C4 — Host-gated verification · blocked (needs GDAL + NAS + shapefiles)

Cannot close from an offline host. These are the outstanding real-environment
confirmations the closeouts explicitly deferred. Group and run in one session on a
GDAL+NAS machine.

C4.1. [ ] Live determinism double-render — Asserted structurally in Epochs 9, 12,
14, 16, 18 but never observed. Run `tools/verify_determinism.py --region Oregon`
(double-render + golden-hash) on a real host and record the SHA. `S`

C4.2. [ ] Tag v1.0 — READY-pending, not released (Gen-1). Needs the real
all-four-endpoints double-render reproducibility gate
(`tools/render_all_endpoints.py --check-determinism` / `reproducibility.yml`) green
on GDAL+NAS, then tag. `S`

C4.3. [ ] Stage Census states/counties shapefiles — Absent (`/tmp/states_shp`,
`/tmp/counties_shp` empty, Epoch 16), which blocked `--state Oregon` political-clip
renders and full `--structures` PNGs. Stage them and produce the deferred
Washington / Clark County structure validation. `S`

C4.4. [ ] Live browser render check of `web/report.html` — No Chrome extension was
connected (Epoch 17); the report was verified statically only. Load it in a browser
and confirm the new panels (regime, analogs, record book, decade FDC, composites)
render. `XS`

C4.5. [ ] Real-data smoke for `--width-preset` — Confirm the C3.3 wiring produces the
intended ~10:1 (state, log) / Q^0.45 (basin) / √Q (watershed) width character on a
real QAMA render. `XS`

Track gate: determinism is *observed* not inferred, v1.0 is tagged, political-clip +
structures + width-preset renders are produced on real data.

---

## Track C5 — Data limitations · informational (likely won't-fix)

Recorded for provenance; mostly by-design constraints, not bugs.

C5.1. [ ] (Optional) gridMET / Daymet climate fallbacks — Unbuilt finer/daily climate
sources noted in Epoch 14; only worth building if a finer product needs them. `M`

C5.2. Known limits (no action): nClimGrid NetCDF carries `crs=None` and its record
extends past requested years — provider samples lon/lat directly and `latest` governs
the window (Epoch 14). No active gauge covers 2014–2023 for Salmon Creek 14212000
(Epoch 12). PRISM-derived assets remain non-sellable by the Rights gate (Epoch 12/14)
— by design.

---

> Provenance: every item traces to `agent-os/retrospectives/`. Recurring themes that
> shaped the track order: (1) offline fakes can't verify the real path — a bug in
> every retro; (2) determinism asserted, never observed — 5 epochs; (3) the dropped
> watch-list step — 4 epochs; (4) real artifacts deferred to an absent GDAL+NAS host.
