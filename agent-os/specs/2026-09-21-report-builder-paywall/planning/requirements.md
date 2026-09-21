# Requirements — Report Builder with Paywall Preview

## Problem

The watershed report page (`web/report.html`) generates a full sample report instantly,
giving away all the analytical value before any purchase. There's no paywall boundary
and no clear path from "see what you'd get" to "pay for the real thing."

## User story

As a potential buyer, I want to configure a watershed report (location, date range,
sections, delivery format), see a convincing preview of what I'll receive, and then
pay to unlock the real gauge-calibrated report — so I understand the value before
committing.

## Requirements

### Must have (P0)

1. **Location picker** — state / county / water-basin (HUC4) scope selector with
   cascading dropdowns populated from `hydro-ux.js` data.
2. **Custom options** — adjustable analysis period (start/end year), optional custom
   title, section toggles (9 report sections individually hideable), delivery format
   (PDF / print / web).
3. **Live preview** — right-panel preview updates as options change; uses deterministic
   sample data seeded by location (not real gauge data).
4. **Paywall boundary** — preview shows headline metrics + first few chart sections
   clearly; remaining sections fade behind a gradient overlay with "Unlock the full
   report" CTA and price ($95+).
5. **Order handoff** — "Order this report" buttons pass product type, region, county/basin,
   and format as URL params to `order.html`.
6. **Deep-link support** — URL params (`?state=X&county=Y`) auto-populate picker and
   generate preview on page load.

### Should have (P1)

7. **Order form pre-fill** — `order.html` reads URL params and pre-selects product type
   and location from query string.
8. **Section toggle persistence** — toggled-off sections stay hidden across re-renders
   within the session.

### Won't have (this epoch)

- Real gauge data in preview (always sample data).
- Stripe payment integration (handled by Epoch 29 payment infrastructure).
- Account/login (email-only identity per existing policy).
- Server-side report generation (preview is client-side only).

## Acceptance criteria

- Selecting a state, scope, and sub-location enables the preview button.
- Preview renders in the right panel with sample data matching the seed.
- Changing title or year range live-updates the preview.
- Lower report sections are visually faded with a gradient and paywall CTA.
- "Order this report" navigates to `order.html` with correct query params.
- Deep-link with `?state=Washington&county=Clark` loads and previews automatically.
- All section toggles show/hide their corresponding report sections.
- Recipe roundtrip test (`node tests/test_recipe_roundtrip.cjs`) stays green.
- No changes to `hydro-ux.js` or `ux.css` (page is self-contained with inline styles).
