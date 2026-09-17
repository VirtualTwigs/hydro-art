# Epoch 29 — Payment & Delivery retrospective (2026-09-16)

_Closed 2026-09-16 (within the combined Epochs 28-30 commit `803f4ae`); retro
written 2026-09-16. **No pre-registered watch-list** — the spec folder
(`2026-09-16-payment-and-delivery`) carries `planning/requirements.md`,
`tasks.md`, and `implementation/report.md`, but no `planning/pre-analysis.md`.
This is a narrative closeout. Part of the "Self-serve customer journey
(Epochs 28-30)" batch; items #127-#131._

## What shipped

### New modules

- **`src/payment.py`** (NEW, 138 lines) — Stripe Checkout integration:
  `create_checkout_session` (builds a session via an injectable `StripeClientLike`
  protocol), `handle_webhook` (stdlib HMAC-SHA256 verification matching Stripe's
  `v1` signature scheme — `t=<timestamp>,v1=<hmac_hex>`, 5-minute tolerance
  window, extracts `request_id` from session metadata), `WebhookError`. Pure,
  offline-testable — Stripe SDK is never imported at module load.

- **`src/trip_overlay.py`** (NEW, 192 lines) — GPX/KML parsing and SVG overlay:
  `parse_gpx` (stdlib `xml.etree`, namespace-aware + bare fallback),
  `parse_kml` (same, handles `lon,lat,ele` triples), `overlay_path_on_svg`
  (adds a `<polyline>` before `</svg>` with configurable stroke/width/opacity,
  linear lat/lon-to-viewbox mapping with 10% margin), `trip_surcharge` (50%
  markup: `int(base_cents * 1.5)`), `validate_trip_order` (trip flag without
  file content raises `TripOverlayError`). Pure, offline-testable — no GDAL, no
  network.

### Extended modules

- **`src/orders.py`** — Added `paid` to `STATUSES` and `TRANSITIONS`
  (`payment_pending -> paid -> fulfilled`). Added payment fields on `Request`:
  `stripe_session_id`, `stripe_payment_intent`, `amount_cents`, `paid_at`.

- **`src/proof.py`** — Added `sign_delivery_url` and `verify_delivery_token`
  with 90-day default expiry (7,776,000 seconds). Reuses the same HMAC scheme as
  proof tokens.

- **`src/server.py`** — Added `POST /api/webhook/stripe` route with HMAC
  signature verification (reads `Stripe-Signature` header, validates via
  `handle_webhook`, transitions `payment_pending -> paid`). Added
  `GET /api/delivery/<token>` route (validates token with `verify_delivery_token`;
  expired returns 410, invalid returns 403, valid returns order data JSON). Added
  `headers`, `webhook_secret`, `delivery_secret` parameters through the handler
  chain.

- **`web/delivery.html`** (206 lines) — Customer-facing delivery page showing
  artwork preview, order details (region, style, size), and download links for
  final (un-watermarked) assets. Loads order data from the token-validated
  `/api/delivery/<token>` route.

### Tests added

| File | New tests | Total in file |
|------|-----------|---------------|
| `tests/test_payment.py` (NEW) | 7 | 7 |
| `tests/test_trip_overlay.py` (NEW) | 8 | 8 |
| `tests/test_orders.py` | +5 | 38 |
| `tests/test_proof.py` | +4 | 10 |
| `tests/test_server.py` | +4 | 32 |

**+28 tests this epoch.** Full suite: **1000 passed**, 6 pre-existing failures
in `test_min_order.py` (feature not yet implemented; tests committed ahead of
code per `2c6972f`). Zero regressions.

### Commit

All Epoch 29 work landed in the combined Epochs 28-30 commit `803f4ae`
(`feat: implement self-serve customer journey`), 35 files changed, 5202
insertions. Roadmap items #127-#131 ticked in `921b136`.

## Real-data findings

No real-data run in this epoch by design. The payment and delivery subsystem is
a pure state-machine + signature layer with no GIS dependency. The expected
real-run pattern (Stripe webhook replay against a live `serve.py`, actual
Checkout redirect) is deferred to the integration/e2e tasks (7.1-7.3). No
bug-the-real-run-surfaced to report.

The webhook HMAC verification uses stdlib `hmac.new` + `hmac.compare_digest`
(constant-time comparison), matching Stripe's documented `v1` scheme. This was
validated against hand-constructed signatures in `tests/test_payment.py`, not
against real Stripe webhook deliveries.

## Invariants held

- **Offline suite:** 1000 passed (+28 new), 6 pre-existing `test_min_order.py`
  failures (known — tests for unimplemented feature). No regressions.
