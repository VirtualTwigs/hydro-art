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

## Not done / follow-ups (remain open on roadmap #21)

- **Region expansion** beyond OR/WA/CA — needs real WBD to derive HUC4 coverage
  for more states (`tools/derive_state_huc4.py` against the national WBD GDB).
- **Tile-budget controls** — cap 3DEP DEM tiles per run behind the
  `TileDiscoverer` seam.
- **Resumable jobs** — resume partial acquisition behind `DownloaderLike`/`Cache`.
- A thin `tools/` packaging CLI (`build_manifest` → `write_manifest` over a real
  NAS cache; `verify_manifest` on a transferred copy) — the offline engine ships
  here; the CLI wrapper is a non-offline follow-on.
