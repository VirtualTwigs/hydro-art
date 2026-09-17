# Implementation Report — Payment & Delivery

**Epoch:** 29 (items #127–#131)
**Date:** 2026-09-16
**Status:** implemented (integration/e2e deferred)

## What shipped

### New modules
- **`src/payment.py`** — Stripe Checkout integration: `create_checkout_session` (builds session via injectable client), `handle_webhook` (HMAC-SHA256 signature verification matching Stripe's `v1` scheme), `WebhookError`. Pure, offline-testable — Stripe SDK never imported at module load.
- **`src/trip_overlay.py`** — GPX/KML parsing: `parse_gpx`, `parse_kml` (stdlib XML), `overlay_path_on_svg` (adds `<polyline>` to SVG), `trip_surcharge` (50% markup), `validate_trip_order`. Pure, offline-testable.
- **`tests/test_payment.py`** — 7 tests: checkout session construction (3), webhook verification (3), payment state lifecycle (1).
- **`tests/test_trip_overlay.py`** — 8 tests: GPX parsing (2), KML parsing (2), SVG overlay (2), surcharge (1), validation (1).

### Extended modules
- **`src/orders.py`** — Added `paid` status, updated transitions (`payment_pending → paid → fulfilled`), added payment fields to `Request` (`stripe_session_id`, `stripe_payment_intent`, `amount_cents`, `paid_at`).
- **`src/proof.py`** — Added `sign_delivery_url` and `verify_delivery_token` with 90-day default expiry. Reuses the same HMAC scheme as proof tokens.
- **`src/server.py`** — Added `POST /api/webhook/stripe` (Stripe webhook with signature verification), `GET /api/delivery/<token>` (signed delivery links). Added `headers`, `webhook_secret`, `delivery_secret` parameters through the handler chain.
- **`tests/test_orders.py`** — +5 tests: `TestPaymentStateMachine` (approved→payment_pending, payment_pending→paid, paid→fulfilled, invalid transition, payment fields).
- **`tests/test_proof.py`** — +4 tests: `TestDeliveryLinks` (roundtrip, 90-day default, expired, tampered).
- **`tests/test_server.py`** — +4 tests: approve returns 200, webhook valid POST, webhook bad signature, delivery valid/expired tokens.

### Tests summary
| File | New tests | Total |
|------|-----------|-------|
| `tests/test_payment.py` | 7 | 7 |
| `tests/test_trip_overlay.py` | 8 | 8 |
| `tests/test_orders.py` | 5 | 38 |
| `tests/test_proof.py` | 4 | 10 |
| `tests/test_server.py` | 4 | 32 |

**Full suite: 1000 passed, 6 pre-existing failures (test_min_order.py). Zero regressions.**

## Deferred items
- Integration test: full payment cycle with fake Stripe webhook (7.1)
- Integration test: trip overlay full cycle (7.2)
- Playwright e2e: approve → Stripe URL, delivery page (7.3)
- Trip overlay UI wiring: file upload in order form (6.3)