- **2D default output byte-identical:** yes. No `PIPELINE_STAGES` change, no
  renderer change. The epoch adds payment/delivery plumbing entirely outside the
  render path.
- **`PIPELINE_STAGES` untouched:** yes. `src/payment.py` and `src/trip_overlay.py`
  are parallel subsystem modules, not wired into the 12-stage pipeline.
- **Rights gate:** N/A for this epoch (payment does not select art style or
  climate source). The `assert_sellable` gate in `src/fulfillment.py` and
  `src/endpoints.py` remains enforced upstream of any order that reaches payment.

## Graded against pre-analysis

No `planning/pre-analysis.md` exists for this spec. The requirements document
flagged three constraints:

1. **No auth — Stripe Checkout only.** Confirmed held. `create_checkout_session`
   builds a hosted Checkout Session; no card data touches the server. The
   `StripeClientLike` protocol means the real Stripe SDK is injected at serve
   time, never imported by `src/`.

2. **Offline-suite discipline.** Confirmed held. `src/payment.py` imports only
   stdlib (`hashlib`, `hmac`, `json`, `time`, `typing`). `src/trip_overlay.py`
   imports only `xml.etree.ElementTree`. Neither touches GDAL or network.

3. **Time-limited delivery (90-day expiry).** Confirmed implemented.
   `sign_delivery_url` defaults to 7,776,000 seconds; `verify_delivery_token`
   rejects expired tokens. Tested in `tests/test_proof.py::TestDeliveryLinks`.

## Carry-forwards (honestly open, not passed)

- **Trip overlay UI wiring (task 6.3).** `src/trip_overlay.py` is implemented
  and tested, but the order form (`web/order.html`) does not yet have a file
  upload field for GPX/KML or an `is_trip_memorial` flag. The backend is ready;
  the frontend integration is deferred.

- **Integration tests (tasks 7.1, 7.2).** A full payment cycle test (fake Stripe
  webhook triggering `approved -> payment_pending -> paid -> fulfilled` with
  delivery email) and a trip overlay full-cycle test have not been written. The
  unit tests cover each transition and each parsing path independently, but the
  end-to-end state-machine walk is not exercised in a single test.

- **Playwright e2e (task 7.3).** No browser-level test that the approve button
  redirects to a Stripe Checkout URL, or that `web/delivery.html` loads and
  displays download links from a token-validated route. The existing Playwright
  harness (`tests/e2e/`) does not cover payment flows.

- **CRS-aware trip overlay.** `overlay_path_on_svg` uses a simple linear
  lat/lon-to-viewbox mapping. For production use against EPSG:5070-projected
  SVGs, coordinates should be reprojected first. The module documents this as a
  known limitation ("For production use, coordinates should be reprojected to
  match the SVG's CRS first").

- **No live Stripe webhook verification.** The HMAC scheme matches Stripe's
  documented `v1` format, but has not been tested against an actual Stripe
  webhook delivery. This is a real-run-only validation.

## Lessons

- **The "no auth" constraint kept the epoch clean.** By delegating payment to
  Stripe Checkout (hosted page, redirect-based), the epoch avoided session
  management, token refresh, and stored credentials entirely. The server routes
  are stateless signature verifiers — the same pattern as proof tokens. This
  meant the `src/proof.py` HMAC machinery was directly reusable for delivery
  links, avoiding a second signing implementation.

- **Batch commits conflate epoch boundaries.** Epochs 28, 29, and 30 landed in
  a single commit (`803f4ae`), making per-epoch attribution harder. The commit
  stat (35 files, 5202 insertions) covers all three epochs. Future multi-epoch
  batches should consider separate commits per epoch for cleaner `git log`
  archaeology.

- **Trip overlay is feature-complete but UI-orphaned.** The backend
  (`parse_gpx`, `parse_kml`, `overlay_path_on_svg`, `trip_surcharge`,
  `validate_trip_order`) is fully tested and ready, but without the order-form
  file upload (task 6.3), a customer cannot actually use it. This is a common
  pattern in this project — backend-first is correct for testability, but the
  feature is not shippable until the UI wiring lands.

- **Pre-existing test failures should be resolved, not normalized.** The 6
  `test_min_order.py` failures (committed as ahead-of-implementation tests in
  `2c6972f`) are a known pattern in this project, but "1000 passed, 6 failed"
  is noisier than "1000 passed" for regression detection. Consider implementing
  the min-order feature or marking those tests as `xfail` so the suite is fully
  green.
