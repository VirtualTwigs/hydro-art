# Requirements — Riverglyph brand transition (Epoch 31, roadmap #137–#141)

## Problem

The product is nearing its first commercial listing (Epoch 11.5) but still presents
publicly as **Hydro-Art** — an internal project name, not a product brand. The approved
public identity is **Riverglyph**, with a selected mark (**Tideline E / Long Shore** R/g
monogram), a defined palette (**River Teal `#176C70`**, Watershed Ink `#142923`, Field
Paper `#F4F2E9`**), and a wordmark in serif type. The identity review (`web/riverglyph.html`)
is complete; implementation has not started.

Every public touchpoint — web pages, email, metadata, listing copy — currently carries
`Hydro·Art` or `Hydro◇Art` wordmarks and cyan/violet neon styling. This must transition
to the Riverglyph identity before the Etsy listing (#56) goes live, so customers encounter
one consistent brand from listing → landing → order → proof → payment → delivery.

## Scope

A **presentation and go-to-market migration** — it must not alter the render pipeline,
artifact bytes, API contracts, persisted technical identifiers, or the offline test suite.

### In scope

1. **Brand foundation (#137):** Finalize editable SVG assets for the Tideline E mark
   (horizontal wordmark, stacked lockup, icon-only, black-only print, reversed).
   Favicon/app-icon and social-preview source art. Shared brand-token layer (River Teal,
   Watershed Ink, Field Paper).

2. **Public customer-surface migration (#138):** Update `web/start.html`, `web/order.html`,
   `web/proof.html`, `web/delivery.html`, `web/gallery.html`, and `web/report.html`:
   document titles, visible wordmarks, navigation, description/meta copy, River Teal
   styling. Preserve order/proof/delivery/report behavior.

3. **Studio, operations, and demo migration (#139):** Update `web/shared/ux.css`,
   `web/shared/editorial.css`, `web/studio.html`, `web/ops.html`. Review prototypes
   (`proto-b-guided.html`, `proto-c-canvas.html`) — migrate or remove from navigation.

4. **Transactional, discovery, and measurement migration (#140):** Update email
   subjects/bodies in `src/email_delivery.py`, page metadata, favicon/social-preview
   references, analytics/listing names. Update the landing-page E2E title expectation
   and add a focused visual smoke check. Preserve historical order records.

5. **Launch gate (#141):** Verify domain/trademark clearance; test full public path with
   approved identity; record go-live timestamp in the revenue ledger.

### Out of scope

- `HYDRO_ART_*` environment variables, `hydro-art/*` manifest schemas, Docker/image names,
  and generator metadata — these are compatibility identifiers, unchanged until a separately
  planned technical migration.
- Render pipeline, `PIPELINE_STAGES`, artifact bytes — untouched.
- New features or functional changes — this is identity only.

## Existing brand surface (what changes)

| File | Brand strings to update |
|---|---|
| `web/start.html` | Title `Hydro-Art — rivers, made to order`, `Hydro·Art` logo/footer |
| `web/order.html` | Title `Hydro-Art — Place an Order`, `Hydro◇Art` nav/footer |
| `web/proof.html` | Title `Hydro·Art — Review Your Proof`, `Hydro◇Art` nav |
| `web/delivery.html` | Title `Hydro-Art / Your Order`, `Hydro◇Art` nav, footer note |
| `web/gallery.html` | Title `Hydro-Art · Marketing Gallery`, `Hydro-Art ◇` heading |
| `web/report.html` | Title `Hydro-Art · Watershed Report`, `Hydro-Art ◇` heading |
| `web/studio.html` | Title `Hydro-Art · Studio`, `Hydro-Art ◇ Studio` heading |
| `web/ops.html` | Title `Hydro-Art / Operations`, `Hydro◇Art` nav |
| `web/proto-b-guided.html` | Title + heading `Hydro-Art` branding |
| `web/proto-c-canvas.html` | Title + heading `Hydro-Art` branding |
| `web/shared/ux.css` | `--accent: #00ffff` (cyan), `--accent-2: #9d00ff` (violet) |
| `web/shared/editorial.css` | `--accent: #236c6a` (close but not `#176C70`) |
| `src/email_delivery.py` | 3 email subjects with `Hydro-Art`, HTML `Hydro&#9671;Art` wordmarks |
| `tests/e2e/tests/01-landing.spec.js` | Title regex `/Hydro-Art/i` |

## Existing brand tokens

| Token | Old value | New value |
|---|---|---|
| Primary accent | `#00ffff` (cyan, ux.css) / `#236c6a` (editorial.css) | `#176C70` (River Teal) |
| Secondary accent | `#9d00ff` (violet, ux.css) | Remove or reassign |
| Dark background | `#07080c` (ux.css) | `#142923` (Watershed Ink) |
| Light background | `#f4f2ea` (editorial.css) | `#F4F2E9` (Field Paper) |
| Ink / text | `#182622` (editorial.css) | `#142923` (Watershed Ink) |

## Constraints

- **Offline suite untouched.** No `src/` import changes, no GDAL dependency, no test
  regression. The only `src/` edit is email copy in `src/email_delivery.py`.
- **Byte-identical renders.** The 2D pipeline and all endpoints produce identical output.
- **No new JS dependencies.** Web pages remain build-free, `file://`-safe.
- **Recipe roundtrip.** `tests/test_recipe_roundtrip.cjs` must still pass (it tests
  `web/shared/hydro-ux.js`, which has no brand strings).
- **E2E update.** The Playwright title check in `01-landing.spec.js` must match the
  new title.

## Acceptance

- A customer encounters one consistent Riverglyph identity across all public pages,
  email, proof, and delivery.
- The Tideline E mark is legible in black, River Teal, and reverse.
- The legacy technical contracts (`HYDRO_ART_*`, manifests) remain compatible.
- The offline suite stays green; recipe roundtrip passes.
- The go-live timestamp is recorded in the revenue ledger.
