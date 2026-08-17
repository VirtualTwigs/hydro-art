# Requirements — External-storage layout & output migration (roadmap #29)

## Roadmap text

> 29. External-storage layout & output migration — Resolve the cache, datasets,
> and output roots to a configurable external-drive location (env var + CLI,
> mount-aware with a local fallback and an optional local working copy during
> generation), and provide a one-time migration that moves existing local output
> onto the drive and leaves the local path referencing it (directory symlink).
> `M`

## Motivation

Local free space is limited (~35 GB). The two bulk consumers of disk in this
project are:

1. **"Database" files** — the extracted NHDPlus HR / WBD `.gdb` datasets (under
   `datasets/`) and the downloaded HUC4 GDB-zip archives (under the cache root)
   that every image build reads. These are hundreds of MB to GB each.
2. **Rendered output** — the SVG/PNG/PDF images written under `output/`.
   Statewide layered SVGs alone run to several MB, and PNG/PDF exports are larger.

Today only the *downloaded archives* live off-machine: `build.py` hardcodes
`NAS_CACHE_DIR = /Volumes/home/data/incoming` (roadmap #21), and `serve.py`
resolves the cache dir with a mount-aware NAS/local fallback
(`_resolve_cache_dir`). The `datasets/` and `output/` roots always land on local
disk (`Pipeline` defaults `datasets_dir="datasets"`, `output_dir="output"`; no
CLI flag or config key redirects them). This item generalizes that off-machine
storage to all three roots and adds a migration for output that already exists
locally.

The user's stored preference (memory `feedback_large_file_storage`): all large
files belong on the external NAS Pro drive, not local disk; when moving existing
large files, leave a symlink at the expected local path so tools still resolve
them; the drive is often unmounted at session start, so never silently persist
large files locally and never `mkdir` under an unmounted `/Volumes` mount point.

## Scope this pass

Two capabilities, one roadmap item:

- **A. Reference external storage** — a single configurable external-drive root
  expands to `cache/`, `datasets/`, and `output/` subdirs on the drive. The
  pipeline reads datasets and the download cache from there and writes images
  there. Mount-aware: when the drive is unmounted, fall back to the current local
  paths so a build never crashes. Optional local working copy (staging) during
  generation for callers who want to write the image locally first and move the
  finished file to the drive.
- **B. Migrate existing output** — a repeatable, dry-runnable migration that
  moves an existing local directory (default `output/`, optionally `datasets/`)
  onto the external drive and replaces the local directory with a symlink to its
  new home, so existing references (`output/oregon.svg`, tooling, docs) keep
  resolving. Idempotent: files already migrated (present + same size at the
  destination) are skipped.

## Functional requirements

- **Configurable external root** — via `--external-root` (build.py/serve.py) and
  the `HYDRO_ART_EXTERNAL_ROOT` environment variable; per-kind explicit overrides
  (`--cache-dir` / `--datasets-dir` / `--output-dir`) win over the derived
  external subdir. Precedence per root: explicit override > external-root subdir
  (when available) > local default.
- **Mount-aware, non-crashing** — an external root is used only when its drive is
  mounted (the root path or its parent exists, mirroring
  `serve._resolve_cache_dir`). When configured-but-unmounted, resolution falls
  back to the local default for the affected roots and reports that it did so; it
  never `mkdir`s under an unmounted mount point.
- **Deterministic resolution** — the same inputs (env, flags, availability probe)
  always yield the same `StorageRoots`; resolution is a pure function with an
  injectable availability probe so it is fully offline-testable.
- **Byte-identical default** — with no external root configured and no override,
  resolution yields exactly today's `cache` / `datasets` / `output` paths, so
  existing builds are unchanged. Storage location is *not* part of `Settings` and
  never affects rendered bytes → determinism and the offline test posture hold.
- **Migration is safe and reversible** — plan first (enumerate files, total
  bytes, skip already-migrated), support a dry run, verify the destination drive
  is mounted before moving, move the tree, then replace the source directory with
  a symlink to the destination. Idempotent; re-running after a partial move
  completes it.
- **Keep-local option** — an optional local staging directory lets a build render
  to local disk and move only the finished artifact to the external output root
  (guards against slow/interrupted writes landing half-written files on the
  drive). Default off → export writes directly to the resolved output root,
  byte-identical to today.

## Non-functional / guardrails

- Pure, deterministic, **offline** engine: `src/storage.py` imports only stdlib
  (`pathlib`, `dataclasses`, `os`, `shutil`, `typing`) — no numpy / geopandas /
  GDAL — so `tests/test_storage.py` runs in the offline suite. Migration
  execution uses real filesystem ops but is tested against `tmp_path` (no network,
  no GDAL).
- No new global state; frozen dataclasses for the value objects (`StorageRoots`,
  `MigrationPlan`, `MigrationItem`, `MigrationResult`). `from __future__ import
  annotations`; docstrings on public functions; 88-col; `ruff`-clean.
- Not wired into `PIPELINE_STAGES` — storage resolution is infrastructure the
  entry points (`build.py`, `serve.py`) perform *before* constructing the
  `Pipeline`; the pipeline still just receives three `Path`s. `src/` never imports
  `tools/` or `web/`.
- Error taxonomy: a dedicated `StorageError(Exception)` for migration/execution
  failures (unmounted destination, source missing). Path *resolution* does not
  raise — it falls back — so `build.py`/`serve.py` need no new exit code.

## Out of scope (deferred)

- A `config.yaml` `storage:` block (env + CLI cover the need this pass; a config
  key can follow without touching the resolver contract).
- Migrating the download **cache** archives (already NAS-staged via #21) or the
  datasets tree by default — the migration tool supports `datasets/` opt-in, but
  the default target is `output/`, the gap #21 left open.
- Zipping/copying a cache into a portable bundle (that is #21's packaging
  planner; this item *moves in place* onto an attached drive).
- Any change to the rendered artifact, `Settings`, or `PIPELINE_STAGES`.
