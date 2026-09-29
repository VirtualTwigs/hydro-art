# Requirements — Gallery Catalog Management (Epoch 33)

## Problem

Rendered artworks go from `output/` directly to a hardcoded 6-item `GALLERY_MATRIX` or
a raw file browser (`web/gallery.html`). There is no operational layer for the operator
to review, curate, version, or selectively publish inventory. The operator cannot:

- Track what has been rendered vs. what is publicly visible.
- Hold a render in draft while evaluating art direction.
- Re-render an artwork and track it as a new version.
- Organize the public gallery into structured sections.
- Generate thumbnails or preview images automatically.

## Goals

1. **Inventory visibility** — every rendered artwork is tracked with provenance (hash,
   timestamp, sources) from the moment it is ingested.
2. **Status lifecycle** — operator moves entries through draft → review → published →
   archived, with rejected as a terminal branch. Only `published` entries appear publicly.
3. **Auto-thumbnails** — ingest generates a resized preview image (PIL) so the operator
   and public gallery have fast-loading previews without manual work.
4. **Batch ingest** — scanning an output directory creates draft entries for all renders
   found; single-item ingest also supported via `--entry-id`.
5. **Structured sections** — the public gallery is organized into named sections
   (Featured, By Region, Seasonal, Limited Edition) with manual sort ordering, not a
   flat list.
6. **Versioning** — re-rendering the same artwork (same region+county+style+endpoint+size)
   creates a new version; the catalog resolves "latest published" for display.
7. **Static export** — `tools/catalog.py export-public` writes a deterministic JSON file
   consumed by the web gallery. No API needed; works with `file://`.
8. **CLI-driven** — all operations via `tools/catalog.py`. No hand-editing JSON.

## Non-goals

- Etsy/Stripe sync (deferred to fulfillment integration).
- Pricing management (lives in the storefront, not the catalog).
- Customer-facing CRUD (operator-only).
- Authentication/authorization (single-operator system).
- Real-time API (static export is sufficient).

## Constraints

- `src/catalog.py` must be pure/offline (no GDAL, no network). Follows the existing
  pattern of `src/gallery.py` and `src/fulfillment.py`.
- Thumbnail generation (PIL/Pillow) is in `tools/catalog.py` (outside the offline suite),
  not in `src/catalog.py`.
- `catalog/catalog.json` is git-tracked, deterministic (`sort_keys`).
- The existing `GALLERY_MATRIX` in `src/gallery.py` seeds the initial catalog but is not
  modified or removed (backward compatibility with existing ledger/golden fixtures).
- Must not break the offline test suite or any existing determinism guarantees.

## Stakeholders

- **Operator (Neil)** — primary user; manages inventory from the CLI.
- **Public visitors** — see only published entries via the web gallery.

## Open questions (resolved during design)

1. **Batch vs explicit ingest?** → Batch by default (scan directory), with `--entry-id`
   for single-item override. Rationale: renders produce multiple files per artwork;
   scanning is less error-prone than listing each file.
2. **Gallery sections?** → Structured (Featured / By Region / Seasonal / Limited Edition).
   Operator assigns section on publish or update.
3. **Versioning on re-render?** → New version entry; catalog resolves latest published.
   Old versions stay in catalog as archived (operator can keep or prune).
4. **Thumbnail generation?** → Automatic on ingest via PIL resize. Default 400px wide,
   aspect-preserved. SVG-only renders get a placeholder or rasterized thumb via cairosvg
   if available.
