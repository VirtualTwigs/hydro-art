# Implementation Report — Gallery Catalog Management (Epoch 33)

## Summary

Implemented the operational inventory layer between raw render output and the public
gallery. The operator can now ingest renders, curate them through a status lifecycle
(draft → review → published → archived), organize into structured sections, version
re-renders, and export a static JSON file for the web gallery.

## Deliverables

### `src/catalog.py` — domain logic (offline, pure)
- `CatalogEntry` frozen dataclass with 18 fields covering render identity, provenance,
  operator decisions, display metadata, and file references.
- `GallerySection` frozen dataclass with 4 predefined sections (Featured, By Region,
  Seasonal, Limited Edition).
- `CatalogStore` — in-memory + JSON-file-backed persistence with CRUD, status
  transitions, filtering (status/region/section/tag), and versioning.
- `artwork_key` — 5-tuple identity for "same artwork" across versions.
- `build_entry_id` — deterministic slug from render identity.
- `validate_entry` — validates against `SUPPORTED_REGIONS`, `ORDER_STYLES`, `ENDPOINTS`.
- `public_entries` / `public_gallery` — export only latest published version per key,
  grouped by section.
- `seed_from_gallery_matrix` — imports existing 6-item `GALLERY_MATRIX` as draft entries.

### `tests/test_catalog.py` — 48 offline tests
- Group 1: Data model & validation (4 + 5 + 3 + 5 = 17 tests)
- Group 2: CatalogStore CRUD (9 tests)
- Group 3: Status transitions (7 tests)
- Group 4: Versioning (4 tests)
- Group 5: Public export (7 tests)
- Group 6: Seed from GALLERY_MATRIX (4 tests)

### `tools/catalog.py` — operator CLI
Commands: `ingest`, `list`, `review`, `publish`, `reject`, `archive`, `update`,
`export-public`, `seed`. Auto-generates thumbnails via PIL on ingest. SHA-256 hashing
of primary deliverable for provenance.

### `web/gallery.html` — upgraded
Tries curated gallery (`data/gallery.json`) first; falls back to raw output browser
(`/api/gallery/outputs`) if unavailable. Curated mode renders structured sections with
headings, descriptions, thumbnails, entry metadata, and "Order" links to `order.html`.

### `web/data/` — static export directory
Created with `.gitkeep`. `tools/catalog.py export-public` writes `gallery.json` here.

## Test results

- **Full offline suite: 1641 passed** (48 new + 1593 existing, 0 failures)
- **Recipe roundtrip: 11/11 passed**
- No regressions in any existing test module.

## Design decisions

1. **Batch ingest by default** — `tools/catalog.py ingest --output-dir` scans for all
   deliverable files; `--entry-id` overrides for single-item.
2. **Structured sections** — 4 predefined (`featured`, `by-region`, `seasonal`,
   `limited-edition`); operator assigns on publish or update.
3. **Versioning** — `next_version` auto-increments; `auto_archive_prior=True` archives
   the previous published version when a new version is ingested.
4. **Thumbnails** — PIL resize to 400x400 max, aspect-preserved. SVG-only renders
   produce no thumbnail (set to `None`).
5. **No Etsy/Stripe sync** — pricing lives in the storefront, not the catalog.
6. **Curated-first web gallery** — tries `data/gallery.json` before falling back to the
   raw API browser, so the page works both in production and during development.
