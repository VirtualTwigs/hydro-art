# Tasks — Print Fulfillment & Product Analytics

**Epoch:** 30 (items #132–#136)
**Method:** TDD — tests first in each group, then implementation, then verify.
**Depends on:** Epoch 29 complete.

## Task Group 1: Shipping address capture

- [x] 1.1 Write `tests/test_shipping.py`: 10 tests (valid address, missing name/street/city/state/zip, invalid zip format, zip+4, optional line2, to_dict roundtrip).
- [x] 1.2 Created `src/shipping.py`: `ShippingAddress` dataclass, `validate_address`, `ShippingError`. Pure, offline-testable.
- [ ] 1.3 *Deferred* — Wire shipping fields into order form UI and `Request` dataclass.
- [x] 1.4 Run tests — all green. Full suite — no regressions.

## Task Group 2: Print vendor integration

- [x] 2.1 Write `tests/test_print_fulfillment.py`: 6 tests (payload construction, vendor ID, vendor ID stored, tracking, print cost, cost total).
- [x] 2.2 Created `src/print_vendor.py`: `PrintVendorLike` protocol, `build_print_order_payload`, `submit_print_order`, `check_shipment`, `calculate_print_cost`. Pure, offline-testable.
- [ ] 2.3 *Deferred* — Wire automatic vendor submission on paid print orders.
- [x] 2.4 Run tests — all green. Full suite — no regressions.

## Task Group 3: Print proof-to-production handoff

- [x] 3.1 Write `tests/test_print_handoff.py`: 2 integration tests (full print cycle with fake vendor, shipping email on fulfillment).
- [ ] 3.2 *Deferred* — Auto-submit on payment confirmation, dedicated `send_shipping_email`.
- [x] 3.3 Run integration tests — all green. Full suite — no regressions.

## Task Group 4: Render performance instrumentation

- [x] 4.1 Write `tests/test_render_instrumentation.py`: 3 tests (render_started with queue wait, render_completed with duration/stages, queue depth per order).
- [x] 4.2 Added `add_event` method to `OrderStore` for recording custom events with arbitrary detail dicts. Events stored in the order's event log.
- [x] 4.3 Run tests — all green. Full suite — no regressions.

## Task Group 5: Product analytics

- [x] 5.1 Write `tests/test_analytics.py`: 6 tests (orders by product, by region, proof acceptance rate, average render time, payment conversion rate, top counties).
- [x] 5.2 Created `src/analytics.py`: `compute_analytics(orders) -> dict`. Pure functions over order dicts with event logs. No database dependency.
- [ ] 5.3 *Deferred* — Create `tools/analytics_report.py` CLI script.
- [x] 5.4 Run tests — all green. Full suite — no regressions.

## Task Group 6: Integration & regression

- [ ] 6.1 *Deferred* — Integration test: 5 mixed orders → analytics.
- [ ] 6.2 *Deferred* — Playwright e2e: print order shipping form.
- [x] 6.3 Full suite — 1027 passed, 6 pre-existing failures. Zero regressions. Implementation report written.
