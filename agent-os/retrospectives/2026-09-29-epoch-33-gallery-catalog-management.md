# Epoch 33 Retrospective — Gallery Catalog Management

**Date:** 2026-09-29
**Items:** #146–#153
**Suite at close:** 1641 passed (48 new catalog tests)

## What shipped

An operational inventory layer between raw render output and the public gallery.
`src/catalog.py` defines `CatalogEntry` (18-field frozen dataclass), `GallerySection`
(4 predefined sections), and `CatalogStore` (in-memory + JSON persistence with CRUD,
status transitions, filtering, and versioning). The status lifecycle
(draft → review → published → archived/rejected) enforces `STATUS_TRANSITIONS`; versioning
auto-archives prior published entries when a new version of the same artwork is ingested.

`tools/catalog.py` is the operator CLI: `ingest` (batch scan + SHA-256 hashing + PIL
thumbnail generation), `list`, `review`, `publish`, `reject`, `archive`, `update`,
`export-public`, and `seed` (imports existing `GALLERY_MATRIX` as draft entries).
`export-public` writes `web/data/gallery.json` — only the latest published version per
artwork key, grouped by section.

`web/gallery.html` upgraded to try `data/gallery.json` first (structured sections with
headings, descriptions, thumbnails, metadata, and "Order" links), falling back to the raw
output browser when the file is missing.

## What went well

- **TDD discipline held.** 48 tests written before implementation across 6 groups; all
  green before moving to the next group, no regressions at close.
- **Clean separation.** `src/catalog.py` is pure/offline (stdlib + `src.config` +
  `src.gallery` + `src.endpoints`), `tools/catalog.py` is the only module that touches
  PIL/filesystem. No pipeline coupling.
- **Seed migration is smooth.** `seed_from_gallery_matrix` imports the existing 6-item
  gallery as draft entries, preserving the transition to curated catalog without losing
  existing content.

## What to watch

- **Thumbnails require PIL.** `tools/catalog.py ingest` depends on Pillow for thumbnail
  generation. SVG-only renders produce no thumbnail. This is fine for the operator CLI
  but would need a fallback if automated ingest runs in a minimal environment.
- **No automatic publish.** The operator must manually transition entries through the
  lifecycle. Automation (e.g., auto-publish on successful CI render) is a future concern.
- **Gallery JSON is static.** `export-public` writes a snapshot; the web gallery doesn't
  poll or update dynamically.
