# Spec: Release packaging, CI & reproducibility gate (Epoch 23, #91–93)

Fifth and final epoch of Generation 1: harden "green suite + artifacts" into a tagged,
reproducible **v1.0**. No art feature; the pure halves of the release gate + changelog live in
`src/` (offline-tested), the real-data/double-render halves stay in `tools/`, and CI wires the
pyramid. Default 2D output stays byte-for-byte identical; public-domain sources only.

## Design

### 1. Flagship e2e single source — `src/endpoints.py` (additive) — supports #92
- Add `FLAGSHIP_E2E` (region/county/style + per-endpoint extras) + `flagship_e2e_requests()`
  returning one validated `EndpointRequest` per endpoint. Refactor `tests/test_endpoints_e2e.py`
  to build its request set from this single source (golden unchanged). Lets the release core
  recompute the e2e contract digest without duplicating the flagship definition.

### 2. Offline release-gate core — `src/release.py` (offline) — #92
- `FixtureCheck(name, ok, detail)` + `ReleaseVerdict(version, fixture_checks,
  determinism_verdicts)` frozen dataclasses; `RELEASE_SCHEMA = "hydro-art/release-gate@1"`.
- `check_render_independent_goldens(*, root=GOLDEN_ROOT)` → recompute the gallery ledger
  (`src.gallery.gallery_ledger`) and the e2e contract digest
  (`src.endpoints.e2e_contract_digest(flagship_e2e_requests())`) and compare (parsed-JSON) to
  the committed fixtures; also assert every `*.json` under the golden root parses.
- `evaluate_release(version, *, determinism_verdicts=(), root=GOLDEN_ROOT,
  require_determinism=True)` → `ReleaseVerdict`. `ready` iff all fixture checks pass **and**
  (determinism not required, or ≥1 verdict supplied and every verdict `.ok`).
- `format_verdict(verdict)` → human-readable block (mirrors `src.determinism.format_verdict`).
- Imports only stdlib + `src.gallery` + `src.endpoints` + `src.determinism`.

### 3. Changelog generator — `src/changelog.py` (offline) — #93
- Pure transforms over structured input (no fs/network in `src/`): `Epoch(number, title, date,
  items:[(id, text)])`; `render_changelog(version, date, epochs, *, notes=None)` → deterministic
  Markdown (Keep-a-Changelog-ish: title, version+date, grouped epochs with their items).
- `parse_roadmap_epochs(text)` → `[Epoch,...]` from the roadmap Markdown (pure string transform,
  mirrors `src.unfinished`); the fs read lives in the `tools/` CLI.

### 4. CLIs (non-suite) — `tools/` — #91/#92/#93
- `tools/release_gate.py`: run the pure fixture checks + (optional) real double-render via the
  existing `verify_determinism` path, print `format_verdict`, exit non-zero when not `ready`.
  `--offline-only` skips the double-render (fixture-match gate only, runnable anywhere).
- `tools/build_changelog.py`: read roadmap + retrospectives, call `render_changelog`, write
  `CHANGELOG.md` (`--check` compares without writing). Standard `sys.path` insert.

### 5. CI workflows — `.github/workflows/` — #91
- `ci.yml`: on push/PR — setup Python 3.12, `pip install -e .` (+ pytest), `pytest -q`,
  `node tests/test_recipe_roundtrip.cjs`, `python tools/coverage_report.py` (report-only).
- `reproducibility.yml`: `workflow_dispatch` + scheduled — documented real-data gate
  (`tools/release_gate.py`, `tools/render_all_endpoints.py --check-determinism`); guarded so it
  no-ops without GDAL/NAS (the real run happens on a capable runner).

### 6. Packaging + release artifacts — #93
- `pyproject.toml` version → `1.0.0`.
- Generate + commit `CHANGELOG.md` (through v1.0).
- `git tag v1.0` is DEFERRED to an explicit user step (documented in the report).

## Discipline / invariants
- `src/release.py`, `src/changelog.py` + tests: stdlib + existing `src.*` only; no
  GDAL/network/`web`/`tools`.
- Nothing enters `PIPELINE_STAGES`; default 2D build byte-identical.
- `tools/*` + `.github/*` outside the suite; TDD per group; full suite at the end.

## Files
- EDIT `src/endpoints.py` (+ `FLAGSHIP_E2E`, `flagship_e2e_requests`, `__all__`)
- EDIT `tests/test_endpoints_e2e.py` (use the single source)
- NEW `src/release.py`, `tests/test_release.py`
- NEW `src/changelog.py`, `tests/test_changelog.py`
- NEW `tools/release_gate.py`, `tools/build_changelog.py`
- NEW `.github/workflows/ci.yml`, `.github/workflows/reproducibility.yml`
- EDIT `pyproject.toml` (version 1.0.0)
- NEW `CHANGELOG.md`
- NEW `agent-os/specs/2026-09-06-release-packaging-ci/implementation/report.md`
