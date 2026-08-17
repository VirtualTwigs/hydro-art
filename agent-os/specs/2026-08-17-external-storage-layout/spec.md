# Spec — External-storage layout & output migration (roadmap #29)

## Summary

Add `src/storage.py`: a pure, deterministic, offline module that (A) resolves the
cache / datasets / output roots to a configurable external-drive location with a
mount-aware local fallback, and (B) plans and executes a one-time migration of an
existing local directory (default `output/`) onto the drive, leaving a directory
symlink behind so existing paths keep resolving. Wire the resolver into `build.py`
and `serve.py`, and add a thin `tools/migrate_storage.py` CLI over the executor.
Storage location is infrastructure resolved *before* the `Pipeline` is built — it
is not part of `Settings`, not in `PIPELINE_STAGES`, and never affects rendered
bytes.

## Public API (`src/storage.py`)

```
DEFAULT_LOCAL_ROOTS: dict[str, str] = {
    "cache": "cache", "datasets": "datasets", "output": "output",
}
EXTERNAL_ROOT_ENV: str = "HYDRO_ART_EXTERNAL_ROOT"

StorageError(Exception)                 # migration/execution failures

@dataclass(frozen=True)
class StorageRoots:
    cache: Path
    datasets: Path
    output: Path
    external_root: Path | None          # the configured drive root, or None
    using_external: bool                 # True iff any root resolved onto it
    staging: Path | None = None          # local working copy for output, if any

def drive_available(root: Path, *, probe: Callable[[Path], bool] = Path.exists) -> bool
    # A drive is usable when its root exists or its parent (mount point) exists.

def resolve_storage(
    *,
    external_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,      # defaults to os.environ
    local_root: str | Path = ".",
    overrides: Mapping[str, str | Path] | None = None,   # per-kind explicit dirs
    staging: str | Path | None = None,
    available: Callable[[Path], bool] | None = None,      # injectable probe
) -> StorageRoots

@dataclass(frozen=True)
class MigrationItem:
    source: Path
    destination: Path
    size: int

@dataclass(frozen=True)
class MigrationPlan:
    source_dir: Path
    dest_dir: Path
    items: tuple[MigrationItem, ...]     # files to move, sorted by source
    skipped: tuple[Path, ...]            # already present at dest (same size)
    total_bytes: int                     # sum of item sizes
    @property
    def is_empty(self) -> bool

@dataclass(frozen=True)
class MigrationResult:
    moved: tuple[Path, ...]              # destinations written
    bytes_moved: int
    symlinked: Path | None               # source_dir, now a symlink -> dest_dir

def plan_migration(source_dir, dest_dir) -> MigrationPlan
def apply_migration(
    plan, *, symlink=True, mover=shutil.move, require_mounted=True,
) -> MigrationResult
```

## Behavior

### A. Root resolution (`resolve_storage`)

- The external root comes from `external_root` if given, else `env[
  EXTERNAL_ROOT_ENV]`, else `None`.
- For each kind in `cache` / `datasets` / `output`, precedence is:
  1. an explicit `overrides[kind]` (a CLI `--cache-dir` / `--datasets-dir` /
     `--output-dir`) — always wins, used verbatim;
  2. `external_root / kind` — **only when `available(external_root)` is true**;
  3. `local_root / DEFAULT_LOCAL_ROOTS[kind]` — the default (today's behavior).
- `available` defaults to `drive_available` (root or its parent exists). When an
  external root is configured but unavailable, every non-overridden kind falls
  back to its local default and `using_external` is `False` (the caller logs a
  "drive not mounted — using local paths" notice). Resolution **never raises and
  never creates directories under an unmounted mount point**.
- `using_external` is `True` iff at least one root resolved to a path under
  `external_root`.
- `staging` (optional): a local working directory for output. Stored on
  `StorageRoots.staging`; when set, callers render into it and move the finished
  file to `output`. `None` → direct write (default, byte-identical).
- With no `external_root`, no `overrides`, and `local_root="."`, the result is
  exactly `Path("cache")`, `Path("datasets")`, `Path("output")`.

### B. Migration (`plan_migration` / `apply_migration`)

- `plan_migration(source_dir, dest_dir)` walks `source_dir` recursively (sorted,
  deterministic), maps each file to `dest_dir / relpath`, and:
  - a file already at the destination with the **same size** → `skipped`
    (idempotent re-run);
  - otherwise → a `MigrationItem` with the source size.
  `total_bytes` sums item sizes. A missing `source_dir` yields an empty plan
  (nothing to migrate), not an error. Pure: no filesystem writes.
- `apply_migration(plan, …)`:
  - if `require_mounted` and the destination drive is not available →
    `StorageError` before moving anything;
  - create each destination's parent, `mover(source, destination)` (default
    `shutil.move`) for every item;
  - when `symlink` and the source directory is now empty of real files, replace
    `plan.source_dir` with a symlink to `plan.dest_dir` (so `output/oregon.svg`
    resolves through the link). If `source_dir` still holds un-migrated files, the
    symlink step is skipped and reported (`symlinked=None`).
  - returns the destinations moved, bytes moved, and the symlink target.
