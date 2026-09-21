# Implementation Report — Report Builder with Paywall Preview

**Date:** 2026-09-21
**Epoch:** 32 · Items #142–#145
**Status:** Complete

## Summary

Redesigned `web/report.html` from a single-panel full-access sample report into a
two-panel report builder with paywall boundary, facility listing, and end-to-end
order handoff. Deep UX audit fixed 12 cross-page issues. 25 Playwright e2e tests
cover the full flow.

## Deliverables

### #142 — Report builder prototype

**`web/report.html`** — complete rewrite.

- **Two-panel layout:** 360px config sidebar + fluid preview panel, responsive at 780px.
- **Location picker:** state/county/basin scope buttons with cascading selects from `hydro-ux.js`.
- **Report options:** year range (1970–2023), custom title, 10 section toggles, delivery format (PDF/Print/Web).
- **Live preview:** `buildSeededReport` generates deterministic sample data seeded by location; re-renders on title/year changes.
- **Paywall boundary:** CSS gradient fade on lower sections (regime through composites) with "Unlock the full report" CTA, $95+ price, order button.
- **Facility listing:** curated registry of ~130 facilities across ~30 HUC4 basins (data centers, water treatment, dams, intakes, reservoirs, springs). Lookup works for all three scopes (state aggregates all basins, county filters by name, basin is direct key).
- **Deep-link:** `?state=X&county=Y` or `?state=X&basin=Z` auto-populates picker, syncs scope buttons, generates preview.

### #143 — Order form pre-fill + UX audit

**`web/order.html`** — URL param pre-fill and 12-issue fix.

- Reads `product`, `region`, `county`, `style`, `title`, `email` from URL params.
- Auto-advances past completed steps: product+location → step 3 (style); product+location+style → step 4 (details).
- Product alias normalization: `print`→`fine-art-print`, `digital`→`digital-image`, `animation`→`year-in-motion`, `report`→`watershed-report`. Backward-compatible with existing `start.html` links.
- Shipping address validation for print orders (required fields check with error message).
- Back-button re-enables Continue on step 2.
- Email pre-fill from proof.html return flow.

### #144 — E2E test coverage

**`tests/e2e/tests/03-report-builder.spec.js`** — 25 Playwright tests across 8 describe blocks:

| Block | Count | Coverage |
|-------|-------|----------|
| Report builder | 8 | Load, empty state, picker, scope, preview, title, year range, determinism |
| Paywall boundary | 2 | CTA + price, fade overlay |
| Section toggles | 2 | Toggle on/off, 10 toggles present |
| Facility listing | 3 | Known basin, empty basin, county filtering |
| Order handoff | 2 | Both buttons, URL params |
| Order form pre-fill | 5 | Skip-to-style, alias normalization, title, email |
| Deep-link | 3 | County, basin + scope sync, state-only guard |
| Responsive | 1 | Single-column at 600px |

### #145 — Close

- `pytest -q`: 1151 passed
- `node tests/test_recipe_roundtrip.cjs`: 11/11 passed
- No `hydro-ux.js` or `ux.css` changes (page self-contained)
- `PIPELINE_STAGES` untouched

## Files changed

| File | Change |
|------|--------|
| `web/report.html` | Complete rewrite — two-panel layout, paywall, facilities |
| `web/order.html` | URL param pre-fill, alias normalization, shipping validation |
| `tests/e2e/tests/03-report-builder.spec.js` | New — 25 e2e tests |
| `agent-os/product/roadmap.md` | Epoch 32 items #142–#145 |
| `agent-os/specs/2026-09-21-report-builder-paywall/*` | Requirements, spec, tasks, report |

## Commits

1. `feat(#142)`: Report builder prototype with paywall preview
2. `feat(#143)`: Order form URL pre-fill from report builder handoff
3. `feat(#142)`: Facility listing in report builder preview
4. `fix(#142)`: Order handoff skips pre-filled steps, product alias normalization
5. `docs`: Roadmap update — tick #142 facilities, #143 pre-fill + UX fixes
6. `test(#144)`: E2E Playwright suite for report builder and order handoff
7. `docs(#145)`: Epoch 32 close — implementation report, tasks complete
