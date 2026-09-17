# Hydro-Art Product Audit

## Executive conclusion

Hydro-Art has a credible and unusually mature **rendering engine**: deterministic
GIS-to-SVG generation, four output endpoints, rights-aware provenance, offline
test discipline, and a visually coherent public surface. The current product is
not yet ready to operate as a public direct-to-customer commerce service. The
central gap is not additional visual capability. It is a safe, truthful,
measurable path from a visitor to a paid, fulfilled order.

The product should therefore make one near-term choice: validate a narrow,
manually fulfilled county-print offer before investing in CONUS rendering,
facility intelligence, self-service configuration, or a broader catalog. This
does not discard those investments. It sequences them behind evidence that a
buyer wants the current core offer and behind security controls required for any
customer data or private artwork.

The audit finds five issues requiring action before a public commerce launch:

1. Customer order, proof, and delivery endpoints have no authorization or
   expiring capability control, despite public-facing pages and predictable order
   identifiers.
2. Customer-controlled values are interpolated into HTML with `innerHTML`,
   creating stored cross-site scripting exposure for staff and customers.
3. The marketing funnel, product promises, fulfillment capability, and product
   documentation contradict one another.
4. The revenue experiment has not started—ledger values are zero—yet the roadmap
   gives more engineering work a higher practical priority than the experiment.
5. The main hydrography source strategy needs a 3D Hydrography Program migration
   plan; USGS has moved legacy NHD/WBD/NHDPlus HR products to static/reference
   status.

The audit corrected two objective planning defects in `agent-os/product/roadmap.md`:
the water-intelligence work is now **Epoch 27 / #112–#119** rather than duplicating
CONUS Epoch 26 IDs, and the revenue-gate timing is correctly measured from actual
listing go-live rather than an already-expired planning date.

## Product definition and strategic choice

Hydro-Art currently describes two different products.

| Product model | Evidence in the repository | What it optimizes for | Conflict |
| --- | --- | --- | --- |
| Made-to-order art service | Landing page, order/proof/delivery pages, fulfillment tool, revenue gate | Emotional place attachment, a concise buying decision, dependable fulfillment | Requires commerce operations, private access control, proof/revision policy, and customer support |
| GIS/art tooling platform | Mission, PRD, CLI, deterministic pipeline | Expert configurability, editable data products, broad geography | Requires developer documentation, data migration strategy, support boundaries, and a different acquisition/pricing model |
| Facility/data-center intelligence | Proposed Epoch 27 | Evidence-backed research and institutional analysis | Requires state adapters, claim review, display rights, and domain expertise; it is not a lightweight art add-on |

The first two models can coexist internally, but the external entry point must
choose one primary promise. The repository’s revenue gate and customer blueprint
make the correct near-term wedge clear: **a made-to-order county watershed print
for a meaningful place in OR/WA/CA/ID**.^1 The website should be evaluated against
that promise, not against an implied future self-service platform.

Facility intelligence is a possible second business line, but it should not be
used to justify expanding the customer catalog before it has an identified buyer,
interviews, a source-rights review, and a paid pilot. Its cost structure and
evidence standard are closer to a research service than to a consumer wall-art
upsell.

## Customer journey audit

### What works

- The landing page clearly presents a visual product, shows real examples, and
  offers a concise no-account narrative.
- The four endpoint model—digital image, print image, animation, and report—is
  technically documented and has a common provenance/rights concept.^2
- A guided request UI, an order state model, operations page, proof page, and
  delivery page exist in the current web surface.
- The browser and pipeline test evidence is meaningful: on September 13, 2026,
  the normal Python suite passed **932 tests** and the two Node suites passed
  **19 tests**. This demonstrates a strong offline regression baseline, not a
  public-launch certification.^3

### Funnel defects

The landing page’s primary calls to action route visitors to prototype/design
surfaces (`proto-b-guided.html`, `report.html`, `studio.html`) rather than the
implemented guided request page (`order.html`). The result is a split funnel:
marketing communicates a made-to-order service, while primary clicks lead to
expert/prototype experiences that do not create a proposal.

The promised and actual offer also diverge:

