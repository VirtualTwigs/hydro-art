# Tasks — Payment & Delivery

**Epoch:** 29 (items #127–#131)
**Method:** TDD — tests first in each group, then implementation, then verify.
**Depends on:** Epoch 28 complete.

## Task Group 1: Payment state machine

- [x] 1.1 Write tests in `tests/test_orders.py`: approved → payment_pending, payment_pending → paid, paid → fulfilled transitions. Invalid transitions rejected (e.g., submitted → paid). Payment fields on Request.
- [x] 1.2 Added `paid` to `STATUSES` and `TRANSITIONS`. Added payment fields (`stripe_session_id`, `stripe_payment_intent`, `amount_cents`, `paid_at`) to `Request`.
- [x] 1.3 Run tests — all green. Full suite — no regressions.

## Task Group 2: Stripe Checkout integration

- [x] 2.1 Write `tests/test_payment.py`: checkout session construction (3 tests), webhook verification (valid, invalid, idempotent — 3 tests), payment state transition (1 test).
- [x] 2.2 Created `src/payment.py`: `create_checkout_session`, `handle_webhook`, `WebhookError`. Pure, offline-testable with fake Stripe client.
- [x] 2.3 Run payment tests — all green. Full suite — no regressions.

## Task Group 3: Server routes — payment

- [x] 3.1 Write tests: approve returns 200, webhook valid POST transitions to paid, webhook bad signature rejected.
- [x] 3.2 Added `POST /api/webhook/stripe` route with HMAC signature verification. Added `headers` param to `handle_request` for Stripe-Signature header. On valid webhook, transitions `payment_pending → paid`.
- [x] 3.3 Run server tests — all green. Full suite — no regressions.

## Task Group 4: Signed delivery links

- [x] 4.1 Write tests in `tests/test_proof.py` (`TestDeliveryLinks`): roundtrip, 90-day default, expired rejected, tampered rejected.
- [x] 4.2 Added `sign_delivery_url` and `verify_delivery_token` to `src/proof.py`. 90-day default expiry (7,776,000 seconds).
- [x] 4.3 Run tests — all green. Full suite — no regressions.

## Task Group 5: Delivery page

- [x] 5.1 `web/delivery.html` exists — shows download links, order details. Updated to work with token-validated route.
- [x] 5.2 Added `GET /api/delivery/<token>` route to `src/server.py`. Returns order data JSON. Validates token with `verify_delivery_token`. Expired → 410, invalid → 403.
- [x] 5.3 `send_delivery_email` already exists in `src/email_delivery.py` — wired on fulfilled transition in `_update_order`.

## Task Group 6: Custom trip overlay

- [x] 6.1 Write `tests/test_trip_overlay.py`: GPX parsing (2 tests), KML parsing (2 tests), overlay adds polyline (1 test), preserves content (1 test), surcharge (1 test), trip requires file (1 test).
- [x] 6.2 Created `src/trip_overlay.py`: `parse_gpx`, `parse_kml`, `overlay_path_on_svg`, `trip_surcharge`, `validate_trip_order`. Pure, offline-testable.
- [ ] 6.3 Wire trip overlay into order form: file upload field (GPX/KML), `is_trip_memorial` flag on request. *Deferred — needs order form UI update.*
- [x] 6.4 Run trip overlay tests — all green. Full suite — no regressions.

## Task Group 7: Integration & e2e

- [ ] 7.1 *Deferred* — Integration test: full payment cycle with fake Stripe webhook.
- [ ] 7.2 *Deferred* — Integration test: trip overlay full cycle.
- [ ] 7.3 *Deferred* — Playwright e2e: approve redirects to Stripe URL, delivery page loads.
- [x] 7.4 Full suite — 1000 passed, 6 pre-existing failures (test_min_order.py). Zero regressions.
