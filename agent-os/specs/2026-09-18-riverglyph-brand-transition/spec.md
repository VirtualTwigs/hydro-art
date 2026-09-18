# Spec — Riverglyph brand transition (Epoch 31, roadmap #137–#141)

Move the public product identity from **Hydro-Art** to **Riverglyph** using the approved
**Tideline E / Long Shore** R/g mark and **River Teal (`#176C70`)** as the primary digital
accent. This is a presentation and go-to-market migration: it must not alter the render
pipeline, artifact bytes, API contracts, or persisted technical identifiers.

## Scope boundary

**Changes:** public names, visible copy, identity assets, metadata, transactional
communications, and public UI color tokens.

**Unchanged:** `HYDRO_ART_*` environment variables, `hydro-art/*` manifest schemas,
Docker/image names, generator metadata, `HydroUX` JS namespace, `PIPELINE_STAGES`,
rendered artifact bytes. These remain compatibility identifiers until a separately
planned, versioned technical migration.

---

## #137 — Brand foundation

Finalize the editable SVG mark assets derived from the approved Tideline E / Long Shore
direction (`web/riverglyph.html`). These are the source-of-truth identity files that all
pages and emails reference.

### Deliverables

| Asset | File | Notes |
|---|---|---|
| Horizontal wordmark | `web/brand/riverglyph-wordmark.svg` | "Riverglyph" in serif + Tideline E double-shore underline |
| Stacked lockup | `web/brand/riverglyph-lockup.svg` | R/g mark above wordmark, for square contexts |
| Icon-only mark | `web/brand/riverglyph-icon.svg` | Tideline E R/g monogram, no wordmark |
| Black-only print mark | `web/brand/riverglyph-print.svg` | Single-color black, no teal — for physical print attribution |
| Reversed mark | `web/brand/riverglyph-reversed.svg` | Light on dark (Field Paper on Watershed Ink) |
| Favicon | `web/brand/favicon.svg` | R/g monogram, readable at 16×16 / 32×32 |
| Favicon ICO | `web/favicon.ico` | Multi-size ICO generated from SVG (16/32/48) |
| Social preview | `web/brand/social-preview.png` | 1200×630 OG image: wordmark + tagline on Field Paper |

### Brand token layer

Add a shared CSS file `web/shared/brand.css` with the canonical Riverglyph tokens:

```css
:root {
  --brand-teal:  #176C70;   /* River Teal — primary accent */
  --brand-ink:   #142923;   /* Watershed Ink — text / dark field */
  --brand-paper: #F4F2E9;   /* Field Paper — light field */
}
```

This file is imported by both `ux.css` (dark theme) and `editorial.css` (light theme)
so token values are defined once. Each theme maps its own `--accent`, `--bg`, `--ink`
etc. to the brand tokens as appropriate.

### Token migration

| Theme file | Variable | Old value | New value |
|---|---|---|---|
| `editorial.css` | `--accent` | `#236c6a` | `var(--brand-teal)` / `#176C70` |
| `editorial.css` | `--ink` | `#182622` | `var(--brand-ink)` / `#142923` |
| `editorial.css` | `--panel` | `#f4f2ea` | `var(--brand-paper)` / `#F4F2E9` |
| `editorial.css` | `--ok` | `#236c6a` | `var(--brand-teal)` / `#176C70` |
| `ux.css` | `--accent` | `#00ffff` | `#176C70` |
| `ux.css` | `--accent-2` | `#9d00ff` | remove (no secondary accent in Riverglyph) |
| `ux.css` | `--accent-dim` | `#0a8f92` | derive from River Teal (e.g. `#0f4f52`) |
| `ux.css` | `--bg` | `#07080c` | `#142923` (Watershed Ink) |

**Note on `ux.css` dark theme:** The studio/ops dark theme uses `--accent` for
interactive highlights (buttons, borders, focus rings). Changing from cyan to River Teal
is a significant contrast shift on dark backgrounds. The dark `--bg` moves from blue-black
to green-black (Watershed Ink). Verify legibility in `studio.html` and `ops.html` after
the change. If River Teal is too low-contrast on Watershed Ink, introduce a lighter
`--accent-light` derived from River Teal for interactive elements on dark fields.

