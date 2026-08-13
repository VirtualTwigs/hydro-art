# Implementation report — Portable cache manifests (roadmap #21 slice)

## What shipped

`src/manifest.py` — a pure, deterministic, offline facility that turns a
`Cache`'s recorded dataset provenance into a **portable, verifiable manifest**.
This is the "offline packaging" slice of the `XL` roadmap #21; region expansion,
tile-budget controls, and resumable jobs are explicitly deferred (they need live
downloads / NAS / real WBD that cannot run in the offline, GDAL-free posture).
Scope was confirmed with the user on 2026-08-12.

## Public API (`src/manifest.py`)

- `ManifestError(AcquisitionError)` — malformed manifest data / strict build miss.
- `ManifestEntry` (frozen) — `key`, `dataset_id`, `huc4`, `filename`, `url`,
  `checksum`, `size`, `relative_path` (POSIX, under the cache root), optional
  `source_release`.
- `CacheManifest` (frozen) — `entries` (always sorted by key) + `version`
  (`MANIFEST_VERSION = "1"`).
- `build_manifest(cache, descriptors, *, strict=False)` — reads
  `cache.metadata(descriptor)` for each descriptor; emits an entry with the
  recorded url/checksum/size/source_release and the descriptor's cache-relative
  path. Un-recorded descriptors are skipped, or raise under `strict`.
- `manifest_for_settings(cache, settings, *, strict=False)` — the region→manifest
  bridge: `build_manifest(cache, resolve_required_files(settings), …)`, so
  multi-state coverage (OR/WA/CA) round-trips through one manifest.
- `manifest_to_dict` / `manifest_from_dict` — canonical dict form;
  `manifest_from_dict` validates structure and raises `ManifestError` on a
  non-list `entries` or a missing required field.
- `write_manifest` / `read_manifest` — deterministic JSON
  (`indent=2, sort_keys=True` + trailing newline); `read_manifest` maps
  JSON/OS errors to `ManifestError`.
- `ManifestVerification` (+ `verify_manifest(manifest, cache_root)`) —
  recomputes SHA-256 + size against each entry; reports `ok` / `missing` /
  `mismatched` with an `is_complete` verdict. Never mutates the cache.
- `ManifestDiff` (+ `diff_manifests(old, new)`) — key-wise set arithmetic;
  `changed` = shared key with a different checksum; `is_synced` verdict.

## Design / guardrails honored

- **Deterministic**: entries sorted by key, stable JSON, and wall-clock
  `downloaded_at` deliberately excluded from the canonical manifest ⇒ identical
  cache state produces byte-identical output (proven order-independent in tests).
  Timestamps still live in the `Cache` index for provenance.
- **Portable**: entry paths are relative to the cache root, so a manifest stays
  valid after the cache is copied to another machine / mount.
- **Offline & GDAL-free**: importing `src.manifest` pulls in **no** numpy /
  geopandas / shapely / pyogrio / networkx / `src.raster` / `src.terrain` /
  `src.hydro_z` (verified: "heavy modules pulled in: none"). It imports only
  stdlib + `src.datasets` / `src.config` / `src.cache`.
- Reuses `Cache` (`record`/`metadata`/`path_for`), `FileDescriptor`, and
  `resolve_required_files` unchanged; no edits to other modules. Not wired into
  `PIPELINE_STAGES`.

## Tests (`tests/test_manifest.py`, 13 tests)

Use a real stdlib `Cache` in `tmp_path` + hand-written archive bytes — no
network / GDAL. Coverage: `build_manifest` from recorded cache / skip un-recorded
/ `strict` raises / sorted-by-key; `to_dict`↔`from_dict` and `write`↔`read`
round-trips; deterministic + insertion-order-independent bytes; malformed
`from_dict` raises; `manifest_for_settings` over OR+WA resolves the full
descriptor set; `verify_manifest` all-ok / missing / mismatch (same-size-diff-
bytes and truncated); `diff_manifests` added/removed/changed/unchanged +
`is_synced`.

## Verification

- `tests/test_manifest.py`: **13 passed**.
- Full suite: **393 passed** (was 380), no regressions.
- numpy/GDAL-free import verified.
- `ruff` not installed in this `.venv`, so lint was not run here; code follows
  repo conventions (`from __future__ import annotations`, frozen dataclasses,
  docstrings, 88-col).

## Phase 2 — Tile-budget controls (second #21 slice)

A second offline slice of #21 landed after the manifests: a **tile budget** that
caps how many 3DEP DEM COGs a single acquisition may fetch, failing fast before
any download.

