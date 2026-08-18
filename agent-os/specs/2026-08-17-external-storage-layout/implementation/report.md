# Implementation Report — External-storage layout & output migration (roadmap #29)

## Summary

Added `src/storage.py`: a pure, deterministic, offline module that (A) resolves
the cache / datasets / output roots to a configurable external-drive location
with a mount-aware local fallback, and (B) plans and executes a one-time
migration of an existing local directory (default `output/`) onto the drive,
leaving a directory symlink behind so paths that still reference the local
location keep resolving. The resolver is wired into `build.py` and `serve.py`,
an optional local-staging working copy is threaded through the export stage, and
a thin `tools/migrate_storage.py` CLI drives the executor. Storage location is
infrastructure resolved *before* the `Pipeline` is built — it is **not** part of
`Settings`, not in `PIPELINE_STAGES`, and never affects rendered bytes. A
no-flag, no-env build is byte-identical to before.

## Changes

- **`src/storage.py`** (new, stdlib-only) — `StorageError`, `DEFAULT_LOCAL_ROOTS`,
  `EXTERNAL_ROOT_ENV`, frozen `StorageRoots`, `drive_available` (root or its
  parent/mount-point exists), and pure `resolve_storage(...)` with precedence
  `override[kind] > external_root/kind (when available) > local_root/default`.
  Migration half: frozen `MigrationItem` / `MigrationPlan` / `MigrationResult`,
  pure `plan_migration` (sorted rglob, same-size files → `skipped`, missing
  source → empty plan), and `apply_migration` (mount guard → `StorageError`
  before any move; per-file move via injectable `mover`; trailing directory
  symlink only when the source is fully drained). No numpy/GDAL/shapely.
- **`src/cli.py`** — added storage flags to `build_parser()`
  (`--external-root`, `--cache-dir`, `--datasets-dir`, `--output-dir`,
  `--staging`), deliberately excluded from `cli_overrides` so they never leak
  into the deterministic `Settings`. Split `resolve_settings(argv)` into
  `settings_from_args(args)` (the body) + `resolve_settings` (parse then
  delegate), so an entry point can parse `argv` once and also read the storage
  flags off the same namespace.
- **`build.py`** — new `_default_cache_dir` + `_storage_roots(args)`: builds
  per-kind `overrides` from the explicit dir flags, reads
  `--external-root`/`$HYDRO_ART_EXTERNAL_ROOT`, and — to preserve today's
  behavior — injects the NAS-or-local cache as an explicit override **only when
  no external root is configured** (with an external root, cache resolves to
  `<root>/cache`). `main()` parses once via `build_parser`, validates through
  `settings_from_args`, logs the resolved roots + `(external drive)`, and passes
  `roots.cache/datasets/output/staging` to `Pipeline`.
- **`serve.py`** — new `_serve_roots(...)`: when an external root (flag or env)
  is present it delegates to `resolve_storage` (all three kinds onto the drive);
  otherwise it keeps serve's NAS-when-mounted-else-local cache default (via the
  unchanged `_resolve_cache_dir`) with local `datasets`/`output`. `main()` gains
  `--external-root`, logs the resolved roots, and passes all three to the
  `Pipeline` behind the `JobRunner`. The existing `_resolve_cache_dir` and its
  three tests are untouched.
- **`src/pipeline.py`** — `RunContext`/`Pipeline` gain an optional
  `staging_dir`. `_export_stage` writes each artifact into `staging_dir` first
  and `shutil.move`s the finished file to `output_dir` when staging is set,
  reporting the final output path in `export_paths`; `staging_dir=None` (default)
  writes straight to `output_dir` — byte-identical. `build.py` forwards
  `roots.staging`.
- **`tools/migrate_storage.py`** (new, thin CLI) — `--external-root` (or env,
  required), `--kind` (`output` default, repeatable; `datasets` opt-in),
  `--local-root`, `--dry-run`, `--no-symlink`. Verifies the drive is mounted
  (`drive_available`) and exits non-zero with the `StorageError` message
  otherwise, before moving anything; prints per-kind file count / bytes /
  results. Imports only stdlib + the GDAL-free `src.storage`. Invoked as
  `python -m tools.migrate_storage` (same convention as `tools/package_cache.py`).

## Tests

- `tests/test_storage.py` (new, 14): 8 resolution (default local, external
  expands all kinds, unmounted fallback, per-kind override wins, env supplies
  root, arg beats env, `staging` surfaces, `drive_available` root/parent probe)
  + 6 migration (sorted plan + summed bytes, same-size skip, missing source →
  empty plan, move + symlink + resolve-through-link, unmounted guard raises
  before any `mover` call, resumable partial re-run).
- `tests/test_build.py` (+4): defaults local when NAS unmounted; cache defaults
  to NAS when mounted (datasets/output stay local); `--external-root` expands all
  three kinds; explicit `--output-dir` overrides the external root.
- `tests/test_serve.py` (+3): `_serve_roots` default keeps local datasets/output;
  external root resolves all three; env var supplies the root.
- `tests/test_migrate_storage.py` (new, 4, offline): missing-root error;
  dry-run moves nothing; real move + symlink resolves through the link;
  unmounted-drive guard leaves the source untouched.
- `tests/test_export_pipeline.py` (+1): staging renders locally then moves to
  output; `export_paths` report the final output path and staging is left empty.

## Verification

- Full suite: **488 passed** (was 462; +26), fully offline (no GDAL, no network).
  Only the pre-existing "svgo not found" warnings.
- Offline guard: `import src.storage` / `import tools.migrate_storage` pulls in no
  numpy / shapely / geopandas.
- Smoke: `python -m tools.migrate_storage --external-root /tmp/… --dry-run`
  reports the real `output/` tree (352 files, 2.3 GiB) and exits 0; missing-root
  and unmounted-drive both exit 1 with a clear message. `build.py --help` and
  `serve.py --help` surface the new storage flags.
- `ruff` is not installed in this `.venv`, so the lint pass was skipped; code
  follows the module style (annotations import, docstrings, `__all__`, 88-col,
  frozen dataclasses).

## Out of scope (as specced)

- A `config.yaml` `storage:` block.
- Migrating the download cache/datasets by default (datasets is opt-in only).
- Portable-bundle zipping (that is #21's packaging planner).
- Any change to rendered bytes, `Settings`, or `PIPELINE_STAGES`.
