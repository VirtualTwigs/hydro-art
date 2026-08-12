# Requirements — Regional scale & offline packaging (roadmap #21)

## Roadmap text

> 21. Regional scale & offline packaging — Expand from Oregon/Washington to
> additional U.S. states, with tile-budget controls, resumable jobs, and portable
> cache manifests. `XL`

## Scope this pass — portable cache manifests

#21 is `XL` and spans four concerns:

1. Region expansion (more U.S. states) — partly done (`California` already wired
   in `SUPPORTED_REGIONS` + `REGION_HUC4`); further states are a data-curation
   task needing real WBD to derive HUC4 coverage.
2. Tile-budget controls — DEM-subsystem concern behind the `TileDiscoverer` seam.
3. Resumable jobs — acquisition-resume behind the `DownloaderLike`/`Cache` seams.
4. **Portable cache manifests** — a deterministic, verifiable manifest of cached
   dataset files that can be exported, moved, and used to verify or reconcile a
   cache on another machine.

Per the user's decision (2026-08-12), **this pass delivers concern #4 only** — the
most self-contained, fully offline-testable slice. Concerns 1–3 are deferred to
later passes (they need live downloads / NAS / real WBD that cannot run in the
offline, GDAL-free test posture). This mirrors how #12/#13 shipped their tested
logic while deferring real-data execution.

## Why portable cache manifests

The download stage caches large hydrography archives on a NAS
(`NAS_CACHE_DIR = /Volumes/home/data/incoming`) and records provenance in the
`Cache` JSON index (url, size, checksum, timestamps). "Offline packaging" means
being able to:

- **Export** an auditable, deterministic manifest of exactly which files a cache
  holds for a given region set (dataset id, HUC code, url, checksum, size, path).
- **Verify** that a cache directory (e.g. after copying the NAS cache to another
  machine, or a removable drive) matches the manifest — files present, checksums
  and sizes intact — before a run trusts it.
- **Diff** two manifests to see what a target cache is missing / has stale, so an
  offline transfer can be reconciled without re-downloading everything.

## Functional requirements

- **Deterministic**: the same cache state produces byte-identical manifest output
  (entries sorted by key; no wall-clock time in the canonical form; stable JSON).
- **Portable**: entry paths are stored **relative to the cache root**, so a
  manifest stays valid after the cache is moved.
- **Verifiable**: verification recomputes SHA-256 + size against the manifest and
  reports `ok` / `missing` / `mismatched` per entry with a completeness verdict.
- **Reconcilable**: a manifest diff classifies keys as added / removed / changed /
  unchanged (changed = same key, different checksum).
- **Region-aware**: a convenience builder produces a manifest for the files a
  `Settings` resolves to (`resolve_required_files`), so multi-state coverage
  (OR/WA/CA today) round-trips through one manifest.
- **Boundary-validated**: malformed manifest data raises a `ManifestError`
  (acquisition-domain, subclasses `AcquisitionError`).

## Non-functional / guardrails

- Pure, deterministic, **offline**: `src/manifest.py` imports only stdlib +
  `src.datasets` / `src.config` / `src.cache` — no numpy / geopandas / GDAL, so
  `tests/test_manifest.py` runs in the offline suite.
- No new global state; frozen dataclasses for value objects; reuse the existing
  `Cache` (`record`/`metadata`/`path_for`) and `FileDescriptor` unchanged.
- Not wired into `PIPELINE_STAGES` — this is an offline packaging/audit utility,
  same posture as the other acquisition helpers.

## Out of scope (deferred, tracked on roadmap #21)

- Region expansion beyond OR/WA/CA (needs real WBD to derive HUC4 maps).
- Tile-budget enforcement and resumable acquisition (need the DEM/download seams
  exercised against live data).
- A `tools/` packaging CLI over a real NAS cache (the offline engine ships here).
