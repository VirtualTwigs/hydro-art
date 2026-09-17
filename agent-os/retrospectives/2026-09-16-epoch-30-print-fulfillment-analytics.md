# Epoch 30 — Print fulfillment & product analytics retrospective (2026-09-16)

_Closed 2026-09-16 (part of the multi-epoch commit `803f4ae`, roadmap marked
complete in `921b136`); no `planning/pre-analysis.md` — narrative closeout.
Last epoch of the "Self-serve customer journey" generation (Epochs 28-30,
#110-#136). Epoch 30 covers items #132-#136._

## What the epoch was

Close the print-order gap left after Epoch 29 (payment and delivery): once a
customer pays for a physical print, the system needs to (a) capture a shipping
address, (b) forward the print-ready file to a vendor, (c) track fulfillment,
and (d) give the product owner analytics over the event log. Five items:

- #132 Print vendor integration (Printful/Prodigi API)
- #133 Shipping address capture
- #134 Print proof-to-production handoff
- #135 Product analytics dashboard
- #136 Render performance instrumentation

All five items shipped their offline-testable core. The UI wiring and
automation glue (auto-submit on payment, shipping form fields in the order
page, `tools/analytics_report.py` CLI) were explicitly deferred.

## What shipped (`803f4ae`, `921b136`)

### `src/shipping.py` (NEW, 87 lines)

Frozen `ShippingAddress` dataclass with `to_dict` roundtrip. `validate_address`
enforces required fields (name, street, city, state, zip) and US ZIP format
(`^\d{5}(-\d{4})?$`). `ShippingError` for invalid payloads. Pure, stdlib-only,
no GDAL.

### `src/print_vendor.py` (NEW, 107 lines)

`PrintVendorLike` protocol (duck-typed vendor client seam).
`build_print_order_payload` assembles the vendor submission dict.
`submit_print_order` and `check_shipment` delegate to the injected client.
`calculate_print_cost` computes price in cents from size + paper type via
`_PRINT_COSTS` (3 sizes: 12x16/18x24/24x36) and `_PAPER_SURCHARGE` (matte/
glossy/canvas). Vendor SDK is lazy-imported, never at module load.

### `src/analytics.py` (NEW, 91 lines)

`compute_analytics(orders)` -- pure function over a list of order dicts with
event logs. Returns: `orders_by_product`, `orders_by_region`,
`proof_acceptance_rate`, `average_render_time_s`, `payment_conversion_rate`,
`top_counties`, `total_orders`. Counter-based aggregation, no database
dependency.

### `src/orders.py` (EXTENDED)

`OrderStore.add_event` method for recording custom events (render timing,
print submission, fulfillment tracking) with arbitrary detail dicts into the
order's event log. This is the instrumentation hook that feeds the analytics
layer (#136).

### New test files (27 tests total)

| File | Tests | Coverage |
|------|-------|----------|
| `tests/test_shipping.py` | 10 | valid/missing-field/zip-format/zip+4/optional-line2/roundtrip |
| `tests/test_print_fulfillment.py` | 6 | payload/vendor-id/tracking/cost/cost-total |
| `tests/test_print_handoff.py` | 2 | full print cycle with fake vendor, shipping email on fulfillment |
| `tests/test_render_instrumentation.py` | 3 | render_started queue wait, render_completed duration/stages, queue depth |
| `tests/test_analytics.py` | 6 | orders-by-product/region, proof acceptance, avg render time, payment conversion, top counties |

All 27 pass (`0.06s`). Full suite: **1027 passed**, 6 pre-existing failures
(`test_min_order.py` -- feature not yet implemented). Zero regressions.

### Commit totals

Part of the 35-file, 5202-insertion Epochs 28-30 commit (`803f4ae`). Epoch 30
specifically contributed `src/shipping.py`, `src/print_vendor.py`,
`src/analytics.py`, the `add_event` extension to `src/orders.py`, and the five
test files above. Roadmap close: `921b136`.

## Real-data findings

No real-data run in this epoch by design. All three new modules are pure
offline -- they describe contracts and compute over in-memory dicts, not over
GIS data or vendor APIs. The expected pattern (vendor SDK failures, address
validation edge cases against real Printful/Prodigi payloads) would surface
when a live vendor client is wired in `serve.py` and a real print order is
submitted. No bug-the-real-run-surfaced to report here.

## Invariants held

- **Offline suite:** 1027 passed (27 new from this epoch), zero regressions.
- **2D default output byte-identical:** yes. No `PIPELINE_STAGES` change; all
  three new modules are parallel subsystems (fulfillment/analytics), not wired
  into the 12-stage pipeline.
- **`PIPELINE_STAGES` untouched:** yes. The commit adds three `src/` modules
  and extends `src/orders.py` but touches no pipeline module.
- **Rights gate:** N/A for this epoch (print vendor forwarding operates on
  already-rendered, rights-cleared assets; `assert_sellable` is enforced
  upstream by `src/fulfillment.py` and `src/endpoints.py`).

## Graded against pre-analysis

No `planning/pre-analysis.md` exists. The `planning/requirements.md` flagged
three constraints:

1. **Customer pays shipping (not absorbed).** Confirmed: `calculate_print_cost`
   exposes size + paper pricing as a pure function; no cost-absorption logic.
   The Stripe line-item wiring is deferred to the UI pass.

2. **Vendor API is external / lazy-imported.** Confirmed: `src/print_vendor.py`
   has no top-level vendor SDK import; the `PrintVendorLike` protocol is the
   only typing surface. Tests use fakes exclusively.

3. **Analytics are internal-only.** Confirmed: `compute_analytics` is a pure
   function returning a dict; no customer-facing dashboard was built. The
   `tools/analytics_report.py` CLI was deferred.

The `requirements.md` user stories described two end-to-end flows. Story 1
(customer orders print, auto-submits to vendor, receives tracking) is
**partially delivered** -- the payload builder, cost calculator, and vendor
seam are in place, but the auto-submit-on-payment trigger is deferred.
Story 2 (product owner runs analytics CLI) is **partially delivered** -- the
`compute_analytics` function exists but `tools/analytics_report.py` does not.

## Carry-forwards (honestly open, not passed)

- **Shipping UI wiring** (task 1.3). `ShippingAddress` validation is tested but
  the `web/order.html` form does not yet capture or send shipping fields to the
  server. Needed before a real print order can complete.

- **Automatic vendor submission** (tasks 2.3, 3.2). `submit_print_order` works
  with a fake client but nothing triggers it on payment confirmation. A real
  `PrintVendorLike` implementation wrapping the Printful/Prodigi SDK needs to be
  authored and wired into `serve.py`.

- **`tools/analytics_report.py`** (task 5.3). The `compute_analytics` function
  is tested; the CLI that reads the `orders/` directory and prints a report is
  not yet written.

- **Mixed-order integration test** (task 6.1). A broader integration test
  exercising 5 mixed orders through the full pipeline into analytics was
  deferred.

- **Playwright e2e: shipping form** (task 6.2). No browser-level test for the
  print shipping flow exists yet.

- **No live byte-identical `verify_determinism.py` double-render was run.**
  Byte-identity rests on the "no pipeline change" invariant, matching the
  standing carry-forward from prior epochs.

## Lessons

- **The "pure core first, wiring later" pattern continues to work well.** All
  three new modules (`shipping`, `print_vendor`, `analytics`) are pure,
  stdlib-only, and fully testable without any vendor SDK or browser. The deferred
  items are all integration/wiring -- the hardest-to-test parts are already
  covered.

- **Protocol-based vendor seams pay for themselves immediately.** The
  `PrintVendorLike` protocol let the handoff integration tests (`test_print_handoff`)
  exercise the full order-to-tracking cycle with a fake vendor client. When a
  real Printful/Prodigi SDK wrapper is authored, it slots in without changing
  any `src/` code.

- **Event-log-driven analytics avoid a second data model.** By building
  `compute_analytics` over the existing `OrderStore` event log rather than
  introducing a separate analytics database, the system stays simple and the
  analytics tests use the same order fixtures as the order tests.

- **Consider writing a pre-analysis even for contract/wiring epochs.** As with
  Epochs 16, 18, and 19, no pre-analysis was written. The requirements were
  straightforward and the risks small, but naming predictions up front would
  have made this retrospective a graded one.
