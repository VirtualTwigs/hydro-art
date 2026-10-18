# Specification: Web UX Fixes (Lightbox, Studio Link, Gallery Thumbnails)

## Goal

Fix three user-reported UX issues on the customer-facing Riverglyph site: catalog cards should showcase artwork before funneling to the order flow, the internal Studio tool should not appear in customer navigation, and the gallery should display real thumbnails instead of "Preview coming soon" placeholders.

## User Stories

- As a visitor on start.html, I want to see artwork at full resolution when I click a catalog card so that I can appreciate the art before committing to an order flow.
- As a customer, I want navigation to show only pages relevant to me so that I am not confused by internal tools.
- As a visitor on gallery.html, I want to see actual artwork thumbnails so that the gallery feels curated and real.

## Architecture Placement

- **Offline `src/` module(s):** none
- **Non-offline `tools/` entry point(s):** none (gallery.json may be updated by hand or via existing `tools/catalog.py export-public`)
- **Touches `PIPELINE_STAGES`?** No
- **Injected seam reused/extended:** none
- **Determinism impact:** No effect on 2D pipeline output; no rendered bytes change

## Specific Requirements

**Lightbox modal on start.html**
- Add a single lightweight lightbox modal (HTML + CSS + vanilla JS) to `web/start.html`. No external dependencies.
- Clicking the `.thumb` image area of a catalog card opens the lightbox with the full-resolution image from `/output/landing/` (the same `<img>` source the card already references).
- The lightbox displays: the image scaled to near-full viewport (max ~90vw/90vh), a visible close button (top-right corner), and a "Start design" CTA button linking to the card's original order URL.
- Closing: click the close button, click the backdrop outside the image, or press Escape.
- The card's text/CTA area outside `.thumb` retains its existing navigation behavior (direct link to order page).
- When artwork is missing (404 fallback placeholder visible), clicking the card should still navigate to the order page -- do not open a lightbox for a placeholder.
- The lightbox must work without a build step and remain `file://`-safe.

**E2E test update for lightbox**
- The existing e2e test at `tests/e2e/tests/01-landing.spec.js` lines 102-115 clicks `a.cover` and asserts navigation to the order page. This test must be updated to reflect the new click behavior: clicking the image area opens the lightbox, and the lightbox CTA navigates to the order URL.
- Add a test that the lightbox opens on image click, displays the image, and can be closed via Escape/backdrop.
- Preserve the existing test that verifies card links exist (`a.cover` href attribute check at line 47).

**Remove Studio nav link from customer pages**
- Remove the `<a href="studio.html">Studio</a>` nav link from `web/order.html` (line 397) and `web/ops.html` (line 71).
- Do NOT modify `web/proof.html` -- `hello@runde.studio` is an email domain, not the Studio feature.
- Do NOT delete `web/studio.html` -- it remains as an internal tool, just unlinked from customer-facing navigation.
- If any e2e test asserts on the Studio nav link, update accordingly.

**Gallery thumbnail fallback in gallery.html**
- When a gallery entry has `"thumbnail": null`, the renderer should attempt a convention-based fallback path: `/output/gallery/<entry_id>/<entry_id>.png`.
- If neither the thumbnail field nor the fallback path resolves (image fails to load), retain the existing "Preview coming soon" placeholder.
- Use an `<img>` element with an `onerror` handler that swaps to the placeholder -- the same pattern start.html already uses for its fallback images.

**Populate gallery.json thumbnails for existing renders**
- Update `web/data/gallery.json` to set the `thumbnail` field for the `conus-neon-hero` entry to `/output/gallery/conus-neon-hero/conus-neon-hero.png` (known to exist in production output).
- Other entries with no existing gallery render keep `"thumbnail": null` and rely on the fallback/placeholder chain.

## Existing Code to Leverage

**`web/start.html` catalog card structure (lines 206-282)**
- Four `<article>` elements with `.thumb` image areas and `<a class="cover">` overlay links.
- Each card image has an `onerror` fallback that creates an `.img-placeholder` div when the image 404s.
- The cover link URLs (`order.html?product=print`, `report.html`, etc.) define where each card's CTA navigates.

**`web/gallery.html` renderer (lines 200-240)**
- JavaScript builds DOM from `web/data/gallery.json` sections and entries.
- Already has a null-thumbnail branch that shows "Preview coming soon" -- extend this with the convention-based fallback path before falling through to the placeholder.

**`tests/e2e/tests/01-landing.spec.js`**
- `trackErrors(page)` helper excludes "Failed to load resource" console messages (lines 21-31).
- `CATALOG` constant in `tests/e2e/helpers.js` maps card names to expected destination URLs -- reuse for lightbox CTA verification.
- Lines 102-115 test card-click navigation -- must be updated for lightbox behavior.

**`tests/e2e/helpers.js` CATALOG constant**
- Maps `{ endpoint, card, page }` for all four catalog cards. The `page` field provides the expected order URL for each card -- use this to verify lightbox CTA targets.

## Rights & Determinism Notes

- No new data sources. All images are existing project renders from USGS public-domain data.
- No pipeline output changes. The 2D default render remains byte-identical.

## Out of Scope

- Deleting or modifying `web/studio.html` itself.
- Adding npm dependencies or a build step to `web/`.
- Any `src/` pipeline changes or `PIPELINE_STAGES` modifications.
- Running `tools/catalog.py ingest` or generating new thumbnails via PIL -- only existing render output is referenced.
- Adding lightbox/modal to pages other than `start.html`.
- Gallery pagination, filtering, or search.
- Generating missing gallery renders for entries other than `conus-neon-hero`.
- Changes to `web/proof.html`.
- Changes to the offline pytest suite (no `src/` changes, so no new unit tests needed).
- Image optimization or WebP conversion for gallery thumbnails.
