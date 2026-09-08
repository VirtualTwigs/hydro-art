# Requirements — Tooling debt corrections (Track C2)

## Source
Corrections roadmap (`agent-os/product/corrections-roadmap.md`), **Track C2 — Tooling debt**.
Distilled from epoch retrospectives (Epochs 9, 12, and the Generation-1 production-release
closeout). Three cheap, fully-offline fixes with high recurrence.

## Discipline (carried from the standing rules)
- **Nothing enters `PIPELINE_STAGES`.** The 2D pipeline's byte-for-byte default output is untouched
  (this track edits only `tools/` shims, `pyproject.toml`, and adds `tests/`).
- `src/` is not modified. `src/flow_metrics.py` / `src/monthly_flow.py` stay numpy-only.
- TDD: write the regression tests first (they must fail red against today's tree), then fix to green.
  Run only the new test module during the group; full offline suite at the end for regressions.
- Fixes must be **behavior-preserving for the normal case**: a tool run the usual way
  (`python -m tools.x` from repo root, or from repo-root CWD) behaves exactly as before; the fix only
  adds correctness for the direct-run / foreign-CWD cases.

## Scope by item

### C2.1 — Direct-run `src`-import shim, applied everywhere
`python tools/<x>.py` fails with `ModuleNotFoundError: No module named 'src'` for any tool that
imports `from src.*` without putting the repo root on `sys.path`. It only works via
`python -m tools.<x>` (module mode). Seven tools currently import `src`, define
`if __name__ == "__main__"`, and lack the shim:

    acquire_dem.py   cache_manifest.py   detect_unfinished.py   migrate_storage.py
    monthly_flow.py  package_cache.py    update_status.py

`detect_unfinished.py` is the SessionStart-hook entry point, so this bug bit a live workflow.
Fix: insert the canonical shim used by the other 31 tools —
`sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` — **before** the first `from src`
import in each of the 7. Three of them (`acquire_dem`, `cache_manifest`, `package_cache`) do not yet
import `pathlib.Path`; add that import.

**Regression guard:** a static, offline test asserting the class-wide invariant "every tool that
runs as `__main__` and imports `src` has a `sys.path.insert` before its first `src` import" — so a
future tool cannot silently reintroduce the bug.

### C2.2 — Pin `ruff`
`ruff` is the configured linter (`[tool.ruff] line-length = 88`) but is absent from
`pyproject.toml`'s `dev` optional-dependencies (only `pytest>=8.0`), so `ruff check src tests` fails
on a clean env until a manual `pip install`. Fix: add `ruff` to `[project.optional-dependencies].dev`.

### C2.3 — CWD-independent report caches
`tools/report_common.py` resolves its figure/cache paths relative to the current working directory:
`FIG_DIR = Path("notebooks/figures")` and `clip_cache = Path(f"output/_wshed_{tag}_mo{min_order}.pkl")`;
its `yearly_flow_by_id` collaborator in `tools/render_state_yoy.py` builds
`Path(f"output/_yoy_net_{code}.pkl")` the same way. Under `jupyter nbconvert` (CWD = notebook dir)
these miss and fall through to a live WBD read (Epoch 12 gotcha). Fix: anchor all three to a REPO
root derived from `__file__`, so the paths are identical when run from repo root but correct from any
CWD.

## Out of scope
- The other correction tracks (C1 process, C3 features, C4 host-gated, C5 data). One item at a time.
- Refactoring tool internals, adding new tool behavior, or changing any rendered bytes.
- The 39 tools that already carry the shim (verified present) — untouched.

## Acceptance
- The 7 tools run as `python <abs-path>/tools/<x>.py --help` from a foreign CWD without
  `ModuleNotFoundError` (proven for the two pure tools via an e2e subprocess test).
- `ruff` is declared in dev deps.
- `report_common` / `render_state_yoy` carry no bare CWD-relative cache/figure literal.
- New regression tests are green; full offline suite shows no regressions; no `PIPELINE_STAGES` edit.
