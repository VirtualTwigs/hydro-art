# Tasks: Riverglyph Brand Transition (Epoch 31, #137–#141)

Legend: `[x]` done, `[ ]` todo. This epoch is presentation-only — no pipeline
changes, no new `src/` modules, no `PIPELINE_STAGES` edit. The only `src/` edit
is email copy in `src/email_delivery.py` (with matching test assertion updates).
TDD applies where tests exist (email, e2e); HTML/CSS groups verify via recipe
roundtrip + visual inspection.

## Task Group 1 — Brand assets (`web/brand/`) · #137 foundation

Everything else depends on these files existing.

- [x] 1.1 Create `web/brand/` directory. Export the Tideline E / Long Shore mark
  from `web/riverglyph.html` into editable SVG assets:
  - `riverglyph-wordmark.svg` — horizontal wordmark (serif + double-shore underline)
  - `riverglyph-lockup.svg` — stacked lockup (R/g mark above wordmark)
  - `riverglyph-icon.svg` — icon-only R/g monogram
  - `riverglyph-print.svg` — single-color black, no teal (physical print attribution)
  - `riverglyph-reversed.svg` — Field Paper on Watershed Ink
  - `favicon.svg` — R/g monogram, readable at 16x16 / 32x32
- [x] 1.2 Generate `web/favicon.ico` — multi-size ICO (16/32/48) from favicon SVG.
- [x] 1.3 Create `web/brand/social-preview.png` — 1200x630 OG image: wordmark +
  tagline on Field Paper background.
- [x] 1.4 Verify mark legibility: Tideline E readable in black, River Teal, and
  reversed variants at 16px (favicon), 32px (nav), and 200px+ (hero).

**Acceptance:** All 8 asset files exist under `web/brand/` (+ `web/favicon.ico`);
marks are visually legible at target sizes; SVGs are clean, editable, no raster
embedded.

## Task Group 2 — Brand token layer + CSS migration · #137 tokens

Depends on TG1 (brand palette finalized).

- [x] 2.1 Create `web/shared/brand.css` with canonical `:root` tokens:
  `--brand-teal: #176C70`, `--brand-ink: #142923`, `--brand-paper: #F4F2E9`.
- [x] 2.2 Update `web/shared/editorial.css` — import `brand.css`, migrate tokens:
  - `--accent: #236c6a` to `var(--brand-teal)` / `#176C70`
  - `--ink: #182622` to `var(--brand-ink)` / `#142923`
  - `--panel: #f4f2ea` to `var(--brand-paper)` / `#F4F2E9`
  - `--ok: #236c6a` to `var(--brand-teal)` / `#176C70`
- [x] 2.3 Update `web/shared/ux.css` — import `brand.css`, migrate tokens:
  - `--accent: #00ffff` to `#176C70` (River Teal)
  - `--accent-2: #9d00ff` — remove (no secondary accent in Riverglyph)
  - `--accent-dim: #0a8f92` — derive from River Teal (e.g. `#0f4f52`)
  - `--bg: #07080c` to `#142923` (Watershed Ink)
- [x] 2.4 Verify legibility of River Teal on Watershed Ink dark background in
  `studio.html` and `ops.html`. If too low-contrast, introduce `--accent-light`
  derived from River Teal for interactive elements on dark fields.
- [x] 2.5 Run recipe roundtrip: `node tests/test_recipe_roundtrip.cjs` — must pass
  (hydro-ux.js untouched, but CSS imports could break page load).

**Acceptance:** `brand.css` defines tokens once; both theme files reference them;
no hardcoded old hex values remain in `editorial.css` or `ux.css` for the four
migrated tokens; recipe roundtrip green; studio/ops interactive elements legible.

## Task Group 3 — Public customer-surface pages · #138

Depends on TG1 (assets) + TG2 (CSS tokens).

- [x] 3.1 `web/start.html`:
  - Title: `Riverglyph — rivers, made to order`
  - Replace `Hydro·Art` logo span with Riverglyph wordmark (inline SVG or text)
  - Add favicon `<link>` (SVG + ICO), social-preview `<meta property="og:image">`
  - Add/update `<meta name="description">`, `og:title`, `og:description`
- [x] 3.2 `web/order.html`:
  - Title: `Riverglyph — Place an Order`
  - Nav: `Hydro◇Art` to Riverglyph wordmark
  - Footer breadcrumb: `Hydro◇Art / Order` to `Riverglyph / Order`
  - Fix `.brand b { color: var(--cyan); }` to `color: var(--accent)`
  - Add favicon + OG meta tags
- [x] 3.3 `web/proof.html`:
  - Title: `Riverglyph — Review Your Proof`
  - Nav: `Hydro◇Art` to Riverglyph wordmark
  - Same `.brand` color fix
  - Add favicon + OG meta tags
- [x] 3.4 `web/delivery.html`:
  - Title: `Riverglyph — Your Order`
  - Nav: `Hydro◇Art` to Riverglyph wordmark
  - Keep footer: `"Hydrographic artwork produced by Runde Strategies."`
  - Add favicon + OG meta tags
- [x] 3.5 `web/gallery.html`:
  - Title: `Riverglyph · Marketing Gallery`
  - Heading: `Hydro-Art ◇` to `Riverglyph`
  - Keep `"hydro-art/gallery-ledger@1"` schema string unchanged (technical ID)
  - Add favicon + OG meta tags
- [x] 3.6 `web/report.html`:
  - Title: `Riverglyph · Watershed Report`
  - Heading: `Hydro-Art ◇` to `Riverglyph`
  - Add favicon + OG meta tags
- [x] 3.7 Run recipe roundtrip: `node tests/test_recipe_roundtrip.cjs` — green.