---

## #138 — Public customer-surface migration

Update the six public-facing pages. Each page needs:

1. **`<title>` tag** — replace `Hydro-Art` with `Riverglyph`.
2. **Visible wordmark** — replace `Hydro·Art` / `Hydro◇Art` with `Riverglyph` (text or
   inline SVG mark from `web/brand/`).
3. **Navigation** — consistent `Riverglyph` wordmark across nav bars.
4. **Meta tags** — add/update `<meta name="description">`, `og:title`, `og:description`,
   `og:image` (social preview), `<link rel="icon">` (favicon).
5. **Footer** — update any brand references; keep `"Produced by Runde Strategies"` note
   (it's the legal entity, not the product brand).
6. **Color** — pages using `editorial.css` pick up the token changes from #137
   automatically; verify River Teal renders correctly in links, buttons, accents.

### Per-page changes

**`web/start.html`** (landing)
- Title: `Riverglyph — rivers, made to order`
- Replace `Hydro·Art` logo span with Riverglyph wordmark (inline SVG or text)
- Add favicon `<link>`, social-preview `<meta property="og:image">`
- Update meta description

**`web/order.html`** (order form)
- Title: `Riverglyph — Place an Order`
- Nav: `Hydro◇Art` → Riverglyph wordmark
- Footer breadcrumb: `Hydro◇Art / Order` → `Riverglyph / Order`
- Replace `.brand b { color: var(--cyan); }` with `color: var(--accent)`

**`web/proof.html`** (proof review)
- Title: `Riverglyph — Review Your Proof`
- Nav: `Hydro◇Art` → Riverglyph wordmark
- Same `.brand` color fix

**`web/delivery.html`** (delivery)
- Title: `Riverglyph — Your Order`
- Nav: `Hydro◇Art` → Riverglyph wordmark
- Footer note stays: `"Hydrographic artwork produced by Runde Strategies."`

**`web/gallery.html`** (marketing gallery)
- Title: `Riverglyph · Marketing Gallery`
- Heading: `Hydro-Art ◇` → `Riverglyph`
- Note: `"hydro-art/gallery-ledger@1"` schema string is a **technical identifier** — do
  not change.

**`web/report.html`** (watershed report)
- Title: `Riverglyph · Watershed Report`
- Heading: `Hydro-Art ◇` → `Riverglyph`

### Behavior preservation

- Order form submission, proof token validation, delivery token validation, report
  rendering — all unchanged. These are functional, not presentational.
- `web/shared/hydro-ux.js` — **not touched**. `HydroUX` is a technical namespace; the
  recipe roundtrip test (`tests/test_recipe_roundtrip.cjs`) must remain green.

---

## #139 — Studio, operations, and demo migration

**`web/studio.html`**
- Title: `Riverglyph · Studio`
- Heading: `Hydro-Art ◇ Studio` → `Riverglyph Studio`
- Picks up `ux.css` token changes from #137

**`web/ops.html`**
- Title: `Riverglyph / Operations`
- Nav: `Hydro◇Art` → Riverglyph
- Picks up `ux.css` token changes

**`web/shared/editorial.css`** — token changes landed in #137; no further edits here.

**`web/shared/ux.css`** — token changes landed in #137; verify studio/ops legibility.

**Prototypes** (`web/proto-b-guided.html`, `web/proto-c-canvas.html`):
- These are internal prototypes. Two options:
  - **Option A (preferred):** Migrate titles/headings to Riverglyph for consistency.
  - **Option B:** Remove from any public navigation links. Keep files but label as archived.
- Decision: migrate (minimal effort — title + heading text only).

---

## #140 — Transactional, discovery, and measurement migration

### Email (`src/email_delivery.py`)

Three email functions contain Hydro-Art branding:

| Email | Subject (old) | Subject (new) |
|---|---|---|
| Order confirmation | `Your Hydro-Art order is complete` | `Your Riverglyph order is complete` |
| Request received | `We received your Hydro-Art request` | `We received your Riverglyph request` |
| Proof ready | `Your proof is ready for review` | _(already brand-neutral — no change)_ |

HTML bodies: replace `Hydro&#9671;Art` wordmark span with `Riverglyph`.
Footer note `"Hydrographic artwork produced by Runde Strategies."` stays (legal entity).

**Test impact:** `tests/test_email_delivery.py` — update any assertions that match on
`Hydro-Art` in subject/body strings. This is the **only `src/` test change**.

### Page metadata

All public pages (#138) get:
- `<link rel="icon" href="brand/favicon.svg" type="image/svg+xml">`
- `<link rel="icon" href="favicon.ico" sizes="any">`
- `<meta property="og:title" content="Riverglyph — ...">`
- `<meta property="og:description" content="...">`
- `<meta property="og:image" content="brand/social-preview.png">`

### E2E test update

`tests/e2e/tests/01-landing.spec.js` line 29:
```js
// Old:
await expect(page).toHaveTitle(/Hydro-Art/i);
// New:
await expect(page).toHaveTitle(/Riverglyph/i);
```

Add a focused visual smoke check: assert the Riverglyph wordmark is visible on the
landing page at desktop (1280px) and mobile (375px) widths. This is a **non-functional
presentation check**, not a full visual regression.

### Analytics / listing names

If Etsy listing analytics reference "Hydro-Art", update the listing title to use
"Riverglyph" — this is handled by #141 (launch gate) and the listing.md update.

### Historical data preservation

- Existing order JSON files in `output/orders/` retain their original `hydro-art` /
  `Hydro-Art` metadata strings. These are persisted records, not live presentation.
- `OrderEvent` history is append-only — no rewriting.

---

## #141 — Riverglyph launch gate

### Pre-launch checklist

- [ ] Domain clearance: confirm `riverglyph.com` (or chosen domain) is available or
      registered. _(Business decision, not code.)_
- [ ] Trademark clearance: confirm no conflicting marks for "Riverglyph" in Class 16
      (prints) / Class 9 (digital). _(Business decision, not code.)_
- [ ] Full public-path walkthrough: landing → order → proof → payment → delivery, with
      the approved Riverglyph identity visible at every step.
- [ ] Mark legibility check: Tideline E mark readable in black, River Teal, and reversed
      variants at 16px (favicon), 32px (nav), and 200px+ (hero).
- [ ] Recipe roundtrip test green: `node tests/test_recipe_roundtrip.cjs` passes.
- [ ] Offline suite green: `.venv/bin/python -m pytest -q` passes with no regressions.
- [ ] E2E landing test green (if Node 18+ available): `npx playwright test tests/01-landing.spec.js`.

### Go-live

- Update `fulfillment-pack/listing.md` to use Riverglyph identity in listing copy.
- Record the **public listing go-live date** in `agent-os/product/revenue-ledger.md` —
  this starts the Epoch 11.5 #59 60-day measurement window.
- Update `HANDOFF.md` to note Epoch 31 completion.

---

## Invariants (must hold after this epoch)

1. **Byte-identical renders.** `build.py` and all `tools/render_*.py` produce the same
   output. No `PIPELINE_STAGES` change, no `Settings` change, no rendering change.
2. **Offline suite green.** Only `tests/test_email_delivery.py` assertions change (brand
   strings in email copy). No new imports, no GDAL dependency.
3. **Recipe roundtrip green.** `hydro-ux.js` is untouched; `HydroUX` namespace stays.
4. **Historical data intact.** No order JSON, event log, or manifest rewriting.
5. **Technical identifiers stable.** `HYDRO_ART_*` env vars, `hydro-art/*` schemas,
   Docker names, `HydroUX` JS namespace — all unchanged.

---

## Out of scope

- Renaming `HydroUX` → `RiverglyphUX` (technical migration, separate epoch).
- Renaming `HYDRO_ART_EXTERNAL_ROOT` env var (infrastructure, separate epoch).
- Renaming the GitHub repo or Python package (if applicable).
- New functional features — this epoch is identity-only.
- Physical print attribution format — the black-only mark is provided (#137) but print
  layout integration is a render-pipeline concern, deferred.
