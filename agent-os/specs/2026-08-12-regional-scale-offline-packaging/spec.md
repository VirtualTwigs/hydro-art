# Spec — Portable cache manifests (roadmap #21, offline-packaging slice)

## Summary

Add `src/manifest.py`: a pure, deterministic, offline facility that exports an
auditable manifest of a `Cache`'s dataset archives, verifies a cache directory
against a manifest, and diffs two manifests for reconciliation. Built on the
existing `Cache` (`record`/`metadata`/`path_for`), `FileDescriptor`, and
`resolve_required_files`. No changes to other modules; not in `PIPELINE_STAGES`.

## Public API (`src/manifest.py`)

```
MANIFEST_VERSION: str = "1"

ManifestError(AcquisitionError)          # malformed manifest data / strict misses

@dataclass(frozen=True)
class ManifestEntry:
    key: str                # "<dataset_id>/<huc4>/<filename>" (FileDescriptor.key)
    dataset_id: str
    huc4: str
    filename: str
    url: str
    checksum: str           # sha256 hex, from Cache metadata
    size: int               # bytes, from Cache metadata
    relative_path: str      # POSIX path under the cache root (portable)
    source_release: str | None = None

@dataclass(frozen=True)
class CacheManifest:
    entries: tuple[ManifestEntry, ...]   # always sorted by key
    version: str = MANIFEST_VERSION

@dataclass(frozen=True)
class ManifestVerification:
    ok: tuple[str, ...]          # keys whose file exists + checksum + size match
    missing: tuple[str, ...]     # keys whose file is absent
    mismatched: tuple[str, ...]  # keys whose checksum or size differs
    @property
    def is_complete(self) -> bool  # not missing and not mismatched

@dataclass(frozen=True)
class ManifestDiff:
    added: tuple[str, ...]       # in new, not old
    removed: tuple[str, ...]     # in old, not new
    changed: tuple[str, ...]     # in both, different checksum
    unchanged: tuple[str, ...]   # in both, same checksum
    @property
    def is_synced(self) -> bool  # not added and not removed and not changed

build_manifest(cache, descriptors, *, strict=False) -> CacheManifest
manifest_for_settings(cache, settings, *, strict=False) -> CacheManifest
manifest_to_dict(m) -> dict
manifest_from_dict(data) -> CacheManifest
write_manifest(m, path) -> None
read_manifest(path) -> CacheManifest
verify_manifest(m, cache_root) -> ManifestVerification
diff_manifests(old, new) -> ManifestDiff
```

## Behavior

- **build_manifest**: for each descriptor, read `cache.metadata(descriptor)`; if
  present, emit a `ManifestEntry` with the recorded `url`/`checksum`/`size`/
  `source_release` and the descriptor's cache-relative path
  (`path_for(descriptor).relative_to(cache.root)`, POSIX). Descriptors with no
  recorded metadata are skipped, unless `strict=True`, which raises
  `ManifestError`. Entries are sorted by `key`.
- **manifest_for_settings**: `build_manifest(cache, resolve_required_files(settings), …)`
  — the region→manifest bridge (multi-state coverage in one manifest).
- **Serialization** (`manifest_to_dict` / `write_manifest`): a JSON object
  `{"version", "entries": [...]}` with entries in key order; `write_manifest`
  emits `json.dumps(..., indent=2, sort_keys=True)` + trailing newline, so
  identical cache state → identical bytes. Wall-clock `downloaded_at` is
  **excluded** from the canonical manifest (kept determinism over provenance;
  timestamps still live in the `Cache` index).
- **manifest_from_dict / read_manifest**: reconstruct + re-sort by key; missing
  required entry fields or a non-list `entries` raise `ManifestError`. Unknown
  `version` is preserved (forward-compatible read, no hard fail).
- **verify_manifest**: resolve each entry's file at `cache_root / relative_path`;
  absent → `missing`; else recompute SHA-256 and compare size → `mismatched` or
  `ok`. Never mutates the cache.
- **diff_manifests(old, new)**: set arithmetic over keys; `changed` = shared key
  with differing checksum; the rest `unchanged`.

## Determinism & guardrails

- Sorted entries + stable JSON + no timestamps ⇒ reproducible manifest bytes.
- Relative paths ⇒ portable across machines / mount points.
- `src/manifest.py` imports only stdlib (`hashlib`, `json`, `pathlib`,
  `dataclasses`, `typing`) + `src.datasets` (`FileDescriptor`,
  `resolve_required_files`, `AcquisitionError`) + `src.config` (`Settings` type)
  + `src.cache` (`Cache` type, duck-typed). No numpy / GDAL — offline suite safe.
- Frozen dataclasses; `from __future__ import annotations`; docstrings; 88-col.

## Tests (`tests/test_manifest.py`)

TG1 (model/build/serialize): build over a real `Cache` in `tmp_path` (write file
→ `cache.record` → `build_manifest`); skip un-recorded descriptor; `strict`
raises; entries sorted by key; `to_dict`/`from_dict` round-trip; `write`/`read`
round-trip; deterministic bytes (two writes identical; insertion order
irrelevant); `manifest_for_settings` over an OR+WA `Settings` yields the resolved
descriptors; `from_dict` on malformed input raises.