| Public or operational statement | Current implementation evidence | Required correction |
| --- | --- | --- |
| “Archival poster,” “framed on request,” and four priced product cards | The fulfillment guide says physical fulfillment is not operational; the real fulfillment command supports PNG/PDF and only the neon-basin county path | Either sell only a digital proof/print-ready-file offer or establish print vendor, shipping, damage/refund, and production SLA before making physical claims |
| “One free revision” | The UI can transition a proof back to `submitted`, but no revision count, scope rule, or approval audit exists | Define an included revision count and what qualifies; enforce it in the request/brief model |
| “Place an Order” and “Track your order” | No payment policy, payment collection, tax handling, refund policy, or binding-order rule exists | Rename to “Request a proposal” until an actual purchase policy exists |
| “No account needed” | Correct goal, but private links are currently guessable request IDs rather than signed capabilities | Retain no-account design, replace IDs with scoped, expiring tokens |
| Report product price and sales copy | Product guide says reports are historical analysis, not forecasts; no customer-report scope/review workflow exists | Keep reports out of the first paid offer or sell only a manually reviewed research brief with explicit limitations |

The existing operations guide already recognizes many of these as proposed or
unresolved. It is now stale against the recently implemented local order flow,
which creates a second problem: staff cannot tell whether a page is an internal
demo, a local operational tool, or a safe public customer surface.^4

## Launch-blocking security and privacy findings

The following findings apply if `serve.py` or its order routes are reachable by
anyone other than a trusted local operator. The deployment documentation correctly
states that the server has no authentication or TLS; the product roadmap and
customer pages must preserve that local-only boundary until the findings are
remediated.^5

| Severity | Finding | Evidence | Required remediation |
| --- | --- | --- | --- |
| P0 | Any caller can list all orders and retrieve a full order by predictable `REQ-YYYYMMDD-NNNN` ID, including email address and job ID | `GET /api/orders`, `GET /api/orders/<id>` in `src/server.py`; sequential IDs in `src/orders.py` | Split staff and customer APIs; require staff authentication for lists/mutations; use high-entropy, scoped, expiring customer capability tokens; never return email to customer views |
| P0 | Any caller can transition an order, start a render, approve a proof, or mark fulfillment | Unauthenticated `POST`/`PATCH /api/orders/...` handlers | Authenticate staff mutations; make customer approval a single-purpose signed token with an idempotency record; do not expose fulfillment mutation to buyer tokens |
| P0 | Delivery treats `approved` as ready and exposes download controls before actual fulfillment | `web/delivery.html` defines ready as `approved` or `fulfilled` | Permit download only from a recorded delivery authorization after `fulfilled`; separate proof preview from final asset delivery |
| P0 | Stored XSS is possible because request fields and email are concatenated into `innerHTML` | `web/proof.html`, `web/delivery.html`, and operations UI; server only requires non-empty email/product | Build DOM with `textContent`/safe templates, validate input size and format server-side, sanitize any SVG preview, add regression tests using HTML payloads |
| P1 | Localhost delivery URL is hard-coded into sent email | `src/server.py` builds `http://localhost:8765/delivery.html?...` | Use a configured canonical public origin and tokenized URL; fail closed if production delivery configuration is absent |
| P1 | Concurrent submissions can reuse a request sequence | `OrderStore.create_request()` releases its lock after allocating sequence and before `_write()`; HTTP server is threaded | Allocate/write under one lock, preferably use UUID/capability IDs and atomic file creation; test concurrent creation |
| P1 | Request IDs are not validated before becoming filesystem path components | `_path(request_id)` interpolates the route value into a path | Enforce exact ID format at every API boundary; reject separators and noncanonical IDs; test traversal attempts |
| P1 | No request-size cap, abuse throttle, bot control, security headers, or incident plan | Standard-library request handler reads declared body; no rate/access controls | Add a reverse proxy or managed application boundary, TLS, body limits, rate limiting, logging, CSP and related headers, privacy policy, and incident-response runbook |

No payment data should be collected by this service. Use a marketplace or a hosted
payment provider for the initial experiment. The FTC advises businesses to collect
only what is needed, protect it, dispose of it appropriately, and plan for a
security incident; these principles are directly relevant to emails, customer
references, proof assets, and delivery links.^6

## Technical and data-product audit

### Rendering engine

The core architecture is a strength: heavy GIS work is lazy/`tools`-side, core
logic is testable offline, and determinism/provenance are first-class concepts.
The offline suite’s 60 warnings do not fail tests, but they show why the release
claim needs careful wording: mocked/integration paths can proceed without WBD
boundary layers and without SVGO. Real GIS, cross-device, and multi-tile checks
remain explicitly open in the correction backlog.^7

