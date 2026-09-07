# Requirements — Epoch 23: Release packaging, CI & reproducibility gate

## Functional

### #91 — CI for the full test pyramid
- A CI workflow runs the **offline** pyramid (unit + integration + e2e) on every push/PR:
  install the minimal core deps, run `pytest -q`, run the CommonJS recipe roundtrip
  (`node tests/test_recipe_roundtrip.cjs`), and report coverage (`tools/coverage_report.py`).
- A **separate, gated** job (manual `workflow_dispatch` / scheduled) is defined for the opt-in
  real-data e2e + determinism (`tools/render_all_endpoints.py --check-determinism`,
  `tools/verify_determinism.py`). It is documented as requiring GDAL + staged NAS data, so it
  does not run on the hosted offline runner by default.

### #92 — Reproducibility release gate
- A **pure/offline** release-gate core (`src/release.py`) that:
  - Recomputes the **render-independent** golden fixtures (gallery ledger, e2e contract digest)
    and asserts each matches its committed file; validates every golden JSON parses.
  - Aggregates `src.determinism.DeterminismVerdict`s (from the non-offline double-render, passed
    in) — all must pass.
  - Produces a `ReleaseVerdict` (ready/blocked + per-check reasons), byte-stable formatting.
- A `tools/release_gate.py` CLI wires the pure core to the real double-render + prints the
  verdict; **exit non-zero blocks the tag** unless determinism holds and fixtures match.
- Single source of truth for the flagship e2e request set (`flagship_e2e_requests` in
  `src/endpoints.py`) so the test and the release core recompute the same golden.

### #93 — Version, changelog & distribution packaging
- Bump `pyproject.toml` version to `1.0.0`.
- A **pure/offline** changelog generator (`src/changelog.py`) that turns parsed epoch/roadmap
  data → a deterministic `CHANGELOG.md` document (mirrors `src/status.py`/`src/unfinished.py`).
- A `tools/build_changelog.py` CLI that reads the roadmap + retrospectives and writes
  `CHANGELOG.md`.
- Generate + commit `CHANGELOG.md` covering the epoch history through v1.0.

## Non-functional / discipline
- **Offline suite stays offline:** `src/release.py`, `src/changelog.py` + their tests import
  only stdlib + existing `src.*` (no GDAL/network/`web`/`tools`).
- **Byte-identical default build:** nothing enters `PIPELINE_STAGES`; no renderer/config bytes
  change.
- **TDD:** 2–8 focused tests first per group; run only those until green; full suite at end.
- **No autonomous tag:** `git tag v1.0` is deferred to an explicit user step.

## Out of scope
- Publishing to PyPI or any external registry (packaging metadata only).
- Standing up a live CI service / connecting a runner (workflow files are the deliverable).