- Re-running after a partial move: the plan skips already-present files and the
  apply completes the rest, then symlinks — so the operation is resumable.

## Entry-point wiring

- **`build.py`**: add `--external-root` (default `None` → env
  `HYDRO_ART_EXTERNAL_ROOT`), `--datasets-dir`, `--output-dir`, and keep the
  existing `--cache-dir` semantics; call `resolve_storage(...)` and pass
  `roots.cache` / `roots.datasets` / `roots.output` to `Pipeline(...)`. Replace
  the hardcoded `NAS_CACHE_DIR` default with the resolver (external root defaults
  to the NAS path when the env/flag is unset **and** the NAS is mounted, else
  local — preserving today's behavior). Log the resolved roots and whether the
  external drive was used.
- **`serve.py`**: generalize `_resolve_cache_dir` to delegate to
  `resolve_storage` so a served run honors the same external root for cache /
  datasets / output; keep the "NAS when mounted else local" default and the
  `--cache-dir` override contract intact.
- Neither entry point changes `Settings`; the `Pipeline` still receives three
  plain `Path`s.

## CLI (`tools/migrate_storage.py`)

A thin executor over `plan_migration` / `apply_migration`:

```
python tools/migrate_storage.py --external-root /Volumes/Pro/hydro-art [--kind output] [--dry-run]
```

- `--external-root` (or `HYDRO_ART_EXTERNAL_ROOT`) is required; `--kind`
  (`output` default, repeatable, also `datasets`) selects which local tree(s) to
  move; `--dry-run` prints the plan (file count, total bytes, skipped) without
  moving; `--no-symlink` disables the trailing symlink.
- Verifies the drive is mounted (`drive_available`) and refuses with a non-zero
  exit + `StorageError` message otherwise. Prints per-kind results. Reads/moves
  real files on real drives, so — like the other `tools/` — it is **not** in the
  offline suite; its `main()` is smoke-tested against `tmp_path`.

## Determinism & guardrails

- `src/storage.py` imports only stdlib (`pathlib`, `dataclasses`, `os`,
  `shutil`, `typing`). No numpy / GDAL / shapely. Offline-suite safe.
- Frozen dataclasses; `from __future__ import annotations`; docstrings; 88-col.
- Not in `PIPELINE_STAGES`. `src/` does not import `tools/` or `web/`.
- Resolution is a pure function of its arguments (env + probe injected), so tests
  never touch real mounts; migration is tested against `tmp_path` with a real
  `shutil.move` and a fake mover for the unmounted-guard path.

## Tests (`tests/test_storage.py`)

TG1 (resolution): no external root → today's `cache`/`datasets`/`output`;
external root + `available=lambda _: True` → the three `<root>/<kind>` subdirs and
`using_external` True; external root + `available=lambda _: False` → local
fallback and `using_external` False; a per-kind override wins over both; env var
supplies the root when the arg is omitted; the arg beats the env var; `staging`
surfaces on `StorageRoots`.

TG2 (migration): `plan_migration` over a populated `tmp_path` tree enumerates all
files sorted with summed `total_bytes`; a file already at the destination with the
same size is `skipped`; `apply_migration` moves every file, leaves a working
directory symlink pointing at the destination, and re-resolves a known file
through the link; an unmounted destination (`require_mounted`, failing probe)
raises `StorageError` before any move; a partial tree (some files pre-present)
re-runs to completion (resumable); missing `source_dir` → empty plan, no error.

## Not in scope (this slice)

A `config.yaml` `storage:` block; migrating the download cache/datasets by
default (datasets is opt-in only); portable-bundle zipping (that is #21's
packaging planner); any change to rendered bytes, `Settings`, or `PIPELINE_STAGES`.