TG2 (verify/diff): verify all-ok; a deleted file → `missing`; a corrupted file →
`mismatched` (both truncated-size and same-size-different-bytes); `is_complete`;
diff added/removed/changed/unchanged + `is_synced`.

## Phase 2 — Tile-budget controls (added slice)

A second offline slice of #21: cap how many 3DEP DEM COGs one acquisition may
fetch, failing fast before any download.

- `ElevationSettings.tile_budget: int` (`0` = unlimited; boundary-validated in
  `_coerce_elevation`, `bool`/non-int/negative rejected).
- `dem.count_tiles(boundary, tier, discoverer=None) -> int` — pure offline
  preflight.
- `dem.acquire_dem(..., max_tiles: int = 0)` — raises `ElevationError` after
  discovery and before the download loop when the tile count exceeds the budget.

## Not in scope

Region expansion (needs real WBD) and a real-NAS packaging CLI remain deferred on
roadmap #21. Resumable jobs turned out to be already implemented
(`Downloader` `.part`+Range resume + `acquire`/`acquire_dem` cache-skip), so no
new work was needed there. Wiring `tile_budget` into a live DEM entry point is a
non-offline follow-on (the DEM subsystem is not in `PIPELINE_STAGES`).

---

# Spec — Package preflight planner (roadmap #21, offline-packaging slice)

## Summary

Add `src/packaging.py`: a pure, deterministic, offline planner that answers "is
this cache ready to package and ship to an offline machine?" for a given
`Settings`. It composes the already-shipped primitives — `resolve_required_files`
(what a build needs), `build_manifest`/`verify_manifest` (what the cache holds,
intact), and the `elevation.tile_budget` (DEM preflight) — into one `PackagePlan`.
Plus a thin `tools/package_cache.py` CLI. Not in `PIPELINE_STAGES`.

## Public API (`src/packaging.py`)

```
PackagingError(AcquisitionError)

@dataclass(frozen=True)
class PackagePlan:
    required: tuple[str, ...]      # all keys the build needs (resolve order)
    present: tuple[str, ...]       # required keys with a valid cached file
    missing: tuple[str, ...]       # required keys absent / unrecorded / file gone
    corrupt: tuple[str, ...]       # required keys cached but checksum/size mismatch
    total_bytes: int               # summed size of cached required entries
    tile_count: int | None         # injected DEM tile preflight (None = skipped)
    tile_budget: int               # settings.elevation.tile_budget (0 = unlimited)
    is_complete    -> bool         # no missing and no corrupt
    within_tile_budget -> bool     # tile_count None or budget 0 or count <= budget
    is_ready       -> bool         # is_complete and within_tile_budget

plan_package(cache, settings, *, cache_root=None, tile_count=None) -> PackagePlan
format_plan(plan) -> str
```

## Behavior

- `required` = `[d.key for d in resolve_required_files(settings)]` (deterministic
  order). Coverage is computed by building a manifest of the cached subset and
  verifying it against `cache_root` (defaults to `cache.root`): a required key is
  `present` if its file verifies, `corrupt` if cached-but-mismatched, else
  `missing` (never recorded, or recorded but the file is gone). The three sets are
  disjoint and partition `required`.
- `total_bytes` sums the sizes of cached required entries (the package footprint).
- **Tile preflight is injected, not computed** — `plan_package` takes an optional
  `tile_count` (the CLI supplies it from `dem.count_tiles` over a real boundary),
  so `src/packaging.py` stays free of numpy/GDAL/shapely and fully offline-testable.
  `tile_budget` is read from `settings.elevation.tile_budget`.
- `is_ready` gates packaging: every required file present + intact and the DEM tile
  count within budget.

## CLI (`tools/package_cache.py`)

A thin wrapper: builds `Settings` for a region + points a `Cache` at a real cache
dir, best-effort computes `count_tiles` when the GIS stack + region boundary are
available (else skips the tile preflight), prints `format_plan`, and exits non-zero
when the plan is not ready. Reads a real (NAS) cache, imports heavy libs → not in
the offline suite, consistent with the other `tools/`.

## Guardrails

- `src/packaging.py` imports only stdlib + `src.manifest` / `src.datasets` /
  `src.config` / `src.cache` — no numpy / geopandas / GDAL / shapely. Pure,
  deterministic, offline; not in `PIPELINE_STAGES`; `PackagingError` subclasses
  `AcquisitionError` (packaging is an acquisition-domain utility).
- `from __future__ import annotations`; docstrings; 88-col.

## Tests (`tests/test_packaging.py`)

TG-P1: full-coverage cache → all present, complete, `total_bytes` summed; a missing
required file → `missing`; a post-record on-disk mutation → `corrupt`; determinism.

TG-P2: injected `tile_count` within/over budget, unlimited budget, and `None`;
`is_ready` composition; `format_plan` summary contents.

## Not in scope (this slice)

Computing the DEM tile count inside `src/` (kept injected/offline); region
expansion beyond OR/WA/CA (needs real WBD); actually copying/zipping a cache into a
shippable bundle (the planner reports readiness; bundling is a `tools/` follow-on).
