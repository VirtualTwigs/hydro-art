# Tasks — Gallery Catalog Management (Epoch 33, #146–#153)

## Group 1 — Data model, validation, store (#146)

Tests first, then implementation.

- [x] 1.1 Write `tests/test_catalog.py` Group 1 (data model & validation) + Group 2 (store CRUD) — ~14 tests
- [x] 1.2 Implement `src/catalog.py`: `CatalogEntry`, `GallerySection`, `ENTRY_STATUSES`, `STATUS_TRANSITIONS`, `artwork_key`, `build_entry_id`, `validate_entry`, `CatalogError`
- [x] 1.3 Implement `CatalogStore`: init, add, get, list (with filters), save/load JSON, deterministic serialization
- [x] 1.4 Run Group 1+2 tests — all green

## Group 2 — Status transitions (#146 cont.)

- [x] 2.1 Write `tests/test_catalog.py` Group 3 (status transitions) — ~5 tests
- [x] 2.2 Implement `CatalogStore.transition` with validation against `STATUS_TRANSITIONS`
- [x] 2.3 Run Group 3 tests — all green

## Group 3 — Versioning (#150)

- [x] 3.1 Write `tests/test_catalog.py` Group 4 (versioning) — ~4 tests
- [x] 3.2 Implement `next_version`, version-aware add, auto-archive prior published
- [x] 3.3 Run Group 4 tests — all green

## Group 4 — Public export + seed (#149, #151)

- [x] 4.1 Write `tests/test_catalog.py` Group 5 (public export) + Group 6 (seed) — ~8 tests
- [x] 4.2 Implement `public_entries`, `public_gallery`, `seed_from_gallery_matrix`
- [x] 4.3 Implement `GallerySection` defaults (`DEFAULT_SECTIONS`) and section-grouped export
- [x] 4.4 Run Group 5+6 tests — all green

## Group 5 — Operator CLI (#147, #148)

- [x] 5.1 Implement `tools/catalog.py` CLI: ingest (with batch scan + SHA-256 hashing + PIL thumbnail generation), list, review, publish, reject, archive, update, export-public, seed
- [x] 5.2 Manual smoke test: ingest a test render, transition through lifecycle, export public JSON

## Group 6 — Web gallery upgrade (#152)

- [x] 6.1 Create `web/data/` directory structure
- [x] 6.2 Upgrade `web/gallery.html` to read `web/data/gallery.json`, render structured sections with thumbnails + metadata, link to order form
- [x] 6.3 Graceful fallback when gallery.json missing

## Group 7 — Full suite + close (#153)

- [x] 7.1 Run full offline test suite — all green, no regressions
- [x] 7.2 Run recipe roundtrip — all green
- [x] 7.3 Write `implementation/report.md`
