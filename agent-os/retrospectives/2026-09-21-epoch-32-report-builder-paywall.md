# Epoch 32 Retrospective — Report Builder with Paywall Preview

**Date:** 2026-09-21
**Items:** #142–#145
**Suite at close:** 1151 passed

## What shipped

Redesigned `web/report.html` from a single-panel sample report into a two-panel report
builder with a paywall boundary. A 360px config sidebar (state/county/basin picker, year
range, 10 section toggles, delivery format) drives a live-updating preview in the main
panel. Lower sections fade behind a CSS gradient with an "Unlock the full report" CTA at
$95+, linking directly to the order form. A curated facility listing (~130 facilities
across ~30 HUC4 basins) surfaces data-center and water-infrastructure context.

`web/order.html` gained URL-param pre-fill and product alias normalization so the handoff
from the report builder (and from `start.html`) skips already-answered steps. A 12-issue
UX audit fixed shipping validation, back-button state, and email pre-fill from proof
return. 25 Playwright e2e tests cover picker, preview, paywall, facilities, order handoff,
deep-link, and responsive layout.

## What went well

- **Seeded preview is convincing.** Deterministic sample data from `buildSeededReport`
  gives the buyer a realistic feel without exposing real gauge-calibrated data.
- **Facility listing adds differentiation.** The curated registry per HUC4 makes the
  report feel tangible — "your basin has 3 data centers and 2 water treatment plants."
- **Handoff is seamless.** URL params + alias normalization + auto-advance mean the buyer
  goes from preview → order form step 3/4 in one click.

## What to watch

- **Facility data is hand-curated.** The ~130-entry registry is a snapshot; Epoch 27's
  water-facility intelligence database would replace it with live, provenance-tracked data.
- **No `src/` changes.** The report builder is entirely in `web/report.html` — no new
  offline-testable modules. The Playwright e2e tests are the quality gate.
