# Tasks — Revenue Validation operations (roadmap #56, #57-ops, #58, #59)

Operational track — **no code, no tests**. Deliverables are documents + a live
listing + measured orders. Closeout is first fulfilled orders and the gate decision,
not a test run. All pack artifacts live under
`agent-os/specs/2026-08-30-revenue-validation-operations/fulfillment-pack/`.

## TG0 — Planning (this commit)
- [x] Confirm Epoch 11.5 code core shipped (`src/fulfillment.py` + `tools/fulfill_order.py`,
      spec `2026-08-30-order-fulfillment/`) and the ledger scaffold exists
      (`agent-os/product/revenue-ledger.md`).
- [x] Write spec artifacts (`planning/requirements.md`, `spec.md`, `tasks.md`).

## TG1 — Fulfillment pack (#57-ops)
- [x] `fulfillment-pack/intake-form.md` — buyer fields mapping 1:1 to the
      `fulfill_order.py` order JSON (region/county/style/size/formats/add_ons/
      title/subtitle/buyer_ref); allowlists mirror `build_order`.
- [x] Document title/subtitle house rules (defaults from `src/fulfillment.py` +
      custom-text style) — in `intake-form.md`.
- [x] `fulfillment-pack/export-checklist.md` — run executor → verify plan/manifest,
      title block, attribution line, print at 100%, aspect caveat, re-run byte-identical.
- [x] Record the exact `attribution_line` string (from `DEFAULT_SOURCES`) —
      `fulfillment-pack/attribution-line.md` (`USGS NHD · USGS NHDPlus HR · USGS WBD`).
- [x] `fulfillment-pack/proof-template.md` — proof message, approval ask, revision policy.
- [ ] Produce sample deliverables via `tools/fulfill_order.py` on a sample county
      (e.g. Clark County, WA) for listing imagery + as a dry run of the pack.
      **(blocked — needs a GDAL host + county GDB, not available in this session)**

## TG2 — Made-to-order listing (#56)
- [x] `fulfillment-pack/listing.md` — title, description, size/format/add-on options,
      24–48 h promise, public-domain source note + attribution, image set.
- [ ] Publish the listing on Etsy (or equivalent); sell only the wired `neon-basin`
      county print in OR/WA/CA/ID; SVG + commercial license as add-ons.
- [x] Rights check: no PRISM-derived art listed; attribution present on every asset.

## TG3 — Instrumentation (#58)
- [x] `fulfillment-pack/instrumentation.md` — the weekly funnel + per-order + per-inquiry
      logging procedure into `revenue-ledger.md`.
- [ ] Begin logging: funnel snapshot weekly; each order → order-ledger row + demand tally;
      non-converting inquiries → demand signal.
      **(blocked — needs live listing)**

## TG4 — Revenue gate (#59)
- [x] `fulfillment-pack/gate.md` — the 60-day evaluation procedure (≥8 orders or ≥$500
      gross **and** median fulfillment <45 min → proceed; else interview 10 non-buyers,
      revise, one further test; no subscriptions / no Utah #47 before a pass).
- [ ] At 60 days (or early threshold): record the continue/iterate/gate-passed/stop
      verdict + observed numbers in the ledger's monthly-decision section.
      **(blocked — needs live listing + 60-day window)**

## Closeout
- [ ] Tick Epoch 11.5 items `[x]` in the roadmap **only** as each operational milestone
      actually lands (listing live; first order fulfilled; gate decided) — not on doc
      authorship alone.
- [ ] On a gate **pass**, unlock the deferred surface (catalog/POD, self-serve, Utah #47,
      Epoch 12 commercialization). On a **fail**, iterate per #59 — do not expand scope.
- [ ] No `implementation/report.md` (no code); the ledger + monthly decision note is the
      record of outcome.
