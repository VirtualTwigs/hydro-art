# Implementation Report — Report Builder with Paywall Preview

**Date:** 2026-09-21
**Epoch:** 32 · Items #142–#143

## Summary

Redesigned `web/report.html` from a single-panel full-access sample report into a
two-panel report builder with a paywall boundary. Added URL-param pre-fill to
`web/order.html` so the report builder → order handoff works end-to-end.

## Changes

### `web/report.html` — complete rewrite

**Layout:** Two-panel grid — 360px config sidebar + fluid preview panel. Responsive
breakpoint at 780px collapses to single column.

**Config panel (left):**
- Location picker: state/county/basin scope buttons with cascading selects
- Report options: year range (1970–2023), custom title input
- Section toggles: 9 toggle switches (tiles, long record, typical year, ENSO, regime, analogs, records, FDC, composites) controlling visibility via `data-section`/`data-section-id` attribute pairing
- Delivery format: PDF/Print/Web button group
- Preview + Order buttons

**Preview panel (right):**
- Empty state until first preview
- "Preview only — sample data" badge
- Full report sections render from `buildSeededReport` (deterministic, seed from location)
- Lower sections (regime through composites) wrapped in `.paywall-fade` with CSS gradient
- Paywall CTA: "Unlock the full report" + price ($95+) + order button

**Deep-link:** URL params `?state=X&county=Y` or `?state=X&basin=Z` auto-populate the picker and generate a preview on page load.

### `web/order.html` — URL param pre-fill

Added pre-fill logic at the end of the IIFE:
- Reads `product`, `region`, `county` from URL params
- Pre-selects product type and marks it visually
- Sets state and county in the location step
- Auto-advances to step 2 (location) when params present

## Testing

| Test | Result |
|------|--------|
| `pytest -q` (1151 tests) | Pass |
| `node tests/test_recipe_roundtrip.cjs` | Pass (11/11) |
| Report page serves (HTTP 200) | Pass |
| Order page serves (HTTP 200) | Pass |

## Deferred

- E2E Playwright tests for report builder (#144) — needs Node 18+ and running server
- Manual responsive/visual smoke — needs browser
