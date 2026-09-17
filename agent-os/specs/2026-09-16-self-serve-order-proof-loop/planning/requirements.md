# Requirements — Self-Serve Order Form & Automated Proof Loop

**Epoch:** 28
**Date:** 2026-09-16
**Status:** planning

## Problem

The existing pipeline produces museum-quality hydrographic art, but there's no
automated way for a customer to order and receive it. Today's flow is concierge:
manual intake, manual render, manual proof delivery. The customer-operations
blueprint (2026-09-05) designed the UX and state model but left implementation
to future epochs.

Customers should be able to:
1. Choose a product (digital/print/animation/report)
2. Customize it (region, county, art direction, size, title)
3. Submit a request with their email (no account)
4. Receive an automated proof via a signed link
5. Accept or adjust settings and re-render
6. All lifecycle events are logged for product improvement

## Constraints

- **No user accounts or auth.** Email is the sole identifier. No passwords,
  OAuth, sessions, or profiles. Proof/delivery links are signed (HMAC + expiry).
- **Offline-suite discipline.** All new `src/` modules must be testable without
  GDAL, network, or database. Existing offline tests must stay green.
- **Pipeline byte-identity.** No change to `PIPELINE_STAGES` or default render
  output. The order/proof system is a wrapper around the existing pipeline.
- **Deterministic.** Same order payload → same render output → same proof.
- **Rights gate.** Every order validated through `src/fulfillment.py` before
  render. No PRISM-derived assets.
- **Progressive disclosure.** No GIS jargon in customer-facing UI. Region →
  county → art direction → size, not HUC/EPSG/FType.

## Existing code to build on

| Module | What it provides | What's needed |
|--------|-----------------|---------------|
| `src/orders.py` | `OrderStore`, `Request`, state machine (submitted→fulfilled), JSON persistence, thread-safe | Extend transitions for re-render loop; add event log; wire to render queue |
| `src/server.py` | HTTP API (`/api/orders`, `/api/render`, `/api/jobs`), static file serving, path-traversal guard | New routes: `POST /api/orders/submit`, `GET /api/proof/<token>`, `POST /api/proof/<token>/approve`, `POST /api/proof/<token>/adjust` |
| `src/fulfillment.py` | `build_order()`, rights gate, deliverable planning, attribution | Validation for order-form payloads |
| `src/jobs.py` | `JobRunner`, job lifecycle, artifact storage | Wire accepted orders → job dispatch |
| `src/email_delivery.py` | `send_confirmation_email`, `send_delivery_email` | Add `send_proof_email` with signed link |
| `src/config.py` | `SUPPORTED_REGIONS`, palette/size allowlists, `build_settings` | Source of truth for form validation |
| `web/start.html` | Landing page, product catalog, pricing | Link to order form |
| `web/shared/hydro-ux.js` | Option data, recipe encode/decode | Power the order form's dynamic options |

## User stories

1. **As a customer**, I visit the site, choose "Digital Image", select Oregon /
   Deschutes County with neon-basin art direction at 4096px, enter a title and
   my email, and submit. I receive a confirmation email with my request ID.

2. **As a customer**, I receive a "proof ready" email with a link. I click it
   and see a watermarked preview of my art, the title, source credit, and two
   buttons: "Approve" and "Adjust & Re-render."

3. **As a customer**, I don't like the title. I click "Adjust", change it, and
   re-submit. A new render starts and I get a new proof link.

4. **As a customer**, I approve the proof. (In Epoch 29, this triggers payment.
   In Epoch 28, approval is recorded and the order moves to "approved" state.)

5. **As a product owner**, I can query the event log to see: how many orders per
   product type, proof acceptance vs. revision rate, average render time, and
   which regions/counties are most requested.

## Non-goals (Epoch 28)

- Payment (Epoch 29)
- Print vendor integration (Epoch 30)
- Custom trip overlay / GPX upload (Epoch 29)
- User accounts, login, order history
- Admin panel / operations queue UI
- Database migration (JSON store is sufficient for MVP)

## Success criteria

1. A customer can complete the full form → submit → proof → approve/revise cycle
   without creating an account.
2. Proof links are signed and expire (default 7 days).
3. Re-render creates a new proof without losing the prior proof record.
4. Every state transition is logged as a structured event.
5. The offline test suite remains green with ≥90% coverage on new `src/` code.
6. Playwright e2e test covers the happy path (submit → proof → approve).
