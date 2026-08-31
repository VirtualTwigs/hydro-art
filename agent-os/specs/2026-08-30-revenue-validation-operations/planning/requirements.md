# Requirements — Revenue Validation operations (roadmap #56, #57-ops, #58, #59)

## Problem

Epoch 11.5 is a **sequencing correction, not a technical epoch**
(`agent-os/product/revenue-validation-amendment.md`): prove a buyer will pay for a
county watershed print **before** the product surface expands. The **code core** of
the fulfillment recipe already landed — `src/fulfillment.py` (order validation, the
PRISM-free Rights gate, deterministic deliverable plan + byte-reproducible manifest;
29 offline tests) and the non-offline `tools/fulfill_order.py` executor, specced in
`agent-os/specs/2026-08-30-order-fulfillment/` with two approved art directions in its
`presets.md`.

What is **not** yet specced is the **operational track** — the non-code work that
actually runs the experiment:

- **#56 Narrow made-to-order listing** — no marketplace listing exists; nothing is
  actually for sale.
- **#57 fulfillment pack (operational half)** — the code core produces the assets, but
  the *operating recipe* around it is missing: a customer intake form, the title/subtitle
  house rules (partly encoded in `src/fulfillment.py` defaults), an export/QA checklist,
  the source-credit/attribution line (produced by `attribution_line`), and a
  proof/approval template.
- **#58 Instrument the test** — `agent-os/product/revenue-ledger.md` is scaffolded
  (funnel table, order ledger, demand tally, monthly-decision section) but has no
  operating procedure tying order events to ledger updates.
- **#59 Revenue gate** — the gate criteria live in the ledger; there is no defined
  decision procedure for when 60 days elapse.

## Scope (this spec)

The **operational plan + artifacts** that turn the shipped fulfillment code into a live,
measured commercial experiment (roadmap Epoch 11.5, items #56, the operational half of
#57, #58, #59). This is an **operating recipe, not code** — it adds no `src/` capability,
no `PIPELINE_STAGES` change, and no test-suite change. Deliverables are documents and a
marketplace listing, plus reuse of the existing `tools/fulfill_order.py` path.

- **#56** — publish one Etsy (or equivalent) made-to-order listing for a personalized
  county watershed print in OR/WA/CA/ID: print-ready PDF/PNG in 24–48 h; editable SVG +
  commercial license as paid add-ons. Sell a service, not a platform.
- **#57-ops** — author the fulfillment pack: intake form, title/subtitle rules, an
  export/QA checklist, the attribution line, and a proof/approval template.
- **#58** — a written procedure for logging every listing event and order into
  `revenue-ledger.md` (views, favorites, inquiries, paid orders, fulfillment time, refund
  rate, requested locations/styles, net revenue after fees).
- **#59** — the gate decision procedure: at 60 days (or on hitting a threshold early),
  evaluate ≥ 8 paid orders **or** ≥ $500 gross **and** median fulfillment < 45 min →
  proceed; else interview 10 non-buyers, revise, run one further test.

## Constraints (carried from the project)

- **Rights gate (public-domain only).** Sell **only** public-domain-sourced art (USGS
  NHDPlus HR / NHD / WBD). The two approved directions (`neon-basin`, `elevation-tint`)
  are PRISM-free (`uses_prism=False`); `assert_sellable` refuses anything else. **No
  PRISM-derived asset ships commercially** until written PRISM licensing is documented.
  Every sold asset carries the `attribution_line` USGS source credit.
- **Reproducible fulfillment.** Each order is fulfilled via `tools/fulfill_order.py`
  (`build_order` → deliverable plan → byte-reproducible manifest under
  `output/orders/<order_id>/`), so a re-order regenerates identical files.
- **No new product surface.** No catalog/POD, self-serve storefront, subscriptions, or
  region expansion (Utah #47) until the #59 gate passes — that is the whole point of the
  gate. Existing OR/WA/CA/ID scope is enough to validate demand.
- **No code / test changes.** This track touches only `agent-os/` docs + external
  marketplace state. The offline suite and 2D default output are untouched by definition.

## Non-goals

- Any change to `src/`, `tools/` (beyond running the existing executor), `PIPELINE_STAGES`,
  or the offline suite.
- Building the `elevation-tint` (`mono`) executor dispatch — deferred; the near-term
  listing sells the wired `neon-basin` direction (the `mono` path fails fast today).
- A storefront, POD catalog, subscriptions, or marketing automation.
- Pricing research prose — market-review links/benchmarks live in `market-analysis/`,
  not here.

## Acceptance

- A live made-to-order listing exists for a county watershed print (OR/WA/CA/ID), with
  a 24–48 h delivery promise and SVG/commercial-license add-ons; listing copy + image set
  recorded in the spec folder.
- A fulfillment pack exists: intake form, title/subtitle rules, export/QA checklist,
  attribution line, and proof/approval template — each an artifact under this spec dir.
- A written instrumentation procedure maps each funnel/order event to a
  `revenue-ledger.md` update; the ledger's tables are the single source of truth.
- A written gate procedure evaluates #59's thresholds at 60 days and records the
  continue / iterate / stop decision in the ledger's monthly-decision section.
- Rights gate honored: only PRISM-free public-domain art is listed/sold; attribution is
  stamped on every deliverable.
