# Requirements — Payment & Delivery

**Epoch:** 29
**Date:** 2026-09-16
**Status:** planning
**Depends on:** Epoch 28 (self-serve order & proof loop)

## Problem

After Epoch 28, a customer can submit an order and approve a proof, but there's
no payment capture or final delivery mechanism. The customer approves a proof
and... nothing happens. This epoch closes the loop: approval triggers payment,
payment triggers final (un-watermarked) delivery via time-limited signed links.

Also includes the custom trip overlay (GPX/KML path on base art) as a premium
add-on with 50% surcharge.

## Constraints

- **No auth.** Payment via Stripe Checkout (hosted page). No card data on our server.
- **Offline-suite discipline.** Stripe SDK never imported at `src/` module load.
  All payment state logic is pure and testable with fakes.
- **Time-limited delivery.** Final download links expire after 90 days. Customer
  can request re-issue via email.

## Items

127. Stripe Checkout integration
128. Payment state machine extension
129. Signed delivery links (90-day expiry)
130. Delivery page (`web/delivery.html`)
131. Custom trip overlay (GPX upload, 50% surcharge)

## User stories

1. **As a customer**, after I approve a proof, I'm redirected to a Stripe payment
   page showing my order total. After paying, I receive a delivery email with
   download links.

2. **As a customer**, I click my delivery link within 90 days and download my
   final PNG/SVG/PDF. After 90 days, the link shows "expired — contact support."

3. **As a customer**, I upload a GPX file of a river trip I took. My order is
   flagged as a "memorial trip" with a 50% surcharge. The proof shows my path
   overlaid on the watershed art.

## Test design (TDD)

### Unit tests (`tests/test_payment.py`) — NEW

```
test_create_checkout_session_payload     — correct line items, amount, metadata
test_payment_webhook_valid_signature     — verified webhook transitions order to paid
test_payment_webhook_invalid_signature   — rejected, no state change
test_payment_state_transitions           — approved → payment_pending → paid → fulfilled
test_delivery_link_signed_and_expires    — 90-day expiry, HMAC signature
test_delivery_link_expired_rejected      — past 90 days → invalid
```

### Unit tests (`tests/test_trip_overlay.py`) — NEW

```
test_parse_gpx_extracts_coordinates     — valid GPX → list of (lat, lon)
test_parse_kml_extracts_coordinates     — valid KML → list of (lat, lon)
test_invalid_gpx_rejected               — malformed XML → error
test_overlay_path_on_svg                — SVG output contains trip path <polyline>
test_surcharge_applied                  — trip order total = base * 1.5
test_trip_order_requires_file           — trip add-on without file → error
```

### Integration tests

```
test_approve_to_payment_to_delivery     — full cycle with fake Stripe
test_trip_overlay_full_cycle            — upload GPX → render with overlay → proof → approve
```

### E2E (Playwright)

```
test_approve_redirects_to_stripe        — approve button → Stripe Checkout URL
test_delivery_page_shows_downloads      — after payment, delivery page works
```