The release materials should distinguish:

```text
offline regression green  ≠  real-data reproducibility observed  ≠  public commerce ready
```

The current correction roadmap already contains the right real-environment work:
live determinism, all-endpoint reproducibility, Census shape staging, and browser
verification. It is a parallel backlog, however, and the primary roadmap’s open
table does not surface its most material blockers. That split creates status
drift risk.

### Hydrography source lifecycle

NHDPlus HR is usable and public-domain, but it is not a future-maintained source.
USGS says that in 2024 it shifted from maintaining NHD, WBD, and NHDPlus HR to 3D
Hydrography Program products; legacy products are available as reference downloads
and services while 3DHP is populated.^8 The existing pipeline should retain pinned
legacy snapshots for reproducibility, but a **3DHP compatibility discovery track**
is now needed before broad regional expansion or a CONUS flagship becomes a core
commercial asset.

Do not silently change a source in customer reorders. A render recipe must include
source family, release/version/DOI, acquisition date, and any compatibility
adapter version. The migration can initially be read-only: compare a selected
basin’s topology, feature classification, visual density, and reproducibility
before changing production defaults.

### CONUS rendering

The updated roadmap correctly identifies graph memory, full-string SVG generation,
and boundary-union cost as CONUS blockers. The recommended architecture sequence
is sound: filter before graph construction, add a streaming writer, then introduce
CONUS wiring and a constrained hero render. This is a **marketing asset project**,
not evidence of customer demand. Keep it after the narrow listing is live unless
it is explicitly time-boxed as a single asset with a measurable acquisition role.

### Water-facility intelligence

The Epoch 27 data model is much more responsible after claim-level evidence,
bitemporal data, display eligibility, and quality alerts were added. Its primary
risk is commercial distraction. It should enter build only when one of these is
true:

- a current buyer requests an evidence-backed facility overlay and accepts a
  manual-research price;
- three to five institutional buyer interviews identify a repeated paid job; or
- a funded partnership supplies a source, rights, and review owner.

Until then, maintain the research and pilot-source catalogue, not a nationwide
production database. The national sources can establish infrastructure context;
they cannot establish site-level data-center water consumption without specific
state, utility, permit, or owner evidence.

## Roadmap audit and corrected sequence

### Corrections made

- The original duplicate Epoch 26 and duplicate #107–#111 assignments were
  corrected. CONUS remains Epoch 26/#107–#111; water intelligence is Epoch
  27/#112–#119.
- The false fixed revenue deadline was replaced. The 60-day gate begins when the
  listing actually goes live, not when planning began.

### Gaps that remain in the primary roadmap

1. **No public-commerce security milestone precedes customer pages.** Add a
   non-negotiable launch gate before any public direct order/proof/delivery use.
2. **No explicit product-definition decision.** Add a one-page offer contract:
   who the first buyer is, exact deliverable, starting price, lead time, one
   included revision, what is excluded, and where payment happens.
3. **No legal/operational launch checklist.** Add privacy notice, terms, refunds,
   print/vendor responsibility, customer-reference license, tax/marketplace
   decision, and source attribution review.
4. **Corrections backlog is detached.** Promote C1 process discipline and C4
   real-data/release verification into the main open-items table or add a linked
   “release blockers” section that cannot be skipped.
5. **No source-migration track.** Add the 3DHP discovery/compatibility milestone
   before committing to nationwide source acquisition.
6. **No decision gate before Epoch 27.** Add a buyer-evidence gate for facility
   intelligence so it is not built solely because it is technically interesting.

### Recommended execution order

| Priority | Decision or work | Exit criterion |
| --- | --- | --- |
| 0 | Reclassify current order/proof/delivery surface as local/internal only | No public links or public deployment; documentation says so consistently |
| 1 | Publish the narrow marketplace listing and fulfillment pack | A buyer can pay through a marketplace; every promise maps to a tested/manual operating step |
| 2 | Begin the 60-day instrumented revenue experiment | Ledger captures actual views, inquiries, paid orders, fees, turnaround, refunds, and reasons for nonpurchase |
| 3 | Repair the public-commerce boundary | Authenticated staff, tokenized customer access, privacy controls, safe rendering, final-delivery authorization, and security review pass |
| 4 | Execute real-data/reproducibility blockers | Real host evidence closes C4 and release status is reconciled |
| 5 | Decide based on evidence | Pass: scale the winning offer; fail: conduct the planned ten interviews and run one revised test |
| 6 | Pursue CONUS, source migration, or facility intelligence | Only where it supports the proven offer or a separately validated buyer/job |

