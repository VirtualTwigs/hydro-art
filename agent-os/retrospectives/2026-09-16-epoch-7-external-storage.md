# Retrospective — Epoch 7: External storage & data operations (#29)

_Closed 2026-08-17 (main commit `87bc123`, follow-up fixes through `38ea2ce`).
Retro written 2026-09-16. One roadmap item, four task groups, one real-data
migration onto the Synology NAS._

## What the epoch was

Move the project's bulk I/O roots -- the download cache, extracted GDB datasets,
and rendered output -- off local disk onto a configurable external drive, without
touching the deterministic 2D pipeline or `Settings`. The motivating constraint:
~35 GB local free space vs. 18.8 GiB of datasets and 2.3 GiB of rendered output.
The hard invariant: **storage location is infrastructure resolved before the
`Pipeline` is built; a no-flag, no-env build is byte-identical.**

## What shipped

### `src/storage.py` (new, stdlib-only, `87bc123`)

Pure, deterministic, offline module. Two halves:

- **Root resolution** -- `resolve_storage(...)` maps one `--external-root` (or
  `$HYDRO_ART_EXTERNAL_ROOT`) into `cache`/`datasets`/`output` subdirs with
  per-kind explicit overrides and a mount-aware local fallback
  (`drive_available` = root or its parent/mount-point exists). Precedence:
  `override[kind] > external_root/kind (when available) > local_root/default`.
  Resolution is a pure function of its arguments (env + probe injected); it
  **never raises and never creates directories under an unmounted mount point**.
- **Migration** -- `plan_migration` (pure, no writes: sorted rglob, same-size
  files -> `skipped`, missing source -> empty plan) + `apply_migration`
  (mount guard -> `StorageError` before any move; per-file move via injectable
  `mover`; trailing directory symlink only when the source is fully drained).
  Frozen dataclasses: `MigrationItem`, `MigrationPlan`, `MigrationResult`.

### Entry-point wiring (`87bc123`)

- **`build.py`** -- new `--external-root`, `--datasets-dir`, `--output-dir`,
  `--staging` flags; `_storage_roots(args)` calls `resolve_storage`, logs the
  resolved roots + `(external drive)`, passes `roots.cache/datasets/output` to
  `Pipeline`. NAS-when-mounted cache default preserved when no external root is
  configured.
- **`serve.py`** -- new `_serve_roots(...)` delegates to `resolve_storage` when
  an external root is present; otherwise keeps the existing NAS-when-mounted
  `_resolve_cache_dir` default.
- **`src/pipeline.py`** -- `RunContext`/`Pipeline` gain optional `staging_dir`.
  `_export_stage` writes to the staging dir first and `shutil.move`s the
  finished file to `output_dir` when set; `staging_dir=None` (default) writes
  directly, byte-identical.
- **`src/cli.py`** -- `resolve_settings` split into `settings_from_args` (the
  body) + `resolve_settings` (parse then delegate), so entry points parse once
  and also read storage flags off the same namespace. Storage flags deliberately
  excluded from `cli_overrides` so they never leak into the deterministic
  `Settings`.

### `tools/migrate_storage.py` (new, `87bc123`)

Thin CLI over `plan_migration`/`apply_migration`:
`--external-root` (or env, required), `--kind` (`output` default, repeatable;
`datasets` opt-in), `--dry-run`, `--no-symlink`. Verifies drive is mounted
before moving anything; non-zero exit + `StorageError` message on failure.

### Follow-up fixes

- `25af46e` / `34a5bea` -- `.gitignore` gained slash-less `output` and
  `datasets` entries so the post-migration symlinks are not shown as untracked.
- `3d90f4e` -- **SMB-safe cross-device mover** (the real-data bug; see below).
- `42bd428` -- docs recording the real NAS migration + end-to-end verification.
- `38ea2ce` -- large SVG write verification to survive silent SMB/NAS corruption.

### Tests (+26)

- `tests/test_storage.py` (14 new): 8 resolution + 6 migration.
- `tests/test_build.py` (+4): defaults local when NAS unmounted; cache defaults
  to NAS when mounted; `--external-root` expands all three; explicit
  `--output-dir` overrides external root.
- `tests/test_serve.py` (+3): `_serve_roots` default, external root, env var.
- `tests/test_migrate_storage.py` (4 new, offline): missing-root error, dry-run,
  real move + symlink, unmounted guard.
- `tests/test_export_pipeline.py` (+1): staging renders locally then moves;
  `export_paths` reports the final output path.

Suite: **488 passing** (was 462; +26).

## Real-data findings

### The bug the real run surfaced: SMB `chflags` (`3d90f4e`)

