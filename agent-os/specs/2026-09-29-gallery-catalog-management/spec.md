# Spec — Gallery Catalog Management (Epoch 33, #146–#153)

## Overview

An operational inventory layer between raw render output and the public gallery.
The operator ingests renders, curates them through a status lifecycle, organizes
them into structured sections, and exports a static JSON file for the web gallery.

## Data model

### CatalogEntry

```python
@dataclass(frozen=True)
class CatalogEntry:
    entry_id: str              # e.g. "wa-clark-neon-basin-24x36"
    version: int               # 1, 2, 3… incremented on re-render

    # Render identity (immutable — defines the "same artwork" key)
    region: str
    county: str | None
    style: str
    endpoint: str              # digital_image | print_image | animation | report
    size: str | None           # "24x36", None for digital-only

    # Provenance
    rendered_at: str           # ISO 8601 timestamp
    render_hash: str           # SHA-256 of primary deliverable
    sources: tuple[str, ...]   # attribution strings

    # Operator decisions
    status: str                # draft | review | published | archived | rejected

    # Display metadata
    title: str
    description: str
    tags: tuple[str, ...]      # freeform tags for filtering
    section: str | None        # gallery section assignment
    sort_order: int            # manual ordering within section (lower = first)

    # Files (relative paths under catalog root)
    deliverables: tuple[str, ...]
    thumbnail: str | None      # relative path to generated thumbnail
```

**Artwork key** (uniqueness for versioning): `(region, county, style, endpoint, size)`.
Two entries with the same key but different `version` are versions of the same artwork.

### GallerySection

```python
@dataclass(frozen=True)
class GallerySection:
    section_id: str            # "featured", "by-region", "seasonal", "limited-edition"
    display_name: str          # "Featured", "By Region", …
    sort_order: int            # section ordering in the public gallery
    description: str           # short blurb shown above the section
```

Predefined sections (operator can add more via CLI):

| ID | Display Name | Sort | Purpose |
|----|-------------|------|---------|
| `featured` | Featured | 0 | Hero picks, front and center |
| `by-region` | By Region | 10 | Organized by state/region |
| `seasonal` | Seasonal | 20 | Time-limited or seasonal renders |
| `limited-edition` | Limited Edition | 30 | Exclusive or numbered runs |

### CatalogStore

JSON-file-backed persistence at `catalog/catalog.json`:

```json
{
  "schema": "hydro-art/catalog@1",
  "sections": [ ... ],
  "entries": [ ... ]
}
```

Deterministic output: `sort_keys=True`, entries sorted by `(section_sort, sort_order, entry_id, -version)`.

## Status lifecycle

```
                  ┌──────────┐
                  │  draft   │ ← ingest creates here
                  └────┬─────┘
                       │ review
                  ┌────▼─────┐
              ┌───│  review  │───┐
              │   └──────────┘   │
         publish              reject
              │                  │
         ┌────▼─────┐     ┌─────▼────┐
         │published │     │ rejected │
         └────┬─────┘     └──────────┘
              │ archive
         ┌────▼─────┐
         │ archived │──── republish ────► published
         └──────────┘
```

Valid transitions:

| From | To |
|------|-----|
| draft | review, rejected |
| review | published, rejected |
| published | archived |
| archived | published (republish) |
| rejected | (terminal) |

## Module boundaries

### `src/catalog.py` (offline, pure)

Domain logic — no I/O beyond what's injected:

- `CatalogEntry`, `GallerySection` dataclasses
- `ENTRY_STATUSES`, `STATUS_TRANSITIONS` constants
- `artwork_key(entry) -> tuple` — the versioning identity
- `CatalogStore` — load/save/query catalog JSON, transition validation
- `next_version(store, key) -> int` — resolve next version number
- `public_entries(store) -> list` — published entries, latest version per key
- `public_gallery(store) -> dict` — structured export grouped by section
- `build_entry_id(region, county, style, endpoint, size) -> str` — deterministic ID
- `validate_entry(entry) -> None | raises CatalogError` — region/style/endpoint checks

Does **not** import GDAL/PIL/network. Uses `src.config.SUPPORTED_REGIONS` and
`src.fulfillment.ORDER_STYLES` for validation (same pattern as `src/gallery.py`).

### `tools/catalog.py` (operator CLI, outside offline suite)

Orchestration + I/O:

