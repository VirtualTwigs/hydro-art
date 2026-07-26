# Requirements: Dataset Acquisition & Cache

## Raw Idea (from roadmap item #2)

Discover and download the required USGS NHDPlus HR / NHD / WBD files for the selected region, with resumable downloads, integrity verification, archive extraction, metadata storage, and a persistent cache that avoids duplicate downloads.

## Source Requirements (from docs/PRD.md)

- **§6 Automatic Dataset Download:** discover required files, download, resume downloads, verify integrity, extract archives, maintain local cache, avoid duplicate downloads, store metadata, detect newer releases.
- **§5.2 Supported Datasets (priority order):** USGS NHDPlus HR (primary), USGS NHD (fallback), Watershed Boundary Dataset / WBD (HUC polygons), HydroSHEDS (optional), MERIT Hydro (optional).
- **§7 Data Storage:** `datasets/`, `cache/`, `output/`, `logs/`; cache persists between runs.
- **§28 Error Recovery:** gracefully recover from network failures, partial downloads, and corrupted archives.
- **§27 Logging:** rich terminal output with download progress and timing.
- **§30 Code Quality:** type hints, docstrings, DI, no global state, unit tests.

## Design Notes / Decisions

- **Region → files:** USGS distributes NHDPlus HR and WBD as per-HUC4 archives. Region names map to the HUC4 codes that cover them; the acquisition stage resolves the archive URLs for those HUC4s.
- **Testability first:** all network access goes through an injectable fetcher abstraction so the full flow can be tested offline with a fake fetcher / local files. No test may hit the real USGS servers.
- **No new heavy deps:** use the Python standard library (`urllib`, `hashlib`, `zipfile`, `json`) plus the already-present `rich` for progress. GIS libraries are NOT needed for this stage.
- **Cache is content-addressed by a stable key** (dataset id + region/HUC + filename); a JSON metadata index records url, size, checksum, timestamp, and source release so duplicate downloads are skipped and newer releases can be detected later.
- **Safety:** archive extraction must guard against path traversal (zip-slip).

## Open Questions (resolve during implementation)

- Exact NHDPlus HR URL template and whether a discovery/listing step is needed vs. a static template — start with a documented URL template per dataset and keep it in a registry that is easy to update.
- Checksum availability: if USGS publishes a sidecar checksum, verify against it; otherwise verify by expected content-length and archive integrity (zip CRC).
