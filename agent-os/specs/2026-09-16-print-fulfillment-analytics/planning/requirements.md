# Requirements — Print Fulfillment & Product Analytics

**Epoch:** 30
**Date:** 2026-09-16
**Status:** planning
**Depends on:** Epoch 29 (payment & delivery)

## Problem

After Epoch 29, digital delivery works end-to-end. But print orders still dead-end
after payment — there's no way to forward a print-ready file to a printing vendor
or track shipment. And there's no analytics to inform product decisions.

This epoch adds: print vendor forwarding (customer pays print + shipping),
and a structured analytics layer over the event log.

## Constraints

- **Customer pays shipping.** We don't absorb print/shipping costs. The customer
  sees print + shipping as a line item at checkout (via Stripe).
- **Vendor API is external.** Print vendor SDK (Printful/Prodigi) is lazy-imported,
  never at `src/` module load time. Offline tests use fakes.
- **Analytics are internal-only.** No customer-facing dashboard. A `tools/` script
  or simple internal page.

## Items

132. Print vendor integration (Printful/Prodigi API)
133. Shipping address capture on order form
134. Print proof-to-production handoff
135. Product analytics dashboard
136. Render performance instrumentation

## User stories

1. **As a customer**, I order a 24×36 print. At checkout, I see the art price +
   print price + shipping. After payment, my print is automatically sent to the
   printer. I receive a shipping confirmation with tracking.

2. **As a product owner**, I run `tools/analytics_report.py` and see: orders by
   product/region, proof acceptance rate, average render time, payment conversion
   rate, and top-requested counties.

## Test design (TDD)

### Unit tests (`tests/test_print_fulfillment.py`) — NEW

```
test_create_print_order_payload         — correct file URL, product spec, address
test_shipping_address_validation        — valid US address passes, invalid rejected
test_print_order_tracks_vendor_id       — vendor order ID stored on request
test_print_order_tracks_shipment        — tracking number recorded when available
test_print_cost_passthrough             — print + shipping added to order total
```

### Unit tests (`tests/test_analytics.py`) — NEW

```
test_orders_by_product_type             — correct counts from event log
test_orders_by_region                   — correct geographic distribution
test_proof_acceptance_rate              — approved / total proofs
test_average_render_time                — mean of render_completed - render_started
test_payment_conversion_rate            — paid / approved
test_revision_reasons_counted           — adjust events grouped by changed field
```

### Integration tests

```
test_print_order_full_cycle             — order → pay → vendor submit → tracking (fake vendor)
test_analytics_across_multiple_orders   — 10 orders → correct aggregate metrics
```

### E2E (Playwright)

```
test_print_order_shows_shipping_form    — print product → shipping address fields appear
test_print_checkout_includes_shipping   — Stripe session has print + shipping line items
```