- **ingest** — scan directory, hash files, generate thumbnails (PIL), call `CatalogStore.add`
- **list** — filter by status/region/section/tag, tabular output
- **review / publish / reject / archive** — status transitions
- **update** — edit title/description/tags/section/sort-order
- **export-public** — write `web/data/gallery.json`
- **seed** — one-time import from `GALLERY_MATRIX` into the catalog

Thumbnail generation: PIL `Image.open().thumbnail((400, 400))` preserving aspect ratio.
For SVG-only renders: skip thumbnail (set to `None`); operator can provide one manually.

### `web/gallery.html` (upgrade)

Reads `web/data/gallery.json`. Renders sections with headings, thumbnails, titles,
descriptions. Each entry links to order form. Replaces the current raw-output browser.
Falls back gracefully if the JSON file doesn't exist (shows "Gallery coming soon").

## Versioning rules

1. On ingest, compute `artwork_key` from the render's metadata.
2. Query `CatalogStore` for existing entries with that key.
3. If found: `version = max(existing versions) + 1`. Previous latest gets auto-archived
   if it was published (operator can override).
4. If not found: `version = 1`.
5. The public gallery export resolves "latest published version" per artwork key.

## Determinism

- `catalog.json` uses `sort_keys=True` + canonical entry ordering.
- `build_entry_id` is a pure function of its inputs.
- `public_gallery` output is deterministic for a given catalog state.
- Thumbnail generation is outside the determinism boundary (image encoding varies);
  thumbnails are not hashed or compared in golden fixtures.

## Test strategy

All `src/catalog.py` tests are offline (no PIL, no filesystem beyond temp dirs).

### Unit tests (`tests/test_catalog.py`)

**Group 1 — Data model & validation**
- `CatalogEntry` construction with all fields
- `artwork_key` extracts the correct 5-tuple
- `build_entry_id` produces deterministic slugs
- `validate_entry` accepts valid entries
- `validate_entry` rejects unknown region/style/endpoint
- `GallerySection` construction and ordering

**Group 2 — CatalogStore CRUD**
- Create store, add entry, retrieve by ID
- Add duplicate entry_id raises `CatalogError`
- List entries with status filter
- List entries with region/section/tag filters
- Store round-trips through JSON (save → load → identical)
- JSON output is deterministic (`sort_keys`, canonical order)

**Group 3 — Status transitions**
- Each valid transition succeeds
- Invalid transitions raise `CatalogError`
- Transition updates the entry in the store
- Rejected is terminal (no transitions out)
- Archived → published (republish) works

**Group 4 — Versioning**
- `next_version` returns 1 for new artwork key
- `next_version` returns N+1 for existing key with N versions
- `public_entries` returns only latest published version per key
- Re-ingest auto-archives prior published version

**Group 5 — Public export**
- `public_gallery` groups entries by section
- Sections are ordered by `sort_order`
- Entries within a section are ordered by `sort_order` then `entry_id`
- Non-published entries are excluded
- Export schema matches `hydro-art/catalog-public@1`
- Empty catalog produces valid empty structure

**Group 6 — Seed from GALLERY_MATRIX**
- `seed_from_gallery_matrix` creates entries for all 6 curated items
- Seeded entries have status `draft`
- Seeded entries preserve item_id as entry_id
- Idempotent — re-seeding skips existing entries

## File layout

```
src/catalog.py                              # domain logic (offline)
tests/test_catalog.py                       # offline unit tests
tools/catalog.py                            # operator CLI (PIL, filesystem)
catalog/catalog.json                        # persistent store (git-tracked)
catalog/thumbnails/                         # generated thumbnails (git-ignored)
web/data/gallery.json                       # public export (git-tracked)
web/gallery.html                            # upgraded gallery page
tests/fixtures/golden/catalog/              # golden fixtures for determinism
```

## Integration with existing systems

| System | Integration |
|--------|------------|
| `src/gallery.py` | `seed_from_gallery_matrix` imports `GALLERY_MATRIX`; gallery.py unchanged |
| `src/fulfillment.py` | Validates styles/sizes against `ORDER_STYLES`/`SIZES` |
| `src/config.py` | Validates regions against `SUPPORTED_REGIONS` |
| `src/endpoints.py` | Validates endpoints against known endpoint names |
| `web/order.html` | Published entries link to order form with pre-filled params |
| `tools/render_gallery.py` | Render → ingest pipeline (future wiring) |
