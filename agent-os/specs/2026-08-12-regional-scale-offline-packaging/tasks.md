# Tasks — Portable cache manifests (roadmap #21, offline-packaging slice)

## TG1 — Manifest model, build, (de)serialization (deterministic)

- [x] Write tests first (`tests/test_manifest.py`): `build_manifest` over a real
      `Cache` in `tmp_path` (write file → `cache.record` → build); un-recorded
      descriptor skipped; `strict=True` raises `ManifestError`; entries sorted by
      key; `manifest_to_dict`/`manifest_from_dict` round-trip; `write_manifest`/
      `read_manifest` round-trip; deterministic bytes (two writes byte-identical;
      insertion order irrelevant); `manifest_for_settings` over OR+WA `Settings`;
      malformed `from_dict` → `ManifestError`.
- [x] `src/manifest.py`: `ManifestError`, `ManifestEntry`, `CacheManifest`,
      `MANIFEST_VERSION`, `build_manifest`, `manifest_for_settings`,
      `manifest_to_dict`, `manifest_from_dict`, `write_manifest`, `read_manifest`
      (stdlib + `src.datasets`/`src.config`/`src.cache` only).
- [x] Run ONLY the new tests; green.

## TG2 — verify + diff

- [x] Write tests first: `verify_manifest` all-ok / missing (deleted file) /
      mismatched (truncated + same-size-different-bytes) / `is_complete`;
      `diff_manifests` added / removed / changed / unchanged / `is_synced`.
- [x] `src/manifest.py`: `ManifestVerification` + `verify_manifest`,
      `ManifestDiff` + `diff_manifests`.
- [x] Run ONLY the new tests; green.

## TG3 — Verify + docs

- [x] Confirm `manifest` imports offline (no numpy/GDAL pulled in); `ruff` if
      available.
- [x] Run the full Python suite (regression check).
- [x] Write `implementation/report.md`; tick this `tasks.md`.
- [x] Add a roadmap #21 progress note (offline-packaging slice shipped; region
      expansion / tile-budget / resume still open); update `HANDOFF.md` +
      `CLAUDE.md` module map. Report; STOP (commit is a separate explicit step).

## Phase 2 — Tile-budget controls (second #21 slice)

## TG-B1 — `tile_budget` config field

- [x] Write tests first (`tests/test_elevation_config.py`): `tile_budget`
      defaults to `0` (unlimited); positive int accepted; negative raises
      `ConfigError`; non-int raises.
- [x] `src/config.py`: add `tile_budget` to `DEFAULTS["elevation"]` (0) +
      `ElevationSettings` + `_coerce_elevation` validation (non-negative int;
      reject bool/non-int).
- [x] Run ONLY the new tests; green.

## TG-B2 — `count_tiles` + `acquire_dem` budget guard

- [x] Write tests first (`tests/test_dem.py`): `count_tiles` matches discovery
      count (offline); `acquire_dem(max_tiles>=count)` proceeds;
      `acquire_dem(max_tiles<count)` raises `ElevationError` **before any fetch**
      (fake downloader never called); `max_tiles=0` unlimited.
- [x] `src/dem.py`: pure `count_tiles(boundary, tier, discoverer=None)`; add
      `max_tiles: int = 0` to `acquire_dem`, raising `ElevationError` after
      discovery and before the download loop when the count exceeds the budget.
- [x] Run ONLY the new tests; green.

## TG-B3 — Verify + docs

- [x] Full Python suite (regression check); note resumable-jobs already built
      (`Downloader` `.part`+Range resume + cache-skip).
- [x] Extend `implementation/report.md`, this `tasks.md`, `spec.md`; roadmap #21
      note; `HANDOFF.md` + `CLAUDE.md`. Report; STOP.

---

# Tasks — Package preflight planner (roadmap #21, offline-packaging slice)

## TG-P1 — Cache-coverage planning

- [x] Write tests first (`tests/test_packaging.py`): `plan_package(cache, settings)`
      over a cache holding every required file reports `required` == all resolved
      keys, `present` == all, empty `missing`/`corrupt`, `is_complete` True, and
      `total_bytes` == the summed sizes; a required file absent from the cache lands
      in `missing` (not present); a cached file whose bytes changed on disk after
      `record` lands in `corrupt`; two identical calls are equal (determinism).
- [x] `src/packaging.py`: `PackagingError(AcquisitionError)`, frozen `PackagePlan`,
      and `plan_package(cache, settings, *, cache_root=None, tile_count=None)` —
      composes `resolve_required_files` + `build_manifest`/`verify_manifest`; pure,
      offline (stdlib + `src.manifest`/`datasets`/`config`/`cache`; no
      numpy/GDAL/shapely); not in `PIPELINE_STAGES`.
- [x] Run ONLY the new tests; green.

## TG-P2 — Tile-budget preflight + readiness + formatting

- [x] Write tests first: an injected `tile_count` within `settings.elevation
      .tile_budget` → `within_tile_budget` True; over budget → False; `tile_budget`
      0 (unlimited) → True even for a large count; `tile_count=None` → True;
      `is_ready` = complete AND within-budget; `format_plan(plan)` returns a
      human-readable summary mentioning readiness + the missing/corrupt counts.
- [x] `src/packaging.py`: `within_tile_budget`/`is_ready` properties + `format_plan`.
- [x] Run ONLY the new tests; green.

## TG-P3 — CLI + verify + docs

- [x] Add `tools/package_cache.py`: a thin CLI over `plan_package` — build settings
      for a region/cache dir, take the DEM tile count via an explicit `--tile-count`
      (from `src.dem.count_tiles`; omitted → preflight skipped, staying honest rather
      than reimplementing WBD boundary loading), print `format_plan`, exit non-zero
      when not ready. Not in the offline suite (reads a real cache).
- [x] Confirm the full Python suite passes (regression check): **430 passed** (+7).
- [x] Extend `spec.md`/`implementation/report.md`; tick this `tasks.md`.
- [x] Update the roadmap #21 note, `HANDOFF.md`, and the `CLAUDE.md` module map.
      Report; STOP.