`shutil.move`'s cross-device fallback calls `copy2`, which calls
`os.chflags` to preserve file flags. The Synology SMB share rejects `chflags`
with `OSError(EINVAL)`, aborting the move mid-tree. This is invisible to offline
tests because `tmp_path` is on the same device (no cross-device fallback) and
the injectable `mover` in the unmounted-guard test is a fake.

**Fix:** replaced the `shutil.move` default mover with a custom `move_file`
that does `copyfile` + best-effort `copymode` (no flags). The `mover` parameter
on `apply_migration` made this a one-line swap.

### Second gotcha: `.DS_Store` blocking the auto-symlink

A stray `.DS_Store` left in a source dir after all "real" files migrated means
the source is not fully drained, so `apply_migration` skips the symlink step
(`symlinked=None`). Not a code bug -- the behavior is correct and intentional
(only symlink when empty) -- but it required a manual `rm .DS_Store` and re-run
to complete the symlink. Documented in HANDOFF.md.

### End-to-end verification

Both `output/` (352 files, 2.3 GiB) and `datasets/` (6796 files, 18.8 GiB)
migrated onto the Synology NAS at `/Volumes/home/data/hydro-art/{output,datasets}`;
local paths are now directory symlinks. Verified via a full `build.py --region
Oregon`: read all GDBs through the `datasets` symlink, download+extract stages
short-circuited (**zero downloads/network**, first stage to log was `validate`),
rendered 1.77M segments, and wrote `output/oregon.svg` (1,062,115,316 bytes)
back through the `output` symlink onto the NAS -- exit 0.

## Invariants held

- **Offline suite:** 488 passing, fully offline (no GDAL, no network).
- **2D default output byte-identical:** yes. Storage location is not part of
  `Settings` and never affects rendered bytes. A no-flag, no-env build resolves
  to today's `cache`/`datasets`/`output` paths unchanged.
- **`PIPELINE_STAGES` untouched:** yes. The only `pipeline.py` change is the
  optional `staging_dir` on export, with `None` (default) byte-identical.
- **Rights gate:** N/A -- no new data source. All renders use USGS
  public-domain data.

## Graded against pre-analysis

The spec folder carries `planning/requirements.md` (functional/non-functional
requirements) but no `planning/pre-analysis.md` with a pre-registered
watch-list, so there is no formal prediction to grade against. The requirements
document did anticipate the core risks correctly:

- **"Never `mkdir` under an unmounted `/Volumes` mount point"** -- held. The
  `drive_available` probe + fallback-to-local behavior was implemented exactly
  as specified, exercised in 3 resolution tests + 1 migration guard test.
- **"Idempotent/resumable migration"** -- held. The plan's `skipped` set +
  partial re-run test verified this.
- **"Storage location is not part of `Settings`"** -- held. The `cli.py` split
  (`settings_from_args` vs. storage flags) enforces the boundary.

The requirements document did **not** predict the SMB `chflags` failure, which
is the gap a pre-analysis would have flagged ("does `shutil.move` work over
SMB?" as a watch-list item).

## Carry-forwards

- **`config.yaml` `storage:` block** -- deferred. The env var + CLI flags cover
  the current need; a config key can follow without touching the resolver
  contract.
- **Datasets migration is opt-in only.** The tool supports `--kind datasets` but
  the default is `output` only. The 18.8 GiB datasets migration was done
  manually via the tool; there is no automatic "migrate everything on first
  run."
- **Large SVG write integrity over SMB** -- the `38ea2ce` commit added
  verification after the Oregon 1 GB SVG write, but the silent-corruption
  concern remains a monitoring item for statewide renders. No automated
  checksum-after-write gate exists in the pipeline.

## Lessons

- **The injectable `mover` parameter saved the epoch.** The spec called for an
  injectable `mover` on `apply_migration` primarily for testing (injecting a
  fake to assert the unmounted guard fires before any move). It also made the
  SMB `chflags` fix a one-line swap of `shutil.move` -> `move_file` without
  changing the module's API or re-testing the resolution half. Design-for-test
  seams double as production-fix seams.
- **SMB/NAS shares are not POSIX.** `shutil.move`, `os.chflags`, and `.DS_Store`
  all interact poorly with SMB. Assume any filesystem operation beyond
  open/read/write/close may fail on a network share; test the first real
  migration against the actual target, not `tmp_path`.
- **Dry-run first, always.** The `--dry-run` mode (352 files, 2.3 GiB reported)
  was run before every real migration and caught nothing -- but it built
  confidence that the plan was correct and the file enumeration was deterministic.
  The cost of adding dry-run is near zero; the cost of not having it when a
  migration goes wrong is unbounded.
