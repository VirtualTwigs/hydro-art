# Tasks — Self-Serve Order Form & Automated Proof Loop

**Epoch:** 28 (items #120–#126)
**Method:** TDD — tests first in each group, then implementation, then verify.

## Task Group 1: Proof module (`src/proof.py`)

Tests first → implementation → verify.

- [x] 1.1 Write `tests/test_proof.py` with 6 tests (sign/verify roundtrip, expired token, tampered token, wrong secret, watermark adds text, watermark preserves paths). All tests fail (module doesn't exist yet).
- [x] 1.2 Create `src/proof.py` with `sign_proof_url`, `verify_proof_token`, `watermark_svg`. Make all 6 tests pass.
- [x] 1.3 Run `tests/test_proof.py` — all green. Run full offline suite — no regressions.

## Task Group 2: Order state machine extensions (`src/orders.py`)

Tests first → implementation → verify.

- [x] 2.1 Write 7 new tests in `tests/test_orders.py`: revision_requested transition, revision→rendering, render_failed transition, render_failed→retry, event logging on transition, event structure, multiple proof cycles. All new tests fail.
- [x] 2.2 Extend `src/orders.py`: add `revision_requested` and `render_failed` to `STATUSES`, update `TRANSITIONS`, add `OrderEvent` dataclass, append events on every `update_status` call. Add `payment_pending` status for forward-compat.
- [x] 2.3 Run `tests/test_orders.py` — all green (old + new). Run full offline suite — no regressions.

## Task Group 3: Order form validation (`src/fulfillment.py` + `src/orders.py`)

Tests first → implementation → verify.

- [x] 3.1 Write tests for order-form payload validation: valid digital-image order, valid print order, invalid region rejected, missing email rejected, PRISM art direction rejected, title too long rejected, unsupported size rejected.
- [x] 3.2 Validation already handled by existing `build_order` in `src/fulfillment.py` — validates region, style, size, formats against config allowlists + rights gate. Added coverage tests in `TestOrderFormValidation`.
- [x] 3.3 Run validation tests — all green. Run full offline suite — no regressions.

## Task Group 4: Server routes — order submission

Tests first → implementation → verify.

- [x] 4.1 Write 4 new tests in `tests/test_server.py`: POST /api/orders returns 202 with valid payload, 400 on bad region, 400 on missing email, 400 on PRISM style.
- [x] 4.2 Updated `_create_order` in `src/server.py` — auto-transitions submitted→accepted→rendering, dispatches render job via runner, returns 202.
- [x] 4.3 Run server tests — all green. Run full offline suite — no regressions.

## Task Group 5: Server routes — proof review

Tests first → implementation → verify.

- [x] 5.1 Write 6 new tests in `tests/test_server.py`: valid proof token → 200, expired token → 410, invalid token → 403, POST approve transitions order, POST adjust triggers re-render, adjust preserves email.
- [x] 5.2 Add `_proof_dispatch` to `src/server.py`: `GET /api/proof/<token>` (returns proof data JSON), `POST /api/proof/<token>/approve`, `POST /api/proof/<token>/adjust`. Wire token verification via `src/proof.py`.
- [x] 5.3 Run server tests — all green. Run full offline suite — no regressions.

## Task Group 6: Automated render queue wiring

Tests first → implementation → verify.

- [x] 6.1 Write integration test `tests/test_order_proof_pipeline.py`: test_full_order_to_proof_cycle, test_proof_ready_after_render_complete, test_revision_cycle, test_event_log_complete_cycle, test_concurrent_orders_isolated.
- [x] 6.2 Integration wired via `_create_order` auto-dispatch and `_proof_dispatch` adjust → re-render. Tested with fake runner in integration tests.
- [x] 6.3 Run integration tests — all green. Run full offline suite — no regressions.

## Task Group 7: Email notifications

Tests first → implementation → verify.

- [x] 7.1 Write tests for `send_proof_email`: called with correct args when proof_ready, includes signed URL, degrades gracefully without Gmail password.
- [x] 7.2 Add `send_proof_email(to, request_id, proof_url, title)` to `src/email_delivery.py`.
- [x] 7.3 Run email tests — all green. Run full offline suite — no regressions.

## Task Group 8: Event log

Tests first → implementation → verify.

- [x] 8.1 Event log tests covered in `TestEventLog` (test_orders.py) and `TestEventLogCompleteCycle` (test_order_proof_pipeline.py).
- [x] 8.2 Added `events` field to `Request` dataclass, `OrderEvent` dataclass. Events appended on `create_request` and every `update_status`.
- [x] 8.3 Run event log tests — all green. Run full offline suite — no regressions.

## Task Group 9: Web UI — order form

- [x] 9.1 Create `web/order.html` — multi-step guided form with progressive disclosure. Uses `web/shared/hydro-ux.js` for option data. Submits to `POST /api/orders`. Shows confirmation with request ID.
- [x] 9.2 State/county dropdowns populated from `HydroUX.STATES` and `HydroUX.COUNTIES` in `hydro-ux.js`.
- [x] 9.3 Updated `web/start.html` — hero CTA → "Order now" linking to `order.html`; product cards link to `order.html?product=<type>`.

## Task Group 10: Web UI — proof review page

- [x] 10.1 Create `web/proof.html` — displays proof data, title, location, source credit, approve/adjust buttons. Token from URL parameter. Fetches proof data from `GET /api/proof/<token>`.
- [x] 10.2 Wire "Approve" button to `POST /api/proof/<token>/approve` — show success confirmation.
- [x] 10.3 Wire "Adjust & Re-render" button — redirect to `web/order.html`.

## Task Group 11: Playwright e2e tests

- [ ] 11.1 *Deferred* — Create `tests/e2e/tests/02-order-flow.spec.js` with happy-path tests (needs running server + Node 18+).
- [ ] 11.2 *Deferred* — Add proof review e2e.
- [ ] 11.3 *Deferred* — Run full Playwright suite (01 + 02) — all green.

## Task Group 12: Full-suite regression & smoke test

- [x] 12.1 Run full offline Python suite (`pytest -q`) — 971 passed, 6 pre-existing failures (test_min_order.py, unrelated). Zero regressions.
- [ ] 12.2 Manual smoke test: start `serve.py`, open order form, submit an order, verify proof email (or check order JSON), review proof page, approve. Confirm full lifecycle.
- [x] 12.3 Write `implementation/report.md` summarizing what shipped, test coverage, and any deferred items.
