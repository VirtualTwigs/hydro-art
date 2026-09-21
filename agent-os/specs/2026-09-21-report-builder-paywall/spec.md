# Spec — Report Builder with Paywall Preview

**Epoch 32 · Items #142–#145**
**Date:** 2026-09-21
**Status:** Prototype implemented, pending formal tests

---

## Overview

Redesign `web/report.html` from a full-access sample report into a two-panel report
builder with a paywall boundary. Left panel: location picker + report customization
options. Right panel: live-updating preview with the lower half faded behind a purchase
CTA. The goal is to convert interest into orders — show enough analytical value to
demonstrate the product, then gate the full report behind payment.

## Architecture

### Page layout

```
+------------------+--------------------------------------------+
| Config Panel     | Preview Panel                              |
| (360px sidebar)  | (fluid, max 800px)                         |
|                  |                                            |
| [Location]       | [Preview badge: sample data]               |
|  scope buttons   | [Report header: name + place + range]      |
|  state select    | [Headline tiles: peak, low, timing, valid] |
|  county/basin    | [Long record sparkline]                    |
|                  | [Typical year + ENSO charts]               |
| [Report Options] |                                            |
|  year range      | ~~~ gradient fade ~~~                      |
|  custom title    | [Regime + Analogs — partially visible]     |
|                  | [Records + FDC + Composites — hidden]      |
| [Sections]       |                                            |
|  9 toggles       | [Paywall CTA]                              |
|                  |  "Unlock the full report"                  |
| [Format]         |  "Order this report" button                |
|  PDF/Print/Web   |  "From $95 · PDF delivered by email"       |
|                  |                                            |
| [Preview report] |                                            |
| [Order this →]   |                                            |
+------------------+--------------------------------------------+
```

### Data flow

1. User selects location (state → county or basin) in left panel
2. "Preview report" button enables when location is complete
3. Click generates a `buildSeededReport(seed, name, place)` using `UX.hash()` + `UX.mulberry32()` — deterministic, same selection → same preview
4. Preview renders in right panel; headline tiles + first charts show clearly
5. Lower sections (regime, analogs, records, FDC, composites) render inside a `.paywall-fade` div with CSS gradient overlay
6. Paywall CTA appears below the fade with "Order this report" linking to `order.html?product=watershed-report&region=...&county=...&format=...`

### Section toggles

Nine toggle switches in the sidebar control visibility of report sections via `data-section` / `data-section-id` attribute pairing:

| Toggle | Section ID | Content |
|--------|-----------|---------|
| Headline metrics | `tiles` | Peak, summer low, timing tiles + validation badge |
| Long record | `long` | Annual peak trend sparkline |
| Typical year | `typical` | Monthly climatology chart |
| ENSO drivers | `enso` | ONI vs. peak flow |
| Snow vs. rain | `regime` | Snowmelt fraction + drift |
| Analog years | `analogs` | Correlation-ranked historical years |
| Record book | `records` | Driest summers + wettest years |
| Flow-duration | `fdc` | Exceedance by decade |
| Climate composites | `composites` | Warm/neutral/cool hydrographs |

Toggling off a section adds `.section-hidden` (`display: none !important`) to matching elements. State persists within the session (no localStorage).

### Deep-link support

URL parameters auto-populate the picker and generate a preview on page load:
- `?state=Washington` → selects state, scope=state
- `?state=Washington&county=Clark` → selects state + county, scope=county
- `?state=Washington&basin=1708` → selects state + basin, scope=basin

### Order handoff

Both "Order this report" buttons (sidebar + paywall CTA) navigate to:
```
order.html?product=watershed-report&region={state}&county={county}&basin={basin}&format={format}
```

Order form pre-fill (P1) reads these params to skip steps 1–2.

## Files changed

| File | Change |
|------|--------|
| `web/report.html` | Complete rewrite: two-panel layout, config sidebar, paywall fade, order CTAs |

## Files NOT changed

- `web/shared/hydro-ux.js` — no modifications needed
- `web/shared/ux.css` — all new styles are inline in `report.html`
- `web/order.html` — order form pre-fill is P1 (not this prototype)
- No Python/backend changes

## Testing strategy

1. **Recipe roundtrip** — `node tests/test_recipe_roundtrip.cjs` (no hydro-ux.js changes, should stay green)
2. **Manual smoke** — load `report.html`, select state/county, verify preview, verify paywall fade, verify order link params
3. **Deep-link** — load `report.html?state=Washington&county=Clark`, verify auto-preview
4. **Responsive** — verify layout collapses to single-column below 780px
5. **E2E extension** (P1) — extend `tests/e2e/tests/01-landing.spec.js` to cover report builder navigation

## Risks and mitigations

| Risk | Mitigation |
|------|-----------|
| Paywall gradient is too aggressive, hides value | Gradient starts after 4 visible sections — enough to demonstrate depth |
| Sample data doesn't match real report shape | `buildSeededReport` mirrors the exact `flow_metrics.py` output schema |
| Order form doesn't read URL params yet | Graceful degradation — form loads at step 1, user re-selects |