- `src/config.py`: `ElevationSettings.tile_budget` (added to `DEFAULTS` as `0`;
  boundary-validated in `_coerce_elevation` — non-negative int, `bool` and
  non-int rejected with `ConfigError`). `0` = unlimited, mirroring the
  `min_*_area_m2: 0.0` "keep everything" convention.
- `src/dem.py`: pure `count_tiles(boundary, tier, discoverer=None)` preflight
  (offline estimate, no download) + a `max_tiles: int = 0` parameter on
  `acquire_dem` that raises `ElevationError` **after discovery, before the
  download loop** when the region's tile count exceeds the budget. Feed it
  `settings.elevation.tile_budget`.
- Tests: `tests/test_elevation_config.py` (+4: default/positive/negative/non-int)
  and `tests/test_dem.py` (+4: `count_tiles` matches discovery; within-budget
  proceeds; over-budget raises before any fetch — fake downloader asserted
  never called; `max_tiles=0` unlimited). Full suite: **401 passed**.

**Resumable jobs — already built.** Investigation showed #21's "resumable jobs"
concern is essentially already implemented: `src/download.py`'s `Downloader`
streams to a `.part` temp file, resumes via an HTTP `Range` request, verifies,
and atomically moves into place; and `acquire`/`acquire_dem` skip already-cached
files. Re-running an interrupted acquisition therefore resumes naturally. No new
work was needed here beyond noting it.

## Phase 3 — Package preflight planner (third #21 slice)

A third offline slice composes the manifest + tile-budget primitives into a single
**"is this cache ready to ship?"** verdict, plus the `tools/` CLI the earlier
follow-up note called for.

- `src/packaging.py` — pure/offline planner. `PackagingError(AcquisitionError)`;
  a frozen `PackagePlan` (`required`/`present`/`missing`/`corrupt` disjoint key
  subsets + `total_bytes` + `tile_count`/`tile_budget`) with `is_complete`,
  `within_tile_budget`, and `is_ready` properties; `plan_package(cache, settings,
  *, cache_root=None, tile_count=None)` resolves the required files, builds a
  manifest of the cached subset, and verifies it — a key is `present` if it
  verifies, `corrupt` if cached-but-mismatched, else `missing`. `format_plan(plan)`
  renders a one-block human summary (readiness verdict, counts, DEM tile preflight,
  and the missing/corrupt keys). Imports only stdlib + `src.manifest`/`datasets`/
  `config`/`cache`; not in `PIPELINE_STAGES`.
- The DEM tile count is **injected** (`tile_count`), compared against
  `settings.elevation.tile_budget` (0 = unlimited); `None` skips the preflight so
  the planner stays offline rather than reimplementing WBD boundary loading.
- `tools/package_cache.py` — thin non-offline CLI: `--region` (nargs+),
  `--cache-dir`, `--config`, optional `--tile-count` (from `src.dem.count_tiles`).
  Builds `Settings` via `resolve_settings`, opens the real `Cache`, prints
  `format_plan`, exits `0` when ready else `1`.
- Tests: `tests/test_packaging.py` (+7) — TG-P1 coverage (full/missing/corrupt/
  determinism) and TG-P2 (tile-budget within/over/unlimited/skipped, `is_ready`,
  `format_plan`), a real `Cache` in `tmp_path` with hand-written archive bytes.
  Full suite: **430 passed** (+7), no regressions. Smoke-tested the CLI: empty
  cache → "NOT READY" exit 1 listing 8 missing files; populated cache → "READY"
  exit 0 with "DEM tiles: 5 (budget unlimited) — within budget".

## Not done / follow-ups (remain open on roadmap #21)

- **Region expansion** beyond OR/WA/CA — needs real WBD to derive HUC4 coverage
  for more states (`tools/derive_state_huc4.py` against the national WBD GDB).
- **Wiring the tile budget end-to-end** — `acquire_dem` accepts `max_tiles`, but
  nothing calls it with `settings.elevation.tile_budget` yet (the DEM subsystem
  isn't in `PIPELINE_STAGES`); the wiring lands when a real DEM entry point does.
- A `tools/` packaging CLI shipped as `tools/package_cache.py` (Phase 3 above:
  `plan_package` + `format_plan` readiness check with an injected `--tile-count`
  preflight). A `write_manifest`-to-disk variant over a real NAS cache (emit a
  portable manifest alongside the packaged files; `verify_manifest` on the
  transferred copy) remains a small non-offline follow-on.