**Acceptance:** All 6 public pages show Riverglyph identity in title, nav,
heading; favicon and OG meta present; `hydro-ux.js` untouched; order/proof/
delivery/report behavior unchanged; recipe roundtrip green.

## Task Group 4 — Studio, operations, and prototypes · #139

Depends on TG2 (CSS tokens inherited by ux.css).

- [x] 4.1 `web/studio.html`:
  - Title: `Riverglyph · Studio`
  - Heading: `Hydro-Art ◇ Studio` to `Riverglyph Studio`
- [x] 4.2 `web/ops.html`:
  - Title: `Riverglyph / Operations`
  - Nav: `Hydro◇Art` to Riverglyph
- [x] 4.3 `web/proto-b-guided.html`:
  - Title + heading: migrate `Hydro-Art` to `Riverglyph`
- [x] 4.4 `web/proto-c-canvas.html`:
  - Title + heading: migrate `Hydro-Art` to `Riverglyph`
- [x] 4.5 Visual verification: confirm River Teal on Watershed Ink is legible for
  buttons, borders, focus rings, and interactive highlights in studio and ops.

**Acceptance:** All 4 internal pages show Riverglyph identity; ux.css dark theme
legible for interactive elements.

## Task Group 5 — Email + test assertions · #140 (TDD)

Depends on TG1–TG4 (brand identity settled). This is the only `src/` change.

- [x] 5.1 **Tests first** — update `tests/test_email_delivery.py`:
  - Change assertion strings matching `Hydro-Art` in email subjects to `Riverglyph`
  - Change assertion strings matching `Hydro&#9671;Art` in HTML bodies to `Riverglyph`
  - Run ONLY: `.venv/bin/python -m pytest tests/test_email_delivery.py -q` — expect failures.
- [x] 5.2 Update `src/email_delivery.py`:
  - Subject: `Your Hydro-Art order is complete` to `Your Riverglyph order is complete`
  - Subject: `We received your Hydro-Art request` to `We received your Riverglyph request`
  - HTML bodies: replace `Hydro&#9671;Art` wordmark spans with `Riverglyph`
  - Keep footer: `"Hydrographic artwork produced by Runde Strategies."`
- [x] 5.3 Run ONLY: `.venv/bin/python -m pytest tests/test_email_delivery.py -q` — green.
- [x] 5.4 Update `tests/e2e/tests/01-landing.spec.js`:
  - Title regex: `/Hydro-Art/i` to `/Riverglyph/i`
  - Add visual smoke check: Riverglyph wordmark visible at 1280px and 375px widths.

**Acceptance:** Email tests pass with Riverglyph strings; e2e title regex updated;
no other `src/` or `tests/` files changed; `src/email_delivery.py` has no
remaining `Hydro-Art` brand strings (technical identifiers like env vars excluded).

## Task Group 6 — Full suite regression + recipe roundtrip

Depends on TG1–TG5.

- [x] 6.1 Run full offline suite: `.venv/bin/python -m pytest -q` — all green,
  record pass count (was 1151, now 1151).
- [x] 6.2 Run recipe roundtrip: `node tests/test_recipe_roundtrip.cjs` — green.
- [x] 6.3 Confirm no `PIPELINE_STAGES` edit — 2D default render byte-identical.
  No `src/config.py` allowlist changes, no `Settings` shape changes.
- [x] 6.4 Confirm `tests/` imports no `tools/`; `src/` imports no `web/` or `tools/`.
- [x] 6.5 Confirm `hydro-ux.js` `HydroUX` namespace untouched; `HYDRO_ART_*` env
  vars unchanged; `hydro-art/*` manifest schemas unchanged.

**Acceptance:** Full suite green with no regressions; recipe roundtrip green;
determinism contract intact; dependency direction preserved; technical identifiers
stable.

## Task Group 7 — Launch gate + close out · #141

Depends on TG6.

- [ ] 7.1 Pre-launch checklist: *Deferred — business clearance (domain registration,
  trademark clearance, full public-path walkthrough) is external, not code.*
  - Domain clearance (`riverglyph.com` available/registered)
  - Trademark clearance (no conflicts in Class 16 / Class 9)
  - Full public-path walkthrough: landing to order to proof to payment to delivery
  - Mark legibility at 16px, 32px, 200px+ in all variants
- [x] 7.2 Update `fulfillment-pack/listing.md` — already uses Riverglyph (updated
  during Epoch 11.5 fulfillment-pack work).
- [ ] 7.3 Record go-live date in `agent-os/product/revenue-ledger.md` — *Deferred:
  record when listing actually publishes (blocked on 7.1 business clearance).*
- [x] 7.4 Update `HANDOFF.md` — noted Epoch 31 completion.
- [x] 7.5 Docs sweep: roadmap items #137–#141 ticked with evidence notes; Epoch 31
  moved to completed section. `CLAUDE.md` module map unaffected (no `src/` shape
  change). `AGENTS.md` consistent.
- [x] 7.6 Write `implementation/report.md`.
- [x] 7.7 Write epoch retrospective in `agent-os/retrospectives/`.

**Acceptance:** Pre-launch checklist complete; listing updated; go-live date
recorded; HANDOFF.md current; full suite + recipe roundtrip confirmed green;
retrospective written.

## Execution Order

1. TG1 — Brand assets (everything depends on these)
2. TG2 — CSS token layer + migration (pages inherit changes)
3. TG3 + TG4 — Page migrations (can parallelize; TG3 = customer-facing, TG4 = internal)
4. TG5 — Email + test assertions (TDD: tests first, then implementation)
5. TG6 — Full suite regression
6. TG7 — Launch gate + close out
