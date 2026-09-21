# Tasks — Report Builder with Paywall Preview

**Spec:** `agent-os/specs/2026-09-21-report-builder-paywall/spec.md`
**Epoch:** 32 · Items #142–#145

---

## Phase 1: Prototype (report builder UI + paywall)

- [x] 1.1 Rewrite `web/report.html` — two-panel layout (360px config sidebar + fluid preview panel)
- [x] 1.2 Location picker — state/county/basin scope buttons with cascading selects from `hydro-ux.js`
- [x] 1.3 Report options — year range selectors, custom title input
- [x] 1.4 Section toggles — 9 toggle switches controlling report section visibility
- [x] 1.5 Delivery format — PDF/Print/Web button group
- [x] 1.6 Live preview — `buildSeededReport` generates deterministic sample in right panel
- [x] 1.7 Paywall fade — CSS gradient overlay on lower sections + "Unlock the full report" CTA
- [x] 1.8 Order handoff — both order buttons link to `order.html` with query params
- [x] 1.9 Deep-link support — URL params auto-populate picker and generate preview on load
- [x] 1.10 Responsive breakpoint — single-column layout below 780px

## Phase 2: Verification

- [x] 2.1 Recipe roundtrip test — `node tests/test_recipe_roundtrip.cjs` stays green
- [ ] 2.2 Manual smoke test — load report builder, select location, verify preview + paywall + order link
- [ ] 2.3 Deep-link smoke — `report.html?state=Washington&county=Clark` auto-previews
- [ ] 2.4 Responsive smoke — verify single-column layout at narrow viewport

## Phase 3: Order form pre-fill (P1)

- [x] 3.1 `order.html` reads `product`, `region`, `county` URL params on load
- [x] 3.2 Auto-advance past product selection to location step when params present
- [x] 3.3 County pre-selected when passed via URL params

## Phase 4: E2E test coverage

- [ ] 4.1 Add report builder navigation to `tests/e2e/tests/01-landing.spec.js`
- [ ] 4.2 Create `tests/e2e/tests/03-report-builder.spec.js` — picker, preview, paywall, order link
- [ ] 4.3 Deep-link e2e test — verify auto-populate from URL params

## Phase 5: Close

- [x] 5.1 Run full offline suite — `pytest -q` all green (1151 passed)
- [x] 5.2 Run recipe roundtrip — `node tests/test_recipe_roundtrip.cjs` green (11/11)
- [x] 5.3 Write `implementation/report.md`
