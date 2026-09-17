# Implementation Report — Self-Serve Order Form & Automated Proof Loop

**Epoch:** 28 (items #120–#126)
**Date:** 2026-09-16
**Status:** implemented (e2e deferred)

## What shipped

### New modules
- **`src/proof.py`** — HMAC-SHA256 signed proof URLs with configurable expiry, token verification, SVG watermarking. Pure, offline-testable.
- **`tests/test_proof.py`** — 6 unit tests: sign/verify roundtrip, expired token, tampered token, wrong secret, watermark text, watermark preserves paths.
- **`tests/test_order_proof_pipeline.py`** — 5 integration tests: full order-to-proof cycle, proof-ready after render, revision cycle, event log completeness, concurrent order isolation.

### Extended modules
- **`src/orders.py`** — Added `OrderEvent` dataclass, `events` field on `Request`, three new statuses (`revision_requested`, `render_failed`, `payment_pending`), extended transition table, event logging on create and every status transition.
- **`src/server.py`** — Auto-dispatch on order submit (submitted→accepted→rendering + job dispatch, returns 202). New `_proof_dispatch` handler for `GET /api/proof/<token>`, `POST /api/proof/<token>/approve`, `POST /api/proof/<token>/adjust`. Added `proof_secret` parameter through the handler chain.
- **`src/email_delivery.py`** — Added `send_proof_email` with HTML/plain-text template for proof-ready notifications.

### Web UI
- **`web/order.html`** — 6-step progressive order form (product → location → style → details → contact → review). Uses `HydroUX.STATES`/`COUNTIES` for dropdowns. Submits to `POST /api/orders`.
- **`web/proof.html`** — Token-based proof review page. Fetches proof data via `GET /api/proof/<token>`. Approve and adjust buttons.
- **`web/start.html`** — Updated hero CTA ("Order now" → order.html) and product card links to point to order form with product pre-selected.

### Tests added/modified
| File | Tests | Status |
|------|-------|--------|
| `tests/test_proof.py` | 6 new | all pass |
| `tests/test_orders.py` | 11 new (4 validation, 4 transition, 3 event) | all pass |
| `tests/test_server.py` | 10 new (4 submit, 6 proof routes) | all pass |
| `tests/test_email_delivery.py` | 3 new (proof email) | all pass |
| `tests/test_order_proof_pipeline.py` | 5 new (integration) | all pass |

**Total suite:** 971 passed, 6 pre-existing failures (test_min_order.py — unrelated, unimplemented feature). Zero regressions.

## Deferred items
- **Playwright e2e tests** (Task Group 11) — needs running server + Node 18+. Test specs outlined but not created.
- **Manual smoke test** (12.2) — needs `serve.py` running with GIS data.
- **Re-render limit** (3 max per order) — noted in spec open questions, not enforced yet.
- **Proof email wiring** into proof-ready transition — `send_proof_email` is implemented but not automatically called when an order transitions to `proof_ready`. Needs the render-complete callback to be wired (the hook exists, just needs the email call).

## Architecture notes
- The proof secret is injected via `proof_secret` kwarg on `handle_request`, threaded through `make_handler` and `serve`. In production, read from `HYDRO_ART_PROOF_SECRET` env var.
- The `_create_order` function now accepts a `runner` parameter for auto-dispatch. When no runner is provided, behavior falls back to the original 201 create-only response.
- Event logging uses dict-serialized `OrderEvent` objects on the `Request.events` list for JSON persistence compatibility.
