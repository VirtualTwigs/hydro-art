# Implementation Report: Release packaging, CI & reproducibility gate (Epoch 23, #91–93)

## Summary
The close of Generation 1: hardens "green suite + artifacts" into a tagged, reproducible
**v1.0**. Adds a pure/offline reproducibility release-gate core and a changelog generator (both
`src/`, offline-tested), CI wiring the offline pyramid plus a gated real-data job, a version bump
to `1.0.0`, and a generated `CHANGELOG.md`. No art feature, no `PIPELINE_STAGES` change; the
default 2D build stays byte-for-byte identical; public-domain sources only. **The `git tag v1.0`
is deferred to an explicit user step** — everything below makes that a one-command finish.

## What shipped

### TG1 — Reproducibility release-gate core (`src/release.py`, #92)
- Flagship single source of truth: `FLAGSHIP_E2E` + `flagship_e2e_requests()` added to
  `src/endpoints.py` (additive); `tests/test_endpoints_e2e.py` refactored to build its request
  set from it (e2e golden unchanged). Lets the release core recompute the e2e digest without
  duplicating the flagship definition.
- `FixtureCheck` / `ReleaseVerdict` (frozen) + `RELEASE_SCHEMA = "hydro-art/release-gate@1"`.
- `check_render_independent_goldens()` recomputes the render-independent goldens (gallery ledger
  via `src.gallery.gallery_ledger`; flagship e2e digest via `e2e_contract_digest`) and compares
  parsed-JSON to the committed fixtures — never raises, returns a full punch list.
- `evaluate_release(version, *, determinism_verdicts, require_determinism)` aggregates fixture
  checks + `src.determinism.DeterminismVerdict`s into a ready/blocked verdict; `format_verdict`
  renders a deterministic report.
- Offline: imports only stdlib + `src.gallery` + `src.endpoints` + `src.determinism`.
- Tests: `tests/test_release.py` (7) — fixtures pass on committed goldens; mismatch detected;
  ready/blocked logic (determinism required/optional); deterministic formatting.

### TG2 — Changelog generator (`src/changelog.py`, #93)
- Pure string/data transforms (stdlib only), mirroring `src.unfinished`/`src.status`: `Epoch`
  dataclass; `parse_roadmap_epochs(text)` extracts epoch number/title + item lead-titles from
  roadmap Markdown; `render_changelog(version, date, epochs, *, notes)` → deterministic,
  byte-identical Markdown. The fs read/write lives in the `tools/` CLI.
- Tests: `tests/test_changelog.py` (4) — parse extracts epochs/items; render deterministic +
  byte-identical; notes; parse→render round-trip stable.

### TG3 — CLIs + CI + version bump (#91/#93, non-suite)
- `tools/release_gate.py`: fixture-match preflight (`--offline-only`, runnable anywhere) or the
  full gate (fixtures + real double-render by shelling out to `tools/verify_determinism.py` per
  `--region`). Exit 0 READY / 1 BLOCKED / 2 usage.
- `tools/build_changelog.py`: reads the roadmap → `render_changelog` → writes `CHANGELOG.md`
  (`--check` compares without writing).
- `.github/workflows/ci.yml`: offline pyramid on push/PR — `pytest -q`, Node recipe roundtrip,
  `tools/coverage_report.py`, `release_gate.py --offline-only`, `build_changelog.py --check`.
- `.github/workflows/reproducibility.yml`: gated (`workflow_dispatch` + weekly `schedule`)
  real-data e2e + determinism, targeting a self-hosted `gdal` runner with staged datasets.
- `pyproject.toml` version → `1.0.0`.

### TG4 — Release artifacts + gate (#93)
- Generated + committed `CHANGELOG.md` (25 epochs, through v1.0); `--check` clean afterward.

## Verification
- `tests/test_release.py`: 7 passed; `tests/test_changelog.py`: 4 passed.
- Full offline suite: **850 passed** (was 839; +11 new).
- `tools/release_gate.py --offline-only` → READY (both render-independent goldens match).
- Offline discipline: `src/release.py`, `src/changelog.py` + tests import no GDAL/network/`web`/
  `tools` (verified by grep); tools + workflows live outside the suite; both tools compile +
  run `--help`; both workflow YAMLs parse.
- Byte-identical default build: only `src/endpoints.py` changed among tracked `src/` — additive
  (41 insertions, 0 deletions), a parallel subsystem outside `PIPELINE_STAGES`; no
  pipeline/rendering/config/coloring bytes touched.

## Deferred (the release tag itself)
- `git tag v1.0` is an explicit, user-authorized step (like "commit item #N").
- The **real** reproducibility gate (double-render byte-identity on the GDAL+NAS machine via
  `tools/release_gate.py --region <r>`) must pass before tagging; the offline suite cannot run
  it. CI's `reproducibility.yml` is where it runs on a capable runner.

## Generation 1 — done
All five Gen-1 epochs (19 endpoint contracts, 20 unit/integration, 21 flagship e2e, 22 marketing
gallery, 23 release/CI/reproducibility) are implemented. v1.0 is ready to tag once the real
double-render gate passes on a GDAL runner and the user authorizes the tag.
