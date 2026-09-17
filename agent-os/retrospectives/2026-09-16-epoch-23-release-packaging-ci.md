# Retrospective -- Epoch 23: Release packaging, CI & reproducibility gate (#91-93)

_Closed 2026-09-06 (primary commit `f233773`, Gen-1 close-out `3e8acf9`,
post-close fix `1eeb81e`); retro written 2026-09-16. **No pre-registered
watch-list** -- the spec folder (`2026-09-06-release-packaging-ci`) carries
`planning/raw-idea.md`, `planning/requirements.md`, `spec.md`, `tasks.md`, and
`implementation/report.md`, but no `planning/pre-analysis.md`. This is a
narrative closeout. Fifth and final epoch of Generation 1 (Epochs 19-23,
#79-93)._

## What the epoch was

Close Generation 1 by hardening "green suite + artifacts" into a tagged,
reproducible **v1.0**. Three deliverables: (1) a pure, offline release-gate
core that recomputes render-independent golden fixtures and aggregates
determinism verdicts, (2) a pure changelog generator from structured roadmap
input, and (3) CI workflows wiring the offline pyramid plus a gated real-data
job. No art feature; no `PIPELINE_STAGES` change; the default 2D build stays
byte-for-byte identical. The `git tag v1.0` itself was explicitly deferred to a
user-authorized step.

All three planned items (#91-93) shipped and the epoch closed on #93.

## What shipped (`f233773`)

### `src/release.py` (NEW, pure/offline, 159 lines) -- #92

- **`FixtureCheck(name, ok, detail)`** + **`ReleaseVerdict(version,
  fixture_checks, determinism_verdicts)`** frozen dataclasses; `RELEASE_SCHEMA =
  "hydro-art/release-gate@1"`.
- **`check_render_independent_goldens()`** recomputes gallery ledger (via
  `src.gallery.gallery_ledger`) and flagship e2e contract digest (via
  `src.endpoints.e2e_contract_digest(flagship_e2e_requests())`) and compares
  parsed-JSON to committed fixtures. Returns a punch list, never raises.
- **`evaluate_release(version, *, determinism_verdicts, require_determinism)`**
  aggregates fixture checks + `DeterminismVerdict`s into a ready/blocked
  verdict. `ready` iff all fixture checks pass AND (determinism not required, or
  at least one verdict supplied and every verdict `.ok`).
- **`format_verdict(verdict)`** renders a deterministic human-readable block.
- Imports only stdlib + `src.gallery` + `src.endpoints` + `src.determinism`.

### `src/changelog.py` (NEW, pure/offline, 112 lines) -- #93

- **`Epoch`** dataclass; **`parse_roadmap_epochs(text)`** extracts epoch
  number/title + item lead-titles from roadmap Markdown (pure string transform,
  mirrors `src.unfinished`).
- **`render_changelog(version, date, epochs, *, notes)`** produces
  deterministic, byte-identical Keep-a-Changelog-style Markdown. The fs
  read/write lives in `tools/build_changelog.py`.

### `src/endpoints.py` additive (41 insertions) -- #92

- **`FLAGSHIP_E2E`** + **`flagship_e2e_requests()`**: the canonical Wahkiakum
  County, WA all-four-endpoints fixture, single source of truth shared by the
  e2e proof (`tests/test_endpoints_e2e.py`, refactored to consume it) and the
  release gate.

### `tools/release_gate.py` (NEW, 83 lines) -- #92

- Fixture-match preflight (`--offline-only`, runnable anywhere) or full gate
  (fixtures + real double-render via `tools/verify_determinism.py` per
  `--region`). Exit 0 READY / 1 BLOCKED / 2 usage.

### `tools/build_changelog.py` (NEW, 62 lines) -- #93

- Reads roadmap, calls `render_changelog`, writes `CHANGELOG.md`. `--check`
  compares without writing.

### `.github/workflows/ci.yml` (NEW, 44 lines) -- #91

- On push/PR to `main`: setup Python 3.12, `pip install -e .` + pytest, five
  steps -- `pytest -q`, `node tests/test_recipe_roundtrip.cjs`,
  `tools/coverage_report.py --quiet`, `release_gate.py --offline-only`,
  `build_changelog.py --check`.

### `.github/workflows/reproducibility.yml` (NEW, 52 lines) -- #91

- `workflow_dispatch` (per-region input) + weekly cron (Monday 06:00 UTC),
  targeting a self-hosted `[self-hosted, gdal]` runner. Full GIS stack install,
  `render_all_endpoints.py --check-determinism`, then
  `release_gate.py --region <r>`.

### `CHANGELOG.md` (NEW, 156 lines) -- #93

- 25 epochs, through v1.0. `--check` clean after generation.

### `pyproject.toml` version bump -- #93

- `version` set to `1.0.0`.

### Post-close fix (`1eeb81e`)

- `tools/verify_determinism.py` had a broken import path after the Gen-1
  restructuring; repaired so `release_gate.py`'s subprocess shell-out actually
  resolves.

### Tests (11 new)

| File | Count | Coverage |
|---|---|---|
| `tests/test_release.py` (NEW) | 7 | fixture pass/mismatch, ready/blocked logic, determinism required/optional, deterministic formatting |
| `tests/test_changelog.py` (NEW) | 4 | parse extracts epochs/items, render deterministic + byte-identical, notes, round-trip |
| `tests/test_endpoints_e2e.py` (EDIT) | -- | refactored to consume `flagship_e2e_requests()` single source; existing golden unchanged |

### Commit totals

18 files changed, 1204 insertions, 12 deletions. Full offline suite: **850
passed** (was 839; +11 new, no regressions).

## Real-data findings

No real-data run in this epoch by design. The spec scoped this as "author the
gate offline, run it on a capable host later." The offline preflight confirmed
both render-independent goldens recompute-match:

- `tools/release_gate.py --offline-only` exited 0 (READY).

The real double-render gate (byte-identical SVG determinism on the GDAL+NAS
machine) was deferred to the `reproducibility.yml` workflow on a self-hosted
runner. No bug-the-real-run-surfaced to report here. One post-close fix
(`1eeb81e`) repaired a broken import in `tools/verify_determinism.py` that
would have prevented the real gate from running -- the kind of wiring bug that
only surfaces when you actually shell out to the tool on a real host, not when
you test the pure core in isolation.

## Invariants held

- **Offline suite:** 850 passed (+11 new), no regressions.
- **2D default output byte-identical:** yes. Only `src/endpoints.py` changed
  among pipeline-adjacent modules, additively (41 insertions, 0 deletions); no
  pipeline/rendering/config/coloring bytes touched. `PIPELINE_STAGES` untouched.
- **`PIPELINE_STAGES` untouched:** yes. The commit adds `src/release.py` and
  `src/changelog.py` as parallel subsystem modules; touches no pipeline module.
- **Rights gate:** N/A -- no new art feature. The existing `assert_sellable`
  enforcement in `src/endpoints.py` and `src/fulfillment.py` is unchanged.
  `CHANGELOG.md` cites only public-domain data sources (USGS NHDPlus HR / NHD /
  WBD, NOAA nClimGrid).

## Graded against pre-analysis

No `planning/pre-analysis.md` exists for this spec. The spec's implicit risks
and the implementation report's verification section allow a narrative grade:

1. **Scope creep into rendering.** Refuted -- zero `PIPELINE_STAGES` change,
   zero renderer bytes, zero config change. The epoch stayed in the
   "gate + generate + wire" lane.
2. **Fixture drift (goldens stale after prior epochs).** Refuted --
   `release_gate.py --offline-only` passed on first run, meaning the gallery
   ledger and e2e contract digest committed by Epochs 21-22 were still
   consistent with the recomputed values.
3. **CI YAML validity.** Both workflows parse and are structurally sound
   (verified by YAML load + `--help` on the tools they invoke). The real CI
   test is the first push to a GitHub-hosted runner -- a carry-forward.
4. **`verify_determinism.py` wiring.** Confirmed as a real gap -- `1eeb81e`
   fixed a broken import path that the offline suite could not catch because
   it only tests the pure `src/release.py` core, not the subprocess shell-out.

## Carry-forwards (honestly open, not passed)

- **No real double-render gate run.** `tools/release_gate.py --region <r>`
  (the full, non-`--offline-only` mode) has not been exercised on a GDAL+NAS
  host. The `git tag v1.0` is blocked on this passing. This is the standing
  carry-forward from Epochs 9/10/14/16/18/19.
- **CI workflows untested on GitHub Actions.** `ci.yml` and
  `reproducibility.yml` are authored and YAML-valid but have not run on a real
  GitHub-hosted or self-hosted runner. The first push to `main` (or PR) is the
  real test.
- **`CHANGELOG.md` freshness.** The generated changelog covers through Epoch 25
  (v1.0); subsequent epochs will need a `tools/build_changelog.py` re-run. The
  `ci.yml` `--check` step guards against drift.
- **Lint baseline.** The 165-error ruff baseline is unchanged; not a regression,
  but also not addressed in this epoch.

## Generation 1 closeout

Epoch 23 is the final epoch of Generation 1 (Epochs 19-23, items #79-93).
Commit `3e8acf9` formally closed the generation with roadmap and HANDOFF
updates. The five Gen-1 epochs delivered:

| Epoch | What | Commit | Tests added |
|---|---|---|---|
| 19 | Endpoint contracts + dispatch | `d3f4e78` | +24 |
| 20 | Offline integration coverage + coverage gate | `f7f1c6d` | +15 |
| 21 | Flagship all-four-endpoints e2e proof | `26e8aee` | +15 |
| 22 | Curated marketing gallery + rights ledger | `db42655` | +17 |
| 23 | Release gate, CI, v1.0 packaging | `f233773` | +11 |

Total: 82 new tests across the generation, suite 768 -> 850. v1.0 is ready to
tag once the real double-render gate passes on a GDAL runner.

## Lessons

- **The offline/real-data split works for release gating.** The pure
  `src/release.py` core is testable offline (7 tests, deterministic); the real
  double-render lives in a tool that shells out. The only wiring bug (`1eeb81e`)
  was in the tool-to-tool shell-out path -- exactly the seam the offline suite
  cannot cover, and exactly the kind of bug that surfaces on first real use.
  Name this gap in the carry-forwards and fix it before tagging.
- **A changelog generator from the roadmap is near-free.** `src/changelog.py`
  is 112 lines of pure string transforms, but it gives the release a durable
  artifact and the CI a freshness check. The `parse_roadmap_epochs` function
  mirrors `src.unfinished` -- the project's habit of parsing its own docs pays
  off as reusable machinery.
- **CI authored last is fine when the suite is the real gate.** The offline
  suite was the working gate for 22 epochs before `ci.yml` existed. Authoring
  CI at the end (rather than the start) worked because the test discipline was
  already established -- CI just wrapped what was already running locally.
- **Consider a pre-analysis even for infrastructure epochs.** As with Epochs
  16, 18, and 19, no `pre-analysis.md` was written. The scope was small and
  risks low, but the `verify_determinism.py` import-path bug would have been
  on a watch-list if one existed. Cost is low; the graded retrospective is
  more useful than the narrative one.
