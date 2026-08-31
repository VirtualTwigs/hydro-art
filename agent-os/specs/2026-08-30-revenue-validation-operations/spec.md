# Spec — Revenue Validation operations (roadmap #56, #57-ops, #58, #59)

The operational recipe that runs the Epoch 11.5 revenue experiment on top of the
already-shipped fulfillment code (`src/fulfillment.py` + `tools/fulfill_order.py`,
spec `agent-os/specs/2026-08-30-order-fulfillment/`). **No code, no `src/`
capability, no `PIPELINE_STAGES` change** — deliverables are documents, a
marketplace listing, and disciplined use of the existing executor + ledger.

Grouped by roadmap item. All artifacts named below live under this spec dir
(`fulfillment-pack/…`) unless they already exist elsewhere (the code core, the
ledger, the presets). Their closeout is the live listing + first fulfilled orders,
not a test.

## #56 — Narrow made-to-order listing

Publish **one** marketplace listing (Etsy or equivalent) — a service, not a platform.

- **Offer**: a personalized **county watershed print** in the supported geography
  (OR/WA/CA/ID), flagship style `neon-basin` (the only county path wired in
  `tools/fulfill_order.py` today; `elevation-tint` is listed as a future direction but
  its executor dispatch isn't wired — do not sell it yet).
- **Fulfillment promise**: print-ready **PDF/PNG in 24–48 h**; **editable SVG** and
  **commercial license** as paid **add-ons** (the `ADD_ONS` in `src/fulfillment.py`).
- **Sizes**: the catalog `SIZES` (300 DPI portrait) — `12x16`, `18x24`, `24x36`.
- **Deliverable**: `fulfillment-pack/listing.md` — the listing title, description,
  size/format/add-on options, the 24–48 h promise, the public-domain source note +
  attribution statement, and the image set used (sample renders produced via
  `tools/fulfill_order.py` on a sample county, e.g. the Clark County, WA smoke).
- **Rights**: list only PRISM-free public-domain art; the attribution line is part of
  every delivered asset (see #57).

## #57 — Repeatable fulfillment pack (operational half)

The operating recipe around the code core. Author each as an artifact:

- **`fulfillment-pack/intake-form.md`** — the buyer intake the listing links to:
  region (OR/WA/CA/ID) + county, style (`neon-basin`), size, formats, add-ons
  (SVG / commercial license), optional custom title/subtitle, buyer reference. These map
  1:1 onto the `tools/fulfill_order.py` order JSON fields (`region`/`county`/`style`/
  `size`/`formats`/`add_ons`/`title`/`subtitle`/`buyer_ref`) so intake → `order.json` is
  mechanical. Validation mirrors the boundary allowlists in `src/fulfillment.py`
  (`build_order`).
- **Title/subtitle rules** — document the defaults already encoded in `src/fulfillment.py`
  (`"<County> County Watersheds"` / `"<Region> · Hydrographic river network"`,
  whitespace-collapsed, capped 60 / 80 chars) plus the house style for custom text.
- **`fulfillment-pack/export-checklist.md`** — the per-order QA checklist:
  run `python tools/fulfill_order.py --order <order_id>.json`; confirm the deliverable
  plan + manifest in `output/orders/<order_id>/`; verify the title block stamped
  correctly; verify the attribution line is present; spot-check the print at 100%;
  confirm the aspect caveat (the rasterized print takes the county's natural aspect at
  the ordered width, per the HANDOFF executor note); re-run once to confirm the manifest
  sha is byte-identical (the `SOURCE_DATE_EPOCH=0` reproducibility guarantee).
- **Attribution line** — the deterministic USGS source credit from
  `fulfillment.attribution_line` (`DEFAULT_SOURCES`), stamped on every sold asset;
  record the exact string in the pack so it's auditable.
- **`fulfillment-pack/proof-template.md`** — the customer proof/approval message:
  what to send for approval (a watermarked/low-res proof), the approval ask, and the
  revision policy, before releasing the final files.

The two approved art directions already live in the order-fulfillment spec's
`presets.md` — reference it, don't duplicate.

## #58 — Instrument the test

A written procedure, not new tooling — `agent-os/product/revenue-ledger.md` is already
scaffolded (funnel snapshot, order ledger, demand tally, monthly-decision section).

- **`fulfillment-pack/instrumentation.md`** — the operating procedure:
  - **Weekly**: update the funnel snapshot (listing views, favorites, inquiries) from
    marketplace analytics.
  - **Per order**: append a row to the order ledger (date, location requested, style,
    add-ons, gross, fees, net, **fulfillment time** measured from order to files-sent,
    refund?, notes) and tally the requested location/style in the demand table.
  - **Per inquiry that doesn't convert**: note the requested location/style (demand
    signal) even without a sale.
  - Net revenue = gross − marketplace − payment fees; median fulfillment time is
    computed across the order ledger.
- The ledger tables remain the single source of truth; this artifact just defines *when
  and how* they're updated so the #59 gate reads clean data, not impressions.

## #59 — Revenue gate

The decision procedure over the instrumented data.

- **`fulfillment-pack/gate.md`** (or a monthly-decision entry) — evaluate at 60 days
  from listing (or earlier if a threshold is clearly hit):
  - **Proceed** to catalog/POD + self-serve **only if** ≥ 8 paid orders **or** ≥ $500
    gross within 60 days **and** median fulfillment < 45 min.
  - **Otherwise**: interview 10 non-buyers, revise the visual/offer, run **one** further
    test. Do **not** build subscriptions or expand region scope (Utah #47).
  - Record the verdict (continue / iterate / gate passed / stop) in the ledger's
    monthly-decision section, with the observed numbers.
- Downstream unlocks gated on a **pass**: catalog/POD, self-serve, Utah #47, and Epoch 12
  commercialization.

## Determinism & rights (carried invariants)

- **Reproducible re-order**: every order goes through `tools/fulfill_order.py`, whose
  manifest is byte-identical on re-run (`SOURCE_DATE_EPOCH=0` pins the PDF CreationDate) —
  a sold print can be regenerated exactly.
- **Public-domain only**: `assert_sellable` refuses any `uses_prism` style; only
  `neon-basin`/`elevation-tint` (PRISM-free) are sellable, and the near-term listing sells
  only the wired `neon-basin`. Attribution is stamped on every asset.
- **No code/test impact**: this track changes only `agent-os/` docs + external
  marketplace state; the offline suite and 2D default output are untouched.

## Out of scope (deferred until the gate passes)

- The `elevation-tint` (`mono`) executor dispatch (a small future code slice, not this
  track).
- Catalog/POD, self-serve storefront, subscriptions, region expansion (Utah #47).
- Any PRISM-derived product (report/animation) — blocked by the Rights gate regardless of
  revenue.
