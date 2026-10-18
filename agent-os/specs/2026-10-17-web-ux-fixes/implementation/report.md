# Implementation Report — Web UX Fixes (2026-10-17)

## Summary

Three customer-facing web UX fixes shipped: catalog card lightbox on start.html,
Studio nav link removal from order.html/ops.html, and gallery thumbnail fallback
in gallery.html. No `src/` pipeline changes; offline suite unaffected.

## Changes

### 1. Catalog card lightbox (start.html)

**`web/start.html`** — Added inline lightbox modal (HTML + CSS + JS):
- Lightbox overlay with close button, full-res image (max 90vw/78vh), and
  "Start design →" CTA linking to the card's order URL.
- `.thumb` elements given `z-index:3` to sit above `.cover` (z-index:2),
  capturing clicks in the image area.
- JS wires each card's `.thumb` click: if a real image is present, opens
  lightbox; if `.img-placeholder` is showing (404 fallback), navigates to
  the order page directly.
- Closes on: close button, backdrop click, Escape key.
- No external dependencies; `file://`-safe.

### 2. Studio nav link removal

**`web/order.html`** — Removed `<a href="studio.html">Studio</a>` from nav.
**`web/ops.html`** — Removed `<a href="studio.html">Studio</a>` from nav.

`web/studio.html` remains in repo (internal tool). `web/proof.html` untouched
(`hello@runde.studio` is an email domain).

### 3. Gallery thumbnail fallback (gallery.html + gallery.json)

**`web/data/gallery.json`** — Set `conus-neon-hero` entry thumbnail to
`/output/gallery/conus-neon-hero/conus-neon-hero.png`. Other entries remain null.

**`web/gallery.html`** — Refactored curated gallery renderer: all entries now
build an `<img>` element. Explicit thumbnails use the provided path; null
thumbnails use convention-based path `/output/gallery/<entry_id>/<entry_id>.png`.
Added `galleryImgFallback` onerror handler that swaps failed images to
"Preview coming soon" placeholder text.

### 4. E2E test updates

**`tests/e2e/tests/01-landing.spec.js`** — Updated from 18 to 24 tests:
- 4 existing card-click tests updated to assert lightbox opens (not navigation)
- New: lightbox CTA href verification (all 4 cards)
- New: lightbox close on Escape
- New: lightbox close on backdrop click
- New: placeholder cards navigate directly (no lightbox)
- 4 cover-link navigation tests preserved (click via card body area)

## Test results

| Suite | Result |
|-------|--------|
| Offline pytest | 1727 passed (3.73s) |
| Recipe roundtrip | 12/12 green |
| E2E landing | 24 passed (10.6s) |

## Files modified

- `web/start.html` — lightbox modal (CSS + HTML + JS)
- `web/order.html` — removed Studio nav link
- `web/ops.html` — removed Studio nav link
- `web/gallery.html` — thumbnail fallback renderer
- `web/data/gallery.json` — conus-neon-hero thumbnail populated
- `tests/e2e/tests/01-landing.spec.js` — 6 new/updated lightbox tests
