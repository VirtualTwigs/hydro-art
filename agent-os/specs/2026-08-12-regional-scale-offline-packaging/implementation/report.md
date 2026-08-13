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

## Phase 4 — Settings-driven DEM acquisition entry point (fourth #21 slice)

Closes the earlier "wire `tile_budget` into a live DEM entry point" follow-up. The
budget guard and cache-policy semantics already existed on `acquire_dem`; what was
missing was anything that read them off a validated `Settings`.

- `src/dem.py` — new `acquire_dem_for_settings(settings, *, boundary, cache,
  downloader, discoverer=None, log=…, clock=…)`. Reads `settings.elevation.tier`,
  `.tile_budget`, and `.cache_policy`; guards on `.enabled` (disabled → `ElevationError`
  before any discovery/fetch); maps `cache_policy == "refresh"` → `acquire_dem`'s
  `refresh` flag (the mapping `acquire_dem`'s own docstring names but nothing wired);
  forwards `max_tiles=tile_budget` into the existing fail-fast budget guard. Added to
  `__all__`. New import `from src.config import Settings` — no cycle (`src.config`
  imports nothing from `src`). Still pure/offline, not in `PIPELINE_STAGES`.
- Tests: `tests/test_dem.py` (+5, TG-W1) — reads tier+budget and proceeds within
  budget (tier honored → preview 30 m); over-budget fails fast (downloader never
  called); `tile_budget=0` unlimited; `enabled=False` raises before discovery;
  `cache_policy="refresh"` redownloads vs. `"reuse"` cache hit. Full suite:
  **435 passed** (+5), no regressions.

## Not done / follow-ups (remain open on roadmap #21)

- **Region expansion** beyond OR/WA/CA — needs real WBD to derive HUC4 coverage
  for more states (`tools/derive_state_huc4.py` against the national WBD GDB).
- **Wiring the tile budget** — done in Phase 4: `acquire_dem_for_settings` reads
  `settings.elevation.tile_budget` (+ tier + cache policy) and forwards to
  `acquire_dem`. The remaining step is putting the DEM subsystem into a real
  (non-offline) entry point / `PIPELINE_STAGES` — a larger effort out of this
  offline slice's scope.
- A `tools/` packaging CLI shipped as `tools/package_cache.py` (Phase 3 above:
  `plan_package` + `format_plan` readiness check with an injected `--tile-count`
  preflight). A `write_manifest`-to-disk variant over a real NAS cache (emit a
  portable manifest alongside the packaged files; `verify_manifest` on the
  transferred copy) remains a small non-offline follow-on.

## Addendum — Manifest packaging CLI (2026-08-13)

Closes the "`write_manifest`-to-disk packaging CLI over a real NAS cache" follow-on
noted just above. The serialization primitives already existed; this slice adds the
missing human-facing pieces.

**`src/manifest.py` (new, tested):** two pure formatters —
`format_verification(ManifestVerification) -> str` (COMPLETE/INCOMPLETE + `ok`/total,
then lists any `missing`/`mismatched` keys) and `format_diff(ManifestDiff) -> str`
(collapses to one "in sync" line, else lists non-empty added/removed/changed groups +
the unchanged count). Added to `__all__`. Tested in `tests/test_manifest.py` (+4:
complete/incomplete verification, synced/changed diff).

**`tools/cache_manifest.py` (new, thin CLI, not in the offline suite):** three
subcommands over a real (e.g. NAS) `Cache`, mirroring `tools/package_cache.py`'s
shape — `write` (`manifest_for_settings` → `write_manifest`; prints entry count +
bytes; `--strict` makes an un-recorded required file a hard error → exit 1),
`verify MANIFEST --cache-dir` (`read_manifest` → `verify_manifest` →
`format_verification`; exit 0 iff complete), and `diff OLD NEW`
(`read_manifest` ×2 → `diff_manifests` → `format_diff`; exit 0 iff synced).

**Verification:** smoke-tested `main()` offline against a fabricated Oregon tmp cache
(8 recorded files) — write exit 0 and file written; verify complete → 0, verify after
deleting a file → 1 (lists the missing key); diff identical → 0, diff with a changed
payload → 1 (lists the changed key); `--strict` on an empty cache → 1. Full Python
suite: **456 passed** (+4), no regressions.

**Still open on #21:** region expansion beyond OR/WA/CA (needs real WBD) and putting
the DEM subsystem into a real (non-offline) entry point / `PIPELINE_STAGES`.
