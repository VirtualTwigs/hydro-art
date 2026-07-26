# Implementation Report: Dataset Acquisition & Cache

**Date:** 2026-07-25
**Status:** Complete — all 4 task groups done, 37/37 tests passing

## What was built

| File | Purpose |
|------|---------|
| `src/datasets.py` | `Dataset` registry (`DATASETS`: NHDPlus HR primary, NHD fallback, WBD, optional HydroSHEDS/MERIT), `REGION_HUC4` map (single extension point for regions), immutable `FileDescriptor`, `resolve_required_files(settings)` with dedup by stable key, `AcquisitionError`. |
| `src/download.py` | `Fetcher` protocol + stdlib `UrllibFetcher` (HTTP Range), `Downloader.fetch` with resumable `.part` streaming, exponential-backoff retry, SHA-256 verification, atomic move, `ChecksumError`. |
| `src/cache.py` | Persistent content-keyed `Cache` with JSON metadata index (url/size/checksum/source_release/timestamp), zip-slip-safe `extract_archive`, `ensure_cached`, `extract_all`, and `acquire` orchestrator. |
| `src/pipeline.py` | `RunContext` (DI + `artifacts` bag), real `download`/`extract` stages replacing stubs; remaining 10 stages still stubs in PRD §8 order. |
| `build.py` | Now catches `AcquisitionError` → exit code 2; accepts an injectable `pipeline` for offline tests. |
| `tests/test_datasets.py`, `test_download.py`, `test_cache.py`, `test_acquisition_integration.py` | 5 + 6 + 4 + 3 = 18 new tests (37 total suite). |

## Key decisions

- **Injectable `Fetcher`/`Downloader` seam:** all network I/O passes through an injected fetcher, so the entire acquire flow is exercised offline with fakes (`FakeFetcher`, `CountingZipDownloader`) — no test touches the USGS network.
- **`acquire` split into `ensure_cached` + `extract_all`:** lets the pipeline's `download` and `extract` stages stay semantically honest while reusing one code path (DRY).
- **Resumable downloads via `.part` temp files:** partial downloads resume from a Range offset; corrupt/mismatched files are discarded before the atomic `replace(dest)`.
- **Content-keyed persistent cache:** second runs reuse verified archives (fetcher not called), verified by `test_second_run_reuses_cache_no_redownload`.
- **Zip-slip guard:** extraction rejects members whose resolved path escapes the target dir.
- **`DownloaderLike` protocol lives in `src/cache.py`** — pipeline imports it from there (not `src.download`).

## Acceptance criteria met

- Registry ordered by priority; Oregon/Washington map to correct HUC4s; resolution dedupes shared files into immutable descriptors.
- All network I/O goes through the injected fetcher; partial/corrupt downloads are cleaned up; verification failures re-attempt with backoff.
- Duplicate downloads avoided via cache; metadata index persists between runs as JSON; extraction is safe and idempotent.
- Pipeline `download`/`extract` run acquisition end-to-end with a fake fetcher in tests and the real fetcher in production; full suite passes with no regressions.

## Notes for next feature (roadmap #3: data loading & geometry validation/repair)

- `context.artifacts["dataset_dirs"]` holds the extracted `.gdb` directories — the input seam for loading.
- GIS dependencies (geopandas, pyogrio, gdal, shapely, fiona) still need adding to `requirements.txt` when the `validate`/`repair_geometries` stages are implemented.
- `expected_sha256` on `FileDescriptor` is currently `None` for all files (USGS TNM does not publish per-file checksums in the URL template); archive CRC via zip validation is the integrity backstop.
