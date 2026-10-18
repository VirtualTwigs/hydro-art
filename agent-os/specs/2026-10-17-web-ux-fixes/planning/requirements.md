# Requirements — Web UX Fixes (2026-10-17)

## Origin

User-reported issues during manual testing of the live Riverglyph customer site.

## Issues

### 1. Catalog cards on start.html link to order page instead of showing artwork

**Current:** Clicking any of the four catalog cards (Poster, Report, Digital, Animation)
on `start.html` immediately navigates to `order.html?product=<type>` or `report.html`.
The customer never gets to see the artwork at full resolution before committing to an
order flow.

**Desired:** Clicking the card image opens a lightbox/modal showing a high-resolution
version of that example image. The order CTA ("Start design →") remains accessible —
either as a button within the lightbox or via the existing card text area — but the
primary image click showcases the art first.

### 2. Studio nav link visible on customer-facing pages

**Current:** `order.html` and `ops.html` include a "Studio" nav link pointing to
`studio.html`. Studio is an internal art-direction tool, not a customer feature.

**Desired:** Remove the Studio nav link from `order.html` and `ops.html`. Do NOT touch
`proof.html` support email addresses (`hello@runde.studio` is a domain, not the Studio
feature). `studio.html` itself stays in the repo for internal use but must not be linked
from any customer-visible navigation.

### 3. Gallery images not loading (gallery.html)

**Current:** The curated gallery at `gallery.html` reads `web/data/gallery.json`, but
every entry has `"thumbnail": null`. The renderer shows "Preview coming soon" for all
items instead of actual artwork.

**Desired:** Gallery entries display actual thumbnails. The existing `tools/catalog.py
ingest` pipeline generates thumbnails via PIL; the `export-public` command writes them
into `gallery.json`. The fix is to either (a) run the catalog tool to populate
thumbnails, or (b) hardcode thumbnail paths to known existing output images, or
(c) make the gallery renderer fall back gracefully (e.g., use the raw output browser
API to find a preview for entries with null thumbnails).

## Constraints

- No `src/` pipeline changes. No `PIPELINE_STAGES` change.
- No changes to `studio.html` itself (it stays as an internal tool).
- Must not break the offline test suite or recipe roundtrip.
- `proof.html` email addresses (`hello@runde.studio`) must not be altered.
