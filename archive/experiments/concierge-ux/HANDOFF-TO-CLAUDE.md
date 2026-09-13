# Claude Handoff — Concierge UX Concept Set

## What is here

The buyer lifecycle also includes `client-confirmation.html` (email-first
waiting state) and `client-delivery.html` (documented final delivery).

`experiments/concierge-ux/` is a linked, static concept set. It is deliberately
not production code and has no backend, persistence, payments, authentication,
or real email service.

| Surface | Audience | Purpose |
| --- | --- | --- |
| `index.html` | All | Entry point and cross-navigation map. |
| `client-product.html` | Buyer | Fine-art-print product detail / expectation-proof before the brief. |
| `client-request.html` | Buyer | Catalog → guided selection → pseudo-proposal. |
| `client-proof.html` | Buyer | No-login proof / approve-or-adjust concept. |
| `ops-dashboard.html` | Operations | Order status, notifications, and work requiring attention. |
| `ops-order.html` | Operations | One-order brief, production checks, recipe, and lineage. |
| `ops-library.html` | Operations | Asset-library concept with privacy/lineage categories. |

The underlying journey and lifecycle are canonicalized in
`agent-os/specs/2026-09-05-customer-operations-experience/spec.md` and
`workflow.mmd`. Read those before changing the concepts or proposing a roadmap.

## Important conclusions preserved by the concepts

1. The buyer is sophisticated about quality but can be technology-novice and
   one-time. The buyer journey therefore begins with an outcome and an example,
   never with technical map settings.
2. No account is required. Email is the order-contact mechanism; private proof
   and delivery links must be signed/expiring, not public guessable URLs.
3. `web/studio.html` is an expert/internal art-direction surface. Do not make it
   the consumer first-touch flow.
4. Product catalog expansion remains **experimental**. Roadmap Epoch 11.5's
   revenue and rights gates still control production commercialization.
5. Customer-provided reference images are private originals. They require a
   separate rights/permission record before any public reuse.
6. Generated proofs/finals are immutable derivatives tied to an order, brief,
   recipe, render job, attribution, and checksum.

## Open items that require decision before roadmap features

Do not turn these into implementation tickets until an owner and decision are
recorded. They are product/operations questions, not coding gaps.

### Commercial model and buyer promise

- Pick the initial sales channel: a direct concierge request, Etsy-style
  marketplace listing, or manually managed email intake. This determines where
  payment, tax, refund, and platform communication rules live.
- Define when `Request` becomes `Order`: at submission, manual review, payment,
  or proof approval. Current concepts intentionally call it a “proposal.”
- Validate the four artifact categories with target buyers. The existing revenue
  validation gate permits a narrow made-to-order county print test, not a broad
  self-serve storefront.
- Set starting price, production lead time, shipping availability, print partner,
  packaging, and damage/reprint/refund policy before presenting them as firm.
- Specify included revision count, what counts as an adjustment, and who can
  authorize an exception. The proof UX currently assumes one bounded adjustment.

### Report and animation claims

- Approve the exact customer-facing claim for “Water story report.” It is a
  historical analytical report, not engineering advice or an investment/flood
  forecast.
- Decide whether a future forecast feature exists at all. If yes, define method,
  uncertainty language, qualified reviewer, liability review, and data source.
- Confirm source/rights policy per artifact at intake. nClimGrid default is
  sellable with attribution; PRISM remains non-sellable without rights.

### Data, identity, and privacy

- Choose a minimal data model and system of record for `Request`, `Order`,
  `ProductionBrief`, `RenderJob`, `Asset`, `ProofReview`, `Delivery`, and
  `CustomerReference`. Preserve immutable IDs proposed in the blueprint.
- Choose storage and a metadata/search layer. Object-store keys must not be used
  as public URLs or as the only asset identifier.
- Define retention/deletion policy for buyer emails, private proofs, and
  customer reference images; include a deletion request process and backup
  behavior.
- Determine consent language and an email provider. Transactional fulfillment
  email must be separable from optional marketing consent.
- Establish signed-link TTL, revocation/reissue process, recipient verification,
  and download logging policy.

### Operations design research

- Observe a coordinator processing 5–10 realistic requests. Validate which
  status states, alerts, filters, and order facts are genuinely needed; do not
  build the dashboard from the visual mock alone.
- Define role boundaries: coordinator, art director, data/rights reviewer,
  production artist, fulfillment owner. For a small team these may be one
  person, but permissions/audit fields should not assume that forever.
- Define the exact QA checklist for each artifact class: geographic correctness,
  visual legibility, title, source credit, dimensions, checksum, privacy,
  rights, and final delivery format.
- Decide which statuses are customer-visible and which remain internal. Raw
  pipeline logs, HUC IDs, cache/source paths, rights flags, and other customers'
  work never cross the boundary.
- Determine the print handoff contract: approved PDF/PNG profile, facility
  receipt, shipment tracking, and failure/reprint handling.

### Technical feasibility and sequencing

- Map a validated internal `Order` payload to `src.fulfillment.build_order` and
  identify fields that need extension rather than duplicating order logic.
- Decide whether experiments should become a small served web application or
  remain static while the pilot runs. Do not introduce a heavyweight stack until
  the operational workflow and sales channel are selected.
- Define idempotency boundaries for request submit, email send, proof approval,
  final export, and delivery. Every external side effect needs a durable event
  record.
- Define an asset lifecycle state machine and enforce allowed transitions:
  private reference → internal preview → private proof → approved final →
  delivered/archived; public catalog publication is a separate explicit action.
- Conduct accessibility review with older users: body text size, contrast,
  obvious action labels, readable pricing, keyboard navigation, and a
  human-support path.

## Recommended research before implementation

1. Five moderated catalog tests with affluent/older, low-technology-comfort
   participants. Success: they can distinguish all artifact types, choose one,
   describe what they receive, and explain what happens after email submission.
2. Five concierge-order dry runs using the proposed operations views. Success:
   an operator can locate every source/proof/final and explain why an asset is
   sellable without searching folders manually.
3. One end-to-end fake order drill: request → intake → brief → existing
   fulfillment executor → proof → approval → delivery → manifest/archive.
   Record each missing field and unsafe handoff.
4. Rights and privacy review of source attribution, customer reference images,
   email/link policy, and report claims.
5. Print vendor evaluation only after the narrow print offer has buyer signal.

## Suggested roadmap gate

Create a development roadmap only after the commercial model, source/rights
policy, data-retention policy, proof/revision rule, and a validated pilot
workflow are decided. The first implementation slice should be the smallest
end-to-end concierge order with one product, one supported geography, one
approved direction, manual payment if needed, and a human review gate—not a
multi-product storefront.
