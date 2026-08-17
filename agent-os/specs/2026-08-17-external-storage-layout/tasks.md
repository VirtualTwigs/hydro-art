# Tasks — External-storage layout & output migration (roadmap #29)

TDD, one task group at a time: write 2–8 tests first per group and run ONLY those,
then implement to green. `src/storage.py` stays stdlib-only and offline-testable.

## TG1 — Storage root resolution (`src/storage.py`)

- [ ] Write tests first (`tests/test_storage.py`): with no external root and
      `local_root="."`, `resolve_storage()` yields `Path("cache")` /
      `Path("datasets")` / `Path("output")` and `using_external` False (default
      byte-identical); an external root with `available=lambda _: True` yields the
      three `<root>/<kind>` subdirs and `using_external` True; the same root with
      `available=lambda _: False` falls back to the local defaults with
      `using_external` False (never points at the unmounted mount); a per-kind
      `overrides` entry wins over both external and local; `env[EXTERNAL_ROOT_ENV]`
      supplies the root when the arg is omitted, and the explicit arg beats the
      env; `staging` surfaces on `StorageRoots`; `drive_available` true when the
      root or its parent exists, false otherwise.
- [ ] `src/storage.py`: `StorageError`, `DEFAULT_LOCAL_ROOTS`,
      `EXTERNAL_ROOT_ENV`, frozen `StorageRoots`, `drive_available`, and pure
      `resolve_storage(...)` with the documented precedence + injectable
      `available` probe (stdlib only; no numpy/GDAL; not in `PIPELINE_STAGES`).
- [ ] Run ONLY the new tests; green.

## TG2 — Migration planner + executor (`src/storage.py`)

- [ ] Write tests first (`tests/test_storage.py`): `plan_migration` over a
      populated `tmp_path` tree enumerates every file sorted by source with a
      summed `total_bytes`; a destination file of the same size is `skipped`
      (idempotent); a missing `source_dir` yields an empty plan (no error);
      `apply_migration` moves every file, replaces the source dir with a symlink to
      the destination, and a known file resolves through the link
      (`(source_dir / name)` reads the moved bytes); an unmounted destination
      (`require_mounted=True` + failing probe) raises `StorageError` before any
      `mover` call (fake mover asserts not called); a partially pre-migrated tree
      re-runs to completion (resumable) and then symlinks.
- [ ] `src/storage.py`: frozen `MigrationItem` / `MigrationPlan` /
      `MigrationResult`, `plan_migration(source_dir, dest_dir)` (pure, no writes),
      and `apply_migration(plan, *, symlink=True, mover=shutil.move,
      require_mounted=True)` (mount guard → `StorageError`; per-file move;
      trailing directory symlink only when the source is fully drained).
- [ ] Run ONLY the new tests; green.

## TG3 — Entry-point wiring (`build.py`, `serve.py`)

- [ ] Write/extend tests (`tests/test_build.py`, `tests/test_serve.py`): `build.py`
      resolves `--external-root` / `--datasets-dir` / `--output-dir` (+ the
      `HYDRO_ART_EXTERNAL_ROOT` env) through `resolve_storage` and passes the
      resolved roots to the injected `Pipeline` (assert the pipeline saw the
      expected dirs; assert an unset external root + unmounted NAS keeps today's
      local defaults); `serve.py`'s cache resolution still honors `--cache-dir` and
      the NAS-when-mounted/local-else default via the generalized resolver.
- [ ] `build.py`: add the flags, call `resolve_storage`, pass
      `roots.cache/datasets/output` to `Pipeline`, log the resolved roots +
      `using_external`; keep the NAS default (external root defaults to the NAS
      path when unset and mounted, else local) so no-flag builds are unchanged.
      `serve.py`: delegate `_resolve_cache_dir` (and the datasets/output roots) to
      `resolve_storage`, preserving the existing default + `--cache-dir` override.
- [ ] Run ONLY the new/changed tests; green.

## TG4 — Migration CLI + optional local staging + verify/docs

- [ ] Add `tools/migrate_storage.py`: a thin CLI over `plan_migration` /
      `apply_migration` — `--external-root` (or env, required), `--kind`
      (`output` default, repeatable; `datasets` opt-in), `--dry-run` (print plan
      only), `--no-symlink`; verify the drive is mounted (`drive_available`) and
      exit non-zero with the `StorageError` message otherwise; print per-kind
      results. Not in the offline suite (moves real files); smoke-test `main()`
      against a `tmp_path` external root (dry-run, real move + symlink, unmounted
      guard).
- [ ] (Optional local working copy) Thread `StorageRoots.staging` into the export
      path: when set, `_export_stage` writes each artifact into the local staging
      dir and moves the finished file to `ctx.output_dir`; when `None`, write
      directly (default, byte-identical). Guarded so a no-staging build is
      unchanged; extend `tests/test_export_pipeline.py` (or add a focused test) to
      cover the move-on-finish path.
- [ ] Confirm `src/storage.py` imports offline (no numpy/GDAL pulled in); `ruff`
      if available.
- [ ] Run the full Python suite (regression check); note the count.
- [ ] Write `implementation/report.md`; tick this `tasks.md`; update `HANDOFF.md`,
      the `CLAUDE.md` module map (new `src/storage.py` + `tools/migrate_storage.py`,
      and the build.py/serve.py storage-resolution note), and mark roadmap #29
      `[x]` with an evidence note. Report; STOP (commit is a separate explicit
      step).
