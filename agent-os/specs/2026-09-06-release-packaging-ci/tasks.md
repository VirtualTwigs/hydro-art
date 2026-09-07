# Task Breakdown: Release packaging, CI & reproducibility gate (Epoch 23, #91–93)

## Overview
Total: 4 task groups. Close Generation 1: a pure/offline reproducibility release-gate core and
changelog generator (both `src/`, tested), CI wiring the offline pyramid + a gated real-data job,
version bump + generated `CHANGELOG.md`. No art feature, no `PIPELINE_STAGES` change; default 2D
build BYTE-FOR-BYTE identical; the `git tag v1.0` is deferred to an explicit user step.

## Cross-cutting constraints
- **TDD:** 2–8 focused tests FIRST per group; run ONLY those until green.
- **Offline discipline:** `src/release.py`, `src/changelog.py` + tests import ONLY stdlib +
  existing `src.*`; NO GDAL/network/`web`/`tools`. `tools/*` + `.github/*` live OUTSIDE the suite.
- **Byte-identical default:** no pipeline/renderer/config bytes change; verify before closing.

---

## Task List

### Task Group 1: Reproducibility release-gate core — `src/release.py` (#92)
**Dependencies:** Epoch 22 (`src/gallery.py`), Epoch 21 (`src/endpoints.py`, `src/determinism.py`)

- [x] 1.0 Flagship single-source + release-gate core + tests
  - [x] 1.1 Add `FLAGSHIP_E2E` + `flagship_e2e_requests()` to `src/endpoints.py` (+ `__all__`);
    refactor `tests/test_endpoints_e2e.py` to build its request set from it (golden unchanged).
  - [x] 1.2 Write tests FIRST in `tests/test_release.py`:
    - `check_render_independent_goldens()` all-pass on the committed fixtures (gallery + e2e).
    - a tampered/mismatched recompute → that check fails.
    - `evaluate_release` ready when fixtures pass + a passing determinism verdict; blocked when a
      verdict fails; blocked when `require_determinism` and none supplied.
    - `format_verdict` is deterministic + names the failing check.
    - Run ONLY these tests.
  - [x] 1.3 Implement `FixtureCheck`, `ReleaseVerdict`, `RELEASE_SCHEMA`,
    `check_render_independent_goldens`, `evaluate_release`, `format_verdict`, `__all__`.
  - [x] 1.4 Run ONLY 1.1–1.2 tests (+ the e2e golden test) until green.

**Acceptance:** offline core recomputes the render-independent goldens + aggregates determinism
verdicts into a ready/blocked verdict; e2e single-source; offline; green.

---

### Task Group 2: Changelog generator — `src/changelog.py` (#93)
**Dependencies:** none (pure)

- [x] 2.0 Pure changelog transforms + tests
  - [x] 2.1 Write tests FIRST in `tests/test_changelog.py`:
    - `render_changelog(version, date, epochs)` → deterministic Markdown (title, version+date,
      grouped epochs + items); byte-identical for equal inputs.
    - `parse_roadmap_epochs(text)` extracts epoch number/title + items from sample roadmap text.
    - round-trip: parse sample → render → stable.
    - Run ONLY these tests.
  - [x] 2.2 Implement `Epoch`, `render_changelog`, `parse_roadmap_epochs`, `__all__` (stdlib only).
  - [x] 2.3 Run ONLY the 2.1 tests until green.

**Acceptance:** deterministic changelog from structured/roadmap input; pure/offline; green.

---

### Task Group 3: CLIs + CI workflows + version bump (#91/#93)
**Dependencies:** TG1, TG2

- [x] 3.0 Non-suite wiring
  - [x] 3.1 `tools/release_gate.py`: fixture checks + (optional) real double-render; print
    `format_verdict`; exit non-zero unless ready; `--offline-only` flag. Compile + `--help`.
  - [x] 3.2 `tools/build_changelog.py`: read roadmap + retrospectives → `render_changelog` →
    write `CHANGELOG.md` (`--check` compares only). Compile + `--help`.
  - [x] 3.3 `.github/workflows/ci.yml` (offline pyramid) + `.github/workflows/reproducibility.yml`
    (gated real-data job). YAML parses.
  - [x] 3.4 Bump `pyproject.toml` version → `1.0.0`.

**Acceptance:** tools compile + run `--help`; workflows parse; version bumped; outside the suite.

---

### Task Group 4: Release artifacts + regression gate (#93)
**Dependencies:** TG1–TG3

- [x] 4.0 Changelog + full suite + report
  - [x] 4.1 Generate + commit `CHANGELOG.md` via `tools/build_changelog.py`; confirm `--check`
    is clean afterward.
  - [x] 4.2 Run the FULL offline suite; confirm no new GDAL/network import in `src/`/`tests/`;
    default 2D build byte-identical.
  - [x] 4.3 Write `implementation/report.md`; note `git tag v1.0` is the deferred explicit step.

**Acceptance:** `CHANGELOG.md` committed + `--check` clean; full offline suite green; default
build byte-for-byte identical. Item gate: v1.0 is ready to tag once the pyramid is green,
determinism holds (real run), and the gallery + docs ship — the tag itself is the user's call.

---

## Execution Order
1. Release-gate core + flagship single-source (TG1).
2. Changelog generator (TG2).
3. CLIs + CI + version bump (TG3).
4. Release artifacts + gate (TG4).
