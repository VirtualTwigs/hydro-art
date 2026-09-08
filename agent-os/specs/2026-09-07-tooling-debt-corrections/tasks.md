# Tasks — Tooling debt corrections (Track C2)

One task group; TDD. Corrections roadmap Track C2 (C2.1 shim, C2.2 ruff, C2.3 CWD-anchored caches).

## Task Group 1 — Tooling debt (C2.1 + C2.2 + C2.3)

- [x] 1.0 Tests first (run only `tests/test_tools_direct_run.py`; must be RED on today's tree):
  - [x] 1.1 `test_direct_run_tools_have_src_import_shim` — every `tools/*.py` with `__main__` + a
    `src` import has a `sys.path.insert` before its first `src` import. (Fails: 7 tools missing.)
  - [x] 1.2 `test_report_caches_are_repo_anchored` — no bare CWD-relative cache/figure literal in
    `report_common.py` / `render_state_yoy.py`. (Fails: 3 literals.)
  - [x] 1.3 `test_ruff_pinned_in_dev_extras` — `ruff` present in `[project.optional-dependencies].dev`.
    (Fails: only pytest.)
  - [x] 1.4 `test_pure_tools_run_as_script_from_foreign_cwd` — subprocess `--help` of
    `detect_unfinished.py` + `update_status.py` from a tmp CWD exits 0, no `ModuleNotFoundError`.
    (Fails red for both today.)
- [x] 1.5 C2.1 — add the canonical shim (`sys.path.insert(0, str(Path(__file__).resolve().parent.parent))`)
  before the first `src` import in the 7 tools; add `from pathlib import Path` to `acquire_dem`,
  `cache_manifest`, `package_cache`.
- [x] 1.6 C2.2 — add `ruff>=0.6` to `pyproject.toml` dev optional-dependencies.
- [x] 1.7 C2.3 — promote a `REPO` constant in `report_common.py` + `render_state_yoy.py`; anchor
  `FIG_DIR`, `clip_cache`, `_yoy_net` cache to it.
- [x] 1.8 Run `tests/test_tools_direct_run.py` — green (4).
- [x] 1.9 Full offline suite for regressions; confirm no `src/` or `PIPELINE_STAGES` edit
  (2D default byte-identical). Tick roadmap C2 items; write `implementation/report.md`.