## Metrics and decision system

The revenue ledger is a good start but needs decision-quality definitions.

| Metric | Definition | Why it matters |
| --- | --- | --- |
| Qualified listing visit | A marketplace visitor who reaches the full listing after page load | Separates passive impressions from consideration |
| Inquiry rate | Unique pre-purchase questions / qualified visits | Tests comprehension and trust |
| Paid conversion | Paid orders / qualified visits | Primary proof of demand |
| Gross margin contribution | Payment received minus marketplace, payment, print, shipping, packaging, and direct rework costs | Gross revenue alone can endorse an unprofitable offer |
| Median elapsed fulfillment | Payment-to-delivery hours, separately recording human minutes | Tests whether 24–48 hour promise and <45 min target are compatible |
| Revision rate | Orders needing revision / proofs sent, plus reason taxonomy | Identifies expectation-proof and intake failures |
| Refund/cancellation rate | Refunds or cancellations / paid orders, with reason | Tests product-market fit and operational reliability |
| Reorder/referral signal | Explicit referral source or second purchase | Stronger quality signal than a like or save |

Pre-register a stop rule as well as a scale rule. If the first test receives
enough qualified visits but no paid orders, do not add features; change one offer
variable—example quality, product framing, price, turnaround, or niche—and run a
second bounded test. If it receives too few qualified visits, the finding is about
distribution rather than product demand.

## Documentation corrections required

The documentation should have one clear status matrix. Today, the operations guide
and administrator guide label the customer lifecycle as prototype/proposed, while
the repository includes a committed local order implementation. Neither statement
is sufficient alone.

Use these labels consistently:

| Surface | Correct current label |
| --- | --- |
| GIS pipeline, fulfillment command, offline tests | Implemented; real-data verification still partially open |
| Static demo container | Internal demo only; no live rendering, auth, or orders |
| `serve.py` + order/proof/delivery endpoints | Local/internal experiment only; prohibited from public deployment |
| Marketplace listing and paid customer workflow | Not launched |
| Signed delivery, payment, print fulfillment, privacy/terms | Not implemented / launch blockers |
| Facility intelligence | Research and proposed roadmap only |

## Sources

[^1]: Hydro-Art. [“Product Roadmap.”](../agent-os/product/roadmap.md) Accessed September 13, 2026; Hydro-Art. [“Revenue Validation Ledger.”](../agent-os/product/revenue-ledger.md) Accessed September 13, 2026.
[^2]: Hydro-Art. [“Production Endpoint Contracts & Hardening.”](../agent-os/specs/2026-09-05-production-endpoint-contracts/spec.md) Accessed September 13, 2026.
[^3]: Hydro-Art local validation: `.venv/bin/python -m pytest -q` (932 passed, 60 warnings), `node tests/test_recipe_roundtrip.cjs` (11 passed), and `node tests/test_report_helpers.cjs` (8 passed), September 13, 2026.
[^4]: Hydro-Art. [“Operations & Customer Usage Guide.”](operations-and-customer-guide.md) Accessed September 13, 2026; Hydro-Art. [“Customer-to-Operations Experience Blueprint.”](../agent-os/specs/2026-09-05-customer-operations-experience/spec.md) Accessed September 13, 2026.
[^5]: Hydro-Art. [“Internal Test Deployment (Static).”](../deploy/README.md) Accessed September 13, 2026; Hydro-Art. [`src/server.py`](../src/server.py), [`src/orders.py`](../src/orders.py), and [`serve.py`](../serve.py), accessed September 13, 2026.
[^6]: U.S. Federal Trade Commission. [“Protecting Personal Information: A Guide for Business.”](https://www.ftc.gov/business-guidance/resources/protecting-personal-information-guide-business) Accessed September 13, 2026.
[^7]: Hydro-Art. [“Corrections Roadmap.”](../agent-os/product/corrections-roadmap.md) Accessed September 13, 2026.
[^8]: U.S. Geological Survey. [“Access 3DHP Data Products.”](https://www.usgs.gov/3d-hydrography-program/access-3dhp-data-products) Accessed September 13, 2026; U.S. Geological Survey. [“About National Hydrography Products.”](https://www.usgs.gov/national-hydrography/about-national-hydrography-products) Accessed September 13, 2026.
