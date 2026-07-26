# Specification: Dataset Acquisition & Cache

## Goal
Resolve, download, verify, extract, and cache the public hydrography archives (USGS NHDPlus HR / NHD / WBD) required for the configured regions, so downstream stages can load render-ready GIS files without any manual fetching and without re-downloading data that is already cached.

## User Stories
- As a user, I want the tool to automatically download the datasets my region needs so that I never have to hunt for USGS files.
- As a user re-running the build, I want already-downloaded data to be reused so that runs are fast and offline-friendly.
- As a developer, I want dataset access behind an injectable interface so that the acquisition flow is fully testable without network access.

## Specific Requirements

**Dataset registry**
- Define a registry of supported datasets (NHDPlus HR primary, NHD fallback, WBD for HUC polygons) with, per dataset: id, human name, priority, and a URL template.
- Keep optional sources (HydroSHEDS, MERIT Hydro) declared but not required for this release.
- Registry is the single place to edit to add/adjust dataset sources.

**Region → required files resolution**
- Map each supported region (Oregon, Washington) to the HUC4 codes covering it.
- Given a `Settings`, resolve the concrete list of required archive descriptors (dataset id, region/HUC, filename, url, expected checksum if known) needed for the run.
- Deduplicate descriptors so a HUC4 shared by two regions is fetched once.

**Fetcher abstraction (DI seam)**
- Define a `Fetcher` protocol used for all network I/O (e.g. `head`/`open` for range-aware streaming).
- Provide a stdlib `UrllibFetcher` implementation; tests inject a fake.
- No module performs bare network calls; the fetcher is injected into the downloader.

**Resumable download**
- Stream downloads to a temp file, then atomically move into the cache on success.
- Support HTTP Range resume: if a partial temp file exists, continue from its offset.
- Retry transient failures with exponential backoff; surface a clear error after max retries.

**Integrity verification**
- Verify a completed download against an expected SHA-256/size when the registry provides one; otherwise verify archive integrity (zip CRC) after download.
- A file failing verification is discarded (not left in the cache) and re-attempted per retry policy.

**Persistent cache + metadata**
- Store archives under `cache/` keyed by a stable id (dataset + region/HUC + filename), persisting between runs.
- Maintain a JSON metadata index recording url, size, checksum, source release/timestamp, and download time.
- Skip download when a cached entry exists and passes verification (avoid duplicate downloads); expose a way to detect a newer release later.

**Archive extraction**
- Extract downloaded zip archives into `datasets/` under a per-dataset/region layout.
- Guard against path traversal (zip-slip); reject entries that escape the target dir.
- Skip extraction when the expected extracted output already exists.

**Error recovery**
- Gracefully handle network failures, partial downloads, and corrupted archives per PRD §28, with actionable messages and safe cleanup of partial artifacts.

**Pipeline integration**
- Replace the `download` and `extract` pipeline stubs so they run the acquisition and extraction against `Settings.regions`, logging progress via `rich`.
- Downstream stages remain stubs; acquisition returns/records the paths of extracted GIS data for later stages.

## Existing Code to Leverage

**`src/config.py` — `Settings` and allowlists**
- `Settings.regions` drives which HUC4s/files to resolve; reuse `SUPPORTED_REGIONS` as the region key set.
- Reuse `ConfigError` style for a new `AcquisitionError` (specific exception type per the error-handling standard).

**`src/pipeline.py` — `Pipeline`/`Stage`**
- Replace the `download` and `extract` stub `Stage`s; keep the DI pattern (stages receive `Settings` + console).

**`src/cli.py` / `build.py`**
- No CLI changes required for this stage; the acquisition runs inside the existing pipeline invocation.

## Out of Scope
- Any GIS processing: reading, validating, repairing, reprojecting, or clipping geometries (roadmap items #3–#4).
- Graph construction, stream ordering, watersheds, coloring, rendering, export (items #5–#10).
- HydroSHEDS / MERIT Hydro acquisition (declared in the registry but not implemented this release).
- "Detect newer releases" auto-refresh logic beyond storing the metadata needed to support it later.
- Parallel/multiprocessing download optimization (performance tuning is a later concern).
- Downloading real multi-GB datasets during tests — tests must run offline against a fake fetcher.
