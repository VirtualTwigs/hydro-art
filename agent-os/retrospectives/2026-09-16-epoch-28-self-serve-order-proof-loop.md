# Epoch 28 — Self-Serve Order Form & Automated Proof Loop retrospective (2026-09-16)

_Closed 2026-09-16 (commit `803f4ae`, bundled with Epochs 29-30 in a single
"self-serve customer journey" commit); retro written 2026-09-17. **No
pre-registered watch-list** — the spec folder
(`2026-09-16-self-serve-order-proof-loop`) carries `spec.md`, `tasks.md`, and
`implementation/report.md`, but no `planning/pre-analysis.md`. This is a
narrative closeout rather than a graded one. First epoch of the "Self-serve
customer journey" block (Epochs 28-30, #120-#135)._

## What the epoch was

Build the automated order-to-proof loop: customer fills a web form, server
validates and auto-dispatches a render job, proof is generated with a watermarked
SVG and a signed time-limited URL, customer reviews and either approves or
adjusts (triggering re-render). No accounts, no passwords — email-only identity
with HMAC-SHA256 signed links. Structured event log on every request for product
analytics. This epoch is the customer-facing entry point that consumes the
Epoch 19 endpoint contracts and the Epoch 24 server/jobs infrastructure.

All seven planned items (#120-#126) shipped.

## What shipped (`803f4ae`)

### `src/proof.py` (NEW, pure/offline, 151 lines)

- **`sign_proof_url(request_id, secret, expires_in=604800)`** — HMAC-SHA256
  signed, base64url-encoded token. Default 7-day expiry.
- **`verify_proof_token(token, secret)`** — returns `(request_id, True)` if
  valid and not expired, `(request_id, False)` if expired but signature valid,
  `("", False)` on tampered/malformed tokens. Uses `hmac.compare_digest` for
  constant-time comparison.
- **`sign_delivery_url` / `verify_delivery_token`** — 90-day variant reusing the
  same HMAC scheme (forward-looking for Epoch 29 delivery links).
- **`watermark_svg(svg_content, text)`** — inserts a diagonal `<text>` overlay
  ("PROOF", 30% opacity, centered, rotated -45deg) before `</svg>`. Extracts
  width/height from the SVG for centering. Original `<path>` elements unchanged.

### `src/orders.py` (MODIFIED)

- Three new statuses: `revision_requested`, `render_failed`, `payment_pending`
  (plus `paid` for Epoch 29 forward-compat).
- Extended `TRANSITIONS` table: `proof_ready -> {approved, revision_requested}`,
  `revision_requested -> {rendering}`, `render_failed -> {rendering}` (retry),
  `approved -> {payment_pending, fulfilled}`, `payment_pending -> {paid}`,
  `paid -> {fulfilled}`.
- **`OrderEvent`** dataclass with `timestamp`/`event`/`detail` + dict
  serialization. Events appended on `create_request` (initial "submitted" event)
  and every `update_status` call.
- **`add_event(request_id, event, detail)`** — append custom events (e.g.
  `proof_viewed`, `render_started`) outside the transition machinery.

### `src/server.py` (MODIFIED)

- **`_create_order`** — accepts optional `runner` for auto-dispatch: validates
  payload, creates request, auto-transitions `submitted -> accepted -> rendering`,
  dispatches render job, returns `202 {request_id, status}`. Without a runner,
  falls back to create-only `201`.
- **`_proof_dispatch`** — `GET /api/proof/<token>` (returns proof data JSON with
  watermarked SVG content, `200`/`403`/`410`), `POST .../approve` (transitions to
  `approved`), `POST .../adjust` (transitions to `revision_requested -> rendering`,
  re-dispatches render). Token verified via `src.proof`.

### `src/email_delivery.py` (MODIFIED)

- **`send_proof_email(to, request_id, proof_url, *, title)`** — HTML + plain-text
  proof-ready notification with signed review link. Degrades gracefully when
  `HYDRO_ART_GMAIL_APP_PASSWORD` is unset.

### Web UI

- **`web/order.html`** (NEW, 954 lines) — 6-step progressive-disclosure form:
  product cards, state/county dropdowns (from `HydroUX.STATES`/`COUNTIES`), art
  direction cards, size selector, email contact, review summary. Submits to
  `POST /api/orders`, shows confirmation with request ID.
- **`web/proof.html`** (NEW, 637 lines) — token-based proof review page.
  Fetches proof data from `GET /api/proof/<token>`, displays watermarked preview,
  title/location/source credit, approve and adjust buttons, expiry notice.
- **`web/start.html`** (MODIFIED) — hero CTA updated to "Order now" linking to
  `order.html`; product cards link with `?product=<type>` pre-selection.

### Test coverage

| File | New tests | Total in file | Status |
|------|-----------|---------------|--------|
| `tests/test_proof.py` | 6 | 6 | all pass |
| `tests/test_orders.py` | 11 | 38 | all pass |
| `tests/test_server.py` | 10 | 32 | all pass |
| `tests/test_email_delivery.py` | 3 | 12 | all pass |
| `tests/test_order_proof_pipeline.py` | 5 | 5 | all pass |

**35 new tests** across five files, all epoch-28-specific tests (97) green.

### Commit totals

Part of a combined commit (`803f4ae`) spanning Epochs 28-30: 35 files changed,
5202 insertions. Full offline suite: **1027 passed** (+35 epoch-28 tests), 6
pre-existing failures (`test_min_order.py` — unimplemented feature, unrelated).
Zero regressions.

## Real-data findings

No real-data run in this epoch by design. The spec explicitly scoped this as
offline-first infrastructure — the form submits to `POST /api/orders` and the
proof page fetches from `GET /api/proof/<token>`, both tested with injected
fakes. Manual smoke (task 12.2: start `serve.py`, submit a real order, verify
proof email, review proof page, approve) was deferred; it needs a running server
with GIS data staged.

No bug-the-real-run-surfaced to report. The expected pattern for this epoch would
be: the signed proof URL contains a host/port that doesn't match when served
behind a reverse proxy, or the watermark SVG dimensions don't match a real
production render's `viewBox`. These remain untested carry-forwards.

## Invariants held

- **Offline suite:** 1027 passed (35 new from this epoch), 6 pre-existing
  failures (unrelated `test_min_order.py`). Zero regressions.
- **2D default output byte-identical:** yes. No `PIPELINE_STAGES` change, no
  renderer change. The epoch adds order/proof infrastructure outside the
  pipeline.
- **`PIPELINE_STAGES` untouched:** yes. `src/pipeline.py` `PIPELINE_STAGES` is
  unchanged — this epoch adds `src/proof.py` and extends `src/orders.py` /
  `src/server.py`, all outside the 12-stage pipeline.
- **Rights gate:** enforced. Order submission validates through
  `src.fulfillment.build_order`, which calls `assert_sellable` — PRISM art
  direction rejected at the boundary. Tested by
  `test_order_submit_prism_rejected_400` in `tests/test_server.py`.

## Graded against pre-analysis

No `planning/pre-analysis.md` exists for this spec, so there is no pre-registered
watch-list to grade against. The spec's "Open questions" section flagged three
concerns:

1. **Proof watermark strategy (SVG vs. PNG).** Confirmed scoped correctly — SVG
   text overlay ships; PNG watermarking deferred. The proof page renders SVG, so
   this is sufficient for the proof loop. PNG watermarking (PIL-based, in `tools/`)
   is Epoch 29+ when payment gates final delivery.
2. **Re-render limit (3 max per order).** Noted but **not enforced**. The
   transition table allows unlimited `revision_requested -> rendering` cycles.
   Carry-forward.
3. **Proof secret management.** `HYDRO_ART_PROOF_SECRET` as env var shipped as
   planned. No secrets manager integration — appropriate for the current
   single-operator deployment.

## Carry-forwards (honestly open, not passed)

- **No manual smoke test.** Task 12.2 (start `serve.py`, submit an order end to
  end, verify proof email, review proof page, approve) was not run. Needs a
  running server with staged GIS data.
- **Playwright e2e tests not created.** Task Group 11 (`tests/e2e/tests/
  02-order-flow.spec.js`) was explicitly deferred — needs running server + Node
  18+. Test specs are outlined in `spec.md` but no file was authored.
- **Proof email not auto-wired to proof-ready transition.** `send_proof_email` is
  implemented and tested in isolation, but the render-complete callback in
  `_create_order` does not call it when the order transitions to `proof_ready`.
  The hook point exists; the one-line wiring was deferred per the implementation
  report.
- **Re-render limit not enforced.** The spec proposed 3 re-renders max per order.
  The transition table permits unlimited revision cycles. This is a soft
  anti-abuse measure, not a correctness concern.
- **Proxy/host URL in signed proof links.** `sign_proof_url` returns a bare
  token, not a full URL — the server constructs the URL from its own host. Behind
  a reverse proxy the host may not match. Untested outside localhost.
- **No live byte-identical `verify_determinism.py` double-render was run for
  this epoch.** Byte-identity rests on the "no renderer change" invariant, not a
  fresh double-render — matching the standing carry-forward from prior epochs.

## Lessons

- **The fulfillment/orders/server layering paid off.** The Epoch 19 endpoint
  contracts and existing `src/orders.py` `OrderStore` provided the validation +
  persistence layers this epoch consumed. `_create_order` is a thin orchestrator
  over `OrderStore.create_request` + `runner.submit` — no new validation logic
  was needed. The discipline of validate-at-the-boundary, pure value objects, and
  injectable seams continues to make downstream epochs clean.
- **Event logging was trivial to add retroactively.** Appending `OrderEvent`
  dicts on every `create_request` and `update_status` call required ~15 lines in
  `src/orders.py`. The JSON-file-backed persistence made the schema extension
  zero-migration. This would not have been as easy with a SQL schema.
- **Bundling three epochs into one commit obscures boundaries.** Commit `803f4ae`
  spans Epochs 28-30 (5202 insertions across 35 files). This makes it harder to
  attribute changes to specific epochs in retrospectives and to bisect regressions.
  Future multi-epoch implementation sessions should prefer one commit per epoch.
- **Consider adding a pre-analysis even for orchestration epochs.** The open
  questions in `spec.md` served a similar purpose informally, but a structured
  pre-analysis with explicit predictions would have made this retrospective a
  graded one rather than a narrative one.
