# Tasks — Web UX Fixes (Lightbox, Studio Link, Gallery Thumbnails)

Legend: `[x]` done · `[ ]` todo. This spec has **no `src/` changes** — all work
is in `web/` HTML/CSS/JS and `tests/e2e/`. E2E tests serve as the "tests-first"
discipline here. The offline pytest suite must stay green (regression only).

## Group 1 — Remove Studio nav link from customer pages · web-only
**Dependencies:** None (smallest, independent change)

- [x] 1.1 Remove `<a href="studio.html">Studio</a>` from `web/order.html` nav
  (line ~397) and `web/ops.html` nav (line ~71). Do NOT touch `web/proof.html`
  or `web/studio.html` itself.
- [x] 1.2 Grep the e2e suite for any assertion on the Studio nav link — update
  if found. Run `node tests/test_recipe_roundtrip.cjs` to confirm no breakage.
- [x] 1.3 Visual spot-check: load `order.html` and `ops.html` in the dev server
  and confirm Studio link is gone; confirm `studio.html` still loads directly.

**Acceptance:** Studio link absent from order.html and ops.html nav; studio.html
still accessible by direct URL; recipe roundtrip green; no proof.html changes.

## Group 2 — Gallery thumbnail fallback + data update · web-only
**Dependencies:** None (independent of Groups 1 and 3)

- [x] 2.1 Update `web/data/gallery.json`: set the `conus-neon-hero` entry's
  `thumbnail` field to `/output/gallery/conus-neon-hero/conus-neon-hero.png`.
  Leave other entries as `"thumbnail": null`.
- [x] 2.2 In `web/gallery.html` renderer (~lines 212-223): when `entry.thumbnail`
  is null, build an `<img>` with convention-based fallback path
  `/output/gallery/<entry_id>/<entry_id>.png` and an `onerror` handler that
  swaps to the existing "Preview coming soon" placeholder (same pattern
  start.html uses for its `.img-placeholder` fallback).
- [x] 2.3 Manual verification: load `gallery.html` in the dev server; confirm
  `conus-neon-hero` shows its thumbnail (or placeholder if NAS not mounted);
  confirm null-thumbnail entries attempt the convention path then fall back
  gracefully to the placeholder text.

**Acceptance:** Gallery entries with explicit thumbnails render them; null-thumbnail
entries try convention path then show placeholder; no JS errors in console.

## Group 3 — Catalog card lightbox on start.html · web + e2e
**Dependencies:** None (can run in parallel with Groups 1-2, but is the largest)

- [x] 3.1 Write e2e tests first in `tests/e2e/tests/01-landing.spec.js`:
  - Update the existing card-click loop (lines 102-115): clicking the `.thumb`
    image area should open a lightbox modal, NOT navigate away. Assert the
    lightbox is visible and contains the card's image.
  - Add test: lightbox displays a "Start design" CTA whose href matches the
    card's original order URL (use `CATALOG[*].page` from helpers.js).
  - Add test: lightbox closes on Escape keypress.
  - Add test: lightbox closes on backdrop click (outside the image).
  - Add test: when artwork is missing (404 placeholder visible), clicking the
    card navigates to the order page (no lightbox for placeholders).
  - Preserve the existing `a.cover` href attribute check (line ~47) — the link
    element still exists, just the click behavior changes for the image area.
  - Target: 5-6 new/updated test assertions.
- [x] 3.2 Implement lightbox in `web/start.html`:
  - Add lightbox HTML overlay (backdrop + image + close button + CTA) — inline,
    no external dependencies, `file://`-safe.
  - Add CSS for the modal (fixed overlay, centered image max 90vw/90vh, close
    button top-right, CTA button below image).
  - Add JS: `.thumb` click opens lightbox with that card's image src and CTA
    href. Close on close-button click, backdrop click, Escape key. Skip lightbox
    (fall through to navigation) when the card shows `.img-placeholder`.
  - Card text area and `a.cover` outside `.thumb` retain existing navigation.
- [x] 3.3 Run ONLY the updated e2e landing tests:
  `cd tests/e2e && npx playwright test tests/01-landing.spec.js`
  Record pass count.

**Acceptance:** Clicking card image opens lightbox with full-res image and CTA;
lightbox closes via close button, backdrop, or Escape; placeholder cards navigate
directly; all landing e2e tests pass; no build step or external deps added.

## Group 4 — Final verification + regression · offline + e2e
**Dependencies:** Groups 1-3

- [x] 4.1 Run full offline pytest suite: `.venv/bin/python -m pytest -q` —
  **1727 passed** in 3.73s, no regressions. **No `PIPELINE_STAGES` edit, so
  2D default render stays byte-identical.**
- [x] 4.2 Run recipe roundtrip: `node tests/test_recipe_roundtrip.cjs` — **12/12 green**.
- [x] 4.3 Run full e2e suite:
  `cd tests/e2e && npx playwright test tests/01-landing.spec.js` — **24 passed** in 10.6s.
- [x] 4.4 Write `implementation/report.md`. HANDOFF.md update deferred to commit.

**Acceptance:** Full offline suite green (count unchanged); recipe roundtrip green;
e2e suite green; all three UX fixes verified in browser.

## Execution Order
1. Groups 1, 2, 3 can execute in parallel (no interdependencies)
2. Group 4 runs after all three are complete (regression + close-out)
