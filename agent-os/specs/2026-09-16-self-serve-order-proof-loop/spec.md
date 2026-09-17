# Spec — Self-Serve Order Form & Automated Proof Loop

**Epoch:** 28 (items #120–#126)
**Date:** 2026-09-16
**Status:** ready for implementation
**Depends on:** Epoch 24 (e2e harness), existing `src/orders.py`, `src/server.py`, `src/jobs.py`

## Overview

Build the automated customer journey: web form → render queue → proof → accept
or revise → re-render. No accounts. Email-only identity. Signed temporary links
for proof review. Structured event log for product analytics.

## Architecture

```
Customer                          Server                        Pipeline
   │                                │                              │
   ├─ POST /api/orders ────────────►│                              │
   │  (form payload + email)        │── validate (config + rights) │
   │                                │── create Request (submitted)  │
   │                                │── auto-accept ───────────────►│
   │◄─ 202 {request_id} ───────────│── dispatch render job         │
   │                                │                              │
   │  ◄── confirmation email ───────│                              │
   │                                │                              │
   │                                │◄── job complete ─────────────│
   │                                │── generate proof (watermark)  │
   │                                │── sign proof URL              │
   │  ◄── proof email (link) ───────│── transition: proof_ready     │
   │                                │                              │
   ├─ GET /proof/<token> ──────────►│                              │
   │◄─ proof page (approve/adjust) ─│                              │
   │                                │                              │
   ├─ POST /proof/<token>/approve ─►│── transition: approved       │
   │◄─ approval confirmation ───────│                              │
   │                                │                              │
   │  ─── OR ───                    │                              │
   │                                │                              │
   ├─ POST /proof/<token>/adjust ──►│── transition: submitted (new) │
   │  (modified payload)            │── re-dispatch render ────────►│
   │◄─ 202 (re-rendering) ─────────│                              │
```

## Module design

### 1. `src/proof.py` — Proof generation & signed URLs (NEW)

Pure, offline-testable. No GDAL imports.

```python
# Key functions:
def sign_proof_url(request_id: str, secret: bytes, expires_in: int = 604800) -> str
def verify_proof_token(token: str, secret: bytes) -> tuple[str, bool]  # (request_id, valid)
def watermark_svg(svg_content: str, text: str) -> str  # adds diagonal watermark text
```

- HMAC-SHA256 signing: `base64url(request_id + "." + expiry_ts + "." + hmac)`
- Secret from `HYDRO_ART_PROOF_SECRET` env var (required for serve, not for offline tests)
- Watermark is a simple SVG `<text>` overlay with "PROOF" diagonal, 30% opacity
- Expiry default: 7 days (configurable)

### 2. `src/orders.py` — Extended state machine (MODIFY)

Add transitions for the re-render cycle and event logging:

```python
# New statuses (insert into STATUSES):
# "revision_requested" — buyer asked to adjust, before new render

# Extended transitions:
TRANSITIONS = {
    "submitted": frozenset({"accepted"}),
    "accepted": frozenset({"rendering"}),
    "rendering": frozenset({"proof_ready", "render_failed"}),
    "proof_ready": frozenset({"approved", "revision_requested"}),
    "revision_requested": frozenset({"rendering"}),
    "approved": frozenset({"payment_pending", "fulfilled"}),  # payment_pending for Epoch 29
    "render_failed": frozenset({"rendering"}),  # retry
    "fulfilled": frozenset(),
}

# Event log on Request:
@dataclass
class OrderEvent:
    timestamp: str      # ISO 8601
    event: str          # "submitted", "render_started", "proof_viewed", etc.
    detail: dict        # event-specific metadata
```

### 3. `src/server.py` — New routes (MODIFY)

Add order-form and proof-review routes:

| Method | Path | Handler | Response |
|--------|------|---------|----------|
| `POST` | `/api/orders` | `_handle_order_submit` | `202 {request_id, status}` |
| `GET` | `/api/proof/<token>` | `_handle_proof_page` | Proof review HTML or `403`/`410` |
| `POST` | `/api/proof/<token>/approve` | `_handle_proof_approve` | `200 {status: approved}` |
| `POST` | `/api/proof/<token>/adjust` | `_handle_proof_adjust` | `202 {request_id, status: rendering}` |

### 4. `src/email_delivery.py` — Proof email (MODIFY)

Add `send_proof_email(to, request_id, proof_url)` — sends the proof-ready
notification with the signed review link.

### 5. `web/order.html` — Customer order form (NEW)

Multi-step guided form:
1. **Product** — four cards (digital, animation, print, report)
2. **Location** — state dropdown → county dropdown (populated from config)
3. **Style** — art direction cards (neon-basin, elevation-tint) with previews
4. **Details** — size selector, title/subtitle fields, optional note
5. **Contact** — email field, submit button
6. **Review** — summary of all choices before final submit

Uses `web/shared/hydro-ux.js` for option data. Submits to `POST /api/orders`.
Shows confirmation with request ID on success.

### 6. `web/proof.html` — Proof review page (NEW)

Loaded via signed token URL. Displays:
- Large watermarked proof image
- Title, location, art direction, size
- Source credit line
- "Approve" button → `POST /api/proof/<token>/approve`
- "Adjust & Re-render" button → returns to pre-filled order form
- Expiry notice

### 7. Event log schema

Every state transition and significant action appends to `request.events`:

```json
[
  {"timestamp": "2026-09-16T10:00:00Z", "event": "submitted", "detail": {"product": "digital_image", "region": "Oregon", "county": "Deschutes"}},
  {"timestamp": "2026-09-16T10:00:01Z", "event": "accepted", "detail": {}},
  {"timestamp": "2026-09-16T10:00:02Z", "event": "render_started", "detail": {"job_id": "abc123"}},
  {"timestamp": "2026-09-16T10:05:30Z", "event": "render_completed", "detail": {"job_id": "abc123", "duration_s": 328}},
  {"timestamp": "2026-09-16T10:05:31Z", "event": "proof_ready", "detail": {"proof_url": "...", "expires": "..."}},
  {"timestamp": "2026-09-16T11:20:00Z", "event": "proof_viewed", "detail": {}},
  {"timestamp": "2026-09-16T11:21:00Z", "event": "approved", "detail": {}}
]
```

## Test design (TDD — tests first)

### Unit tests (`tests/test_proof.py`) — NEW

```
test_sign_and_verify_roundtrip          — sign a request_id, verify returns (id, True)
test_expired_token_rejected             — sign with expires_in=0, verify returns (id, False)
test_tampered_token_rejected            — flip a byte, verify returns ("", False)
test_different_secret_rejected          — sign with key A, verify with key B → False
test_watermark_adds_text_element        — SVG output contains <text> with "PROOF"
test_watermark_preserves_original_paths — original <path> elements unchanged
```

### Unit tests (`tests/test_orders.py`) — EXTEND

```
test_revision_requested_transition      — proof_ready → revision_requested is valid
test_revision_to_rendering_transition   — revision_requested → rendering is valid
test_render_failed_transition           — rendering → render_failed is valid
test_render_failed_retry_transition     — render_failed → rendering is valid
test_event_logged_on_transition         — every status change appends to events list
test_event_has_timestamp_and_type       — event structure matches schema
test_multiple_proof_cycles_logged       — submit → proof → revise → proof → approve = 7+ events
```

### Unit tests (`tests/test_server.py`) — EXTEND

```
test_order_submit_returns_202           — valid payload → 202 with request_id
test_order_submit_bad_region_400        — invalid region → 400 with error
test_order_submit_missing_email_400     — no email → 400
test_order_submit_prism_rejected_400    — PRISM art direction → 400 (rights gate)
test_proof_page_valid_token_200         — signed token → 200 with proof HTML
test_proof_page_expired_token_410       — expired token → 410 Gone
test_proof_page_invalid_token_403       — bad signature → 403 Forbidden
test_proof_approve_transitions_order    — POST approve → order status = approved
test_proof_adjust_triggers_rerender     — POST adjust → order status = rendering
test_proof_adjust_preserves_email       — re-render keeps original email
```

### Integration test (`tests/test_order_proof_pipeline.py`) — NEW

```
test_full_order_to_proof_cycle          — submit → auto-accept → render → proof_ready (with fake pipeline)
test_revision_cycle                     — submit → proof → adjust → re-render → new proof
test_event_log_complete_cycle           — all events present after full cycle
test_concurrent_orders_isolated         — two orders don't interfere
```

### E2E test (`tests/e2e/tests/02-order-flow.spec.js`) — NEW (Playwright)

```
test_order_form_loads                   — /order.html loads with product cards
test_order_form_progressive_disclosure  — selecting product reveals location step
test_order_form_county_populates        — selecting Oregon populates county dropdown
test_order_form_submit_happy_path       — fill all fields → submit → see confirmation
test_proof_page_loads_with_token        — proof URL shows watermarked image
test_proof_approve_flow                 — approve button → success confirmation
test_proof_adjust_flow                  — adjust button → pre-filled form → re-submit
```

## File inventory

| File | Action | Description |
|------|--------|-------------|
| `src/proof.py` | CREATE | Signed URLs, watermarking, token verification |
| `src/orders.py` | MODIFY | Extended transitions, event log, `OrderEvent` |
| `src/server.py` | MODIFY | New proof routes, order-form submit handler |
| `src/email_delivery.py` | MODIFY | `send_proof_email` |
| `web/order.html` | CREATE | Multi-step order form |
| `web/proof.html` | CREATE | Proof review page |
| `web/start.html` | MODIFY | Link to order form |
| `tests/test_proof.py` | CREATE | Proof module unit tests |
| `tests/test_orders.py` | MODIFY | Extended state machine tests |
| `tests/test_server.py` | MODIFY | Proof route tests |
| `tests/test_order_proof_pipeline.py` | CREATE | Integration tests |
| `tests/e2e/tests/02-order-flow.spec.js` | CREATE | Playwright e2e |

## Sequencing

Tasks are ordered for TDD: write tests first in each group, then implement.

1. **Group 1: Proof module** (#123 partial) — `test_proof.py` → `src/proof.py`
2. **Group 2: Order state machine** (#120, #125) — extend `test_orders.py` → modify `src/orders.py`
3. **Group 3: Server routes** (#122, #123) — extend `test_server.py` → modify `src/server.py`
4. **Group 4: Email** (#126) — extend `test_email_delivery.py` → modify `src/email_delivery.py`
5. **Group 5: Web UI** (#121, #124) — `web/order.html`, `web/proof.html`
6. **Group 6: Integration** — `test_order_proof_pipeline.py`
7. **Group 7: E2E** — Playwright `02-order-flow.spec.js`

## Open questions

1. **Proof watermark strategy** — SVG text overlay is simple but doesn't protect
   PNG proofs. For PNG, consider a PIL-based watermark in `tools/` (outside
   offline suite). Decision: start with SVG-only proofs (the proof page renders
   SVG); PNG watermarking is Epoch 29+ when payment gates final delivery.

2. **Re-render limit** — Should we cap re-renders? Proposal: 3 re-renders per
   order. After that, email the customer to contact support. Prevents abuse.

3. **Proof secret management** — `HYDRO_ART_PROOF_SECRET` as env var is MVP.
   For production, consider a secrets manager. Decision: env var for now.
