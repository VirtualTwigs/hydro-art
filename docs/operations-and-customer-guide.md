# Operations & Customer Usage Guide

A complete, plain-language guide to the two sides of Hydro-Art's made-to-order
service: the **Customer** (a buyer who wants a finished piece of a meaningful
place) and **Operations** (the staff who turn that request into a reproducible,
rights-cleared, delivered artifact).

This guide is the practical companion to the design blueprint in
`agent-os/specs/2026-09-05-customer-operations-experience/spec.md` and the
cradle-to-grave flowchart in that spec's `workflow.mmd`. Read the blueprint for
*why*; read this for *how to use it today*.

> **Just want one rendered image, end to end?** See
> `docs/end-to-end-first-image.md` — a hands-on runbook for the live
> form → job → processing → image path (`serve.py` + `web/studio.html`), plus
> the CLI equivalent and how to produce a watershed report.

---

## How to read this guide

Every capability is tagged so no one over-promises:

- **[Works today]** — implemented, offline-tested code you can run right now
  (the deterministic pipeline, `src.fulfillment`, `tools/fulfill_order.py`,
  determinism/release gates).
- **[Prototype]** — a static, click-through concept under `experiments/`. No
  backend, no persistence, no payments, no real email. Use it for demos, buyer
  research, and design review — not for live orders.
- **[Proposed]** — described in the blueprint, not built. Do not present it to a
  customer as if it exists.

### The one guardrail that overrides everything

The only commercially validated offer is a **made-to-order county watershed
print** in Oregon, Washington, California, or Idaho, using **public-domain
sources only**. The four-product catalog and every customer/ops web surface are
**experiments and information architecture** — they are *not* authorization to
launch a self-serve storefront, expand geography, or sell the animation/report
products before the Epoch 11.5 revenue and rights gates pass. When in doubt,
sell nothing that `src.fulfillment.assert_sellable` would reject.

---

# Part 1 — Customer guide

## What Hydro-Art is (and isn't)

You come with a **place, a memory, a room, or a question** — not a GIS project.
You choose an outcome, see a credible example of what to expect, and submit an
email-backed request. **No account, no password, no dashboard.** Your email is
only an order-contact identifier; it is never turned into a login or marketing
list by implication.

## The four things you can order

| Product | What you get | Options | Starting price* | What it is **not** |
| --- | --- | --- | --- | --- |
| **Digital image** | A high-resolution personal map image of a place. | Place, art direction, title, digital size. | from $38 | Not an editable GIS/source file by default. |
| **Moving water study** | A short, elegant view of seasonal or historical change. | Place, time framing, art direction, GIF/MP4. | from $64 | Not a live forecast or real-time monitor. |
| **Fine-art print** | An archival map print made for a room and kept for years. | Place, art direction, size, title. | from $110 | No physical shipment is promised until print fulfillment is operational. |
| **Water story report** | A researched visual explanation of how a watershed has behaved over time. | Watershed/place, historical framing, optional question. | from $95 | Not engineering advice or an investment/flood **forecast**. |

\* Price hypotheses from the blueprint — confirm current pricing before quoting.

> **"Forecast" is never promised.** The report is *historical analysis plus
> questions worth monitoring* — never a prediction. Say it that way to buyers.

## Your journey, step by step

Each moment does exactly one job, so you never meet map settings before you
understand the outcome.

1. **Discover** — a splash page: one sentence about the offer + one labeled
   example. *"What is this?"*
2. **Orient** — the artifact catalog: four cards, each with an example, use
   case, included delivery, starting price, lead time, and one plain limitation.
   *"What can I receive?"*
3. **Imagine** — a product-detail / *expectation-proof* page: at least three
   examples at the same scope, titled "example of art to expect," explaining
   what varies by place and what stays consistent. *"Will it resemble what I
   want?"*
4. **Personalize** — a guided brief: pick a location, a small curated
   art-direction set, a title/subtitle preference, and a few product-specific
   choices. No palette codes, HUC numbers, gamma, or file-format jargon.
5. **Commit lightly** — a proposal cart: one aligned summary with price, likely
   delivery window, an example thumbnail, and editable choices. It is called a
   **proposal** (not a paid order) until a payment policy exists.
6. **Identify** — an email request: email, name, optional note. A marketing
   consent box appears *only* if you opt in.
7. **Reassure** — a confirmation page + email with a **Request ID**, a compact
   summary, one art example, the expected next contact, and a reply-to address.
8. **Approve** — a **proof review link**: a large watermarked proof, a
   production summary, the source-credit line, and simple *Approve* / *Request
   adjustment* choices. The link is signed, expires, and needs no login.
9. **Receive** — a delivery email / download page: your files or a fulfillment
   notice, plus size/format, title, date, attribution, license, and "keep this
   link" language.

## What you will and won't see

You receive a clear description, your chosen title, the source-credit line, and
the approved proof. You will **never** be shown the machinery — source file
paths, cache locations, watershed (HUC) IDs, raw QA notes, checksums, pipeline
arguments, or any other customer's work.

## Try the customer prototypes  **[Prototype]**

Open these in a browser (they are `file://`-safe — just double-click):

| Page | What it demonstrates |
| --- | --- |
| `experiments/concierge-ux/index.html` | Entry point + map of the whole concept set. |
| `experiments/concierge-ux/client-product.html` | Fine-art-print detail / expectation proof. |
| `experiments/concierge-ux/client-request.html` | Catalog → guided selection → pseudo-proposal. |
| `experiments/concierge-ux/client-confirmation.html` | Email-first "we've got your request" waiting state. |
| `experiments/concierge-ux/client-proof.html` | No-login proof, approve-or-adjust. |
| `experiments/concierge-ux/client-delivery.html` | Documented final delivery. |
| `experiments/shop.html` | Earlier catalog / pseudo-cart interaction prototype. |

These are concepts for research and demos. They do not submit anything, send
email, or take payment.

---

# Part 2 — Operations guide

Operations turns an incomplete email proposal into an **archived, reproducible,
rights-cleared asset with a delivery outcome**. The success test: *any delivered
artifact can be located, explained, regenerated, and audited* from a Request ID,
Order ID, or Asset ID.

## The lifecycle you own

```
Request → (scope & rights valid?) → Order → Production brief → Render recipe
  → Render/export job → (visual & provenance QA?) → Asset library
  → Proof email + review link → (buyer approves?) → Deliver / print handoff
  → Archive manifest & outcome
```

Rejections loop back: failed scope/rights → clarify or decline; failed QA →
re-brief; revision requested → re-brief.

## Phases, owners, and required checks

| Phase | Owner | Required checks | Output |
| --- | --- | --- | --- |
| **Intake** | Coordinator | Contactability; product availability; geography; completeness; duplicate detection. | `Request` record + triage status. |
| **Scope & rights** | Coordinator + data lead | Product rules; **source eligibility**; climate-source check; location support; commercial-rights flag. | Accepted request, or a plain-language clarify/decline email. |
| **Briefing** | Art director | Customer choices → a constrained style/size/time recipe; title rules. | Versioned `ProductionBrief`. |
| **Render** | Production artist / pipeline | Deterministic job; tool version; source/data snapshot; output profile. | Candidate assets + run log. |
| **QA** | Art director + data QA | Correct place/scope; legibility; title; **source credit**; dimensions; checksum; rights; no customer-data exposure. | Approved proof candidate, or a rework reason. |
| **Buyer proof** | Coordinator | Watermark; accessible link; expiry; accurate delivery window; revision limit. | Proof email event + buyer decision. |
| **Fulfillment** | Coordinator | Approval captured; export checklist; license; manifest; print handoff/dispatch. | Delivery event. |
| **Archive** | Coordinator | Manifest complete; asset relations; retention state; request images separated; outcome recorded. | Searchable archival record. |

On a small team one person may wear every hat — but keep the audit/permission
fields distinct so it doesn't have to stay that way.

## What actually runs today: fulfilling a county print  **[Works today]**

The reproducible, rights-checked *logic* lives in the offline-tested
`src.fulfillment` (order validation, title/attribution rules, deliverable plan,
manifest). The heavy driver that renders real GIS data is
`tools/fulfill_order.py`. It runs only in a **full (non-offline) environment**
with the GIS stack installed and datasets staged.

**One-line order (Clark County, WA — the validated case):**

```bash
.venv/bin/python tools/fulfill_order.py \
  --order-id ORD-1001 --region Washington --county Clark \
  --style neon-basin --size 18x24 --formats png pdf \
  --add-ons svg commercial_license --huc4 1708
```

**Or from an order file** (mirrors the flags exactly):

```bash
.venv/bin/python tools/fulfill_order.py --order order.json
```

```json
{
  "order_id": "ORD-1001",
  "region": "Washington",
  "county": "Clark",
  "style": "neon-basin",
  "size": "18x24",
  "formats": ["png", "pdf"],
  "add_ons": ["svg", "commercial_license"],
  "title": null,
  "subtitle": null,
  "buyer_ref": "jane@example.com"
}
```

**What it produces**, under `output/orders/<order_id>/`:

- `<order_id>_master.svg` — the neon-basin county clip with a stamped
  title / subtitle / **source-credit** block.
- One print raster per requested format (`png` via resvg, `pdf` via
  `rsvg-convert` with `SOURCE_DATE_EPOCH=0` pinned so re-orders are
  byte-identical).
- Add-ons if requested: an editable `svg`, a `commercial_license` text doc.
- `<order_id>.manifest.json` — the provenance manifest with per-file SHA-256s,
  so a re-order regenerates **byte-for-byte**.

### Valid values (enforced by `src.fulfillment`)

| Field | Allowed values | Notes |
| --- | --- | --- |
| `region` | Oregon, Washington, California, Idaho | `SUPPORTED_REGIONS` (single source in `src/config.py`). |
| `style` | `neon-basin`, `elevation-tint` | Only `neon-basin` is wired into the county fulfillment path today; `elevation-tint` uses the `mono` renderer and is not yet sellable through this tool. |
| `size` | `12x16`, `18x24`, `24x36` | Pixel dimensions from `SIZES`. |
| `formats` | `png`, `pdf` | Print rasters. |
| `add_ons` | `svg`, `commercial_license` | Optional deliverables. |
| `--huc4` | e.g. `1708` for Clark County, WA | The HUC4 GDB to scan. |

`build_order` validates every field against these allowlists and raises a
user-facing `OrderError` on anything unsupported — validate at intake, before you
make any promise to a buyer.

## The rights gate — never sell an unlicensed source  **[Works today]**

`src.fulfillment.assert_sellable` is the enforcement point:

- **USGS NHDPlus HR / NHD / WBD** hydrography is U.S. federal **public domain** —
  free to sell, but you must record the source + attribution on every asset (the
  tool stamps the credit line and writes it into the manifest and license doc).
- Climate defaults to **nClimGrid-Monthly** (public domain, sellable *with
  attribution*).
- **PRISM is not public domain.** Any style flagged `uses_prism` is refused by
  `assert_sellable` — **never ship a `--climate-source prism` asset
  commercially** (A/B comparison only).

If a proposed asset would fail `assert_sellable`, it is not sellable. Full stop.

## Reproducibility & determinism gates  **[Works today]**

Before a print goes out — and before a release is tagged — prove the output is
deterministic:

```bash
# Double-render one region/county and check run-to-run + golden byte identity:
.venv/bin/python tools/verify_determinism.py --region Washington --county Wahkiakum

# The full release gate (offline fixture match + real double-render):
.venv/bin/python tools/release_gate.py --region Washington --county Wahkiakum

# Offline-only preflight (no GDAL; runs anywhere, e.g. in CI):
.venv/bin/python tools/release_gate.py --offline-only
```

Identical inputs must produce identical output. A county render needs the Census
county boundary shapefile (`cb_2023_us_county_500k`) staged locally; a
whole-region render does not.

## Identifiers — meaningful IDs, never filenames-as-database

| Entity | ID pattern | Purpose |
| --- | --- | --- |
| Request | `REQ-YYYYMMDD-####` | Email-submitted, pre-payment record. |
| Order | `ORD-YYYYMMDD-####` | Accepted commission; maps to fulfillment `order_id`. |
| Brief revision | `BRF-<order>-rN` | Immutable interpretation of the request. |
| Render job | `JOB-<order>-rN` | One pipeline run against a brief revision. |
| Asset | `AST-<order>-<role>-rN` | Preview, proof, final, figure, bundle, thumbnail. |
| Delivery | `DLV-<order>-N` | A sent download, print handoff, or shipment. |
| Customer reference | `REF-<request>-N` | Buyer-provided file; never assumed licensed for reuse. |

## Storage layout  **[Proposed]**

A layout contract (not a specific cloud vendor). The database holds
IDs/metadata; object storage holds immutable files; access URLs are **generated,
not stored as permanent public paths.**

```text
library/
  requests/REQ-YYYYMMDD-####/
    request.json
    references/REF-...-original.ext
    correspondence/intake-email.eml-or-json
  orders/ORD-YYYYMMDD-####/
    brief/BRF-...-r1.json
    recipes/recipe-r1.yaml
    jobs/JOB-...-r1/run-log.json
    proofs/AST-...-proof-r1.jpg
    finals/AST-...-final-r1.png
    reports/AST-...-report-r1.pdf
    manifests/ORD-....manifest.json
    delivery/DLV-...-record.json
```

Note: `tools/fulfill_order.py` **today** writes to `output/orders/<order_id>/`.
The `library/` tree above is the proposed durable home once an asset library
exists.

## Asset metadata & visibility rules  **[Proposed]**

Every asset needs, before it can be sent or published: `asset_id`,
`order_id`/`request_id`, `role`, `status`, `created_at`, `created_by`,
`source_kind`, `original_filename`, `media_type`, `pixel_width`, `pixel_height`,
`checksum_sha256`, `brief_revision`, `recipe_digest`, `render_job_id`,
`rights_status`, `attribution_text`, `visibility`, `retention_class`,
`parent_asset_id`, `customer_reference_id`, `storage_key`.

Rules that matter operationally:

1. `source_kind` ∈ {`generated`, `customer_supplied`, `licensed`,
   `reference_only`} — never guessed from a filename.
2. `visibility` ∈ {`internal`, `customer_private`, `approved_public`,
   `expired`}. Default `internal` for generated, `customer_private` for customer
   material. Marking anything `approved_public` is a separate, explicit decision.
3. A final asset must reference one approved brief revision, recipe digest,
   render job, attribution text, and checksum.
4. Derivatives keep a `parent_asset_id`; never overwrite a proof or final in
   place.
5. A buyer reference may influence art direction but never becomes a
   public/gallery/training asset without a separately recorded permission.

## The internal-only boundary (do not cross)

Never expose in any customer-facing surface: source paths, cache locations, HUC
identifiers, raw QA failures, rights flags, customer email history, job logs,
checksums, pipeline arguments, or any other customer's assets.

## Operations prototypes  **[Prototype]**

| Page | What it demonstrates |
| --- | --- |
| `experiments/concierge-ux/ops-dashboard.html` | Order status, notifications, and work needing attention. |
| `experiments/concierge-ux/ops-order.html` | One order: brief, production checks, recipe, lineage. |
| `experiments/concierge-ux/ops-library.html` | Asset-library concept with privacy/lineage categories. |
| `web/studio.html` | The **expert / internal** art-direction control surface. Internal only — it must **not** be a buyer's first interface. |

---

# Part 3 — What's real vs. what's proposed

| Capability | Status |
| --- | --- |
| Deterministic GIS→SVG pipeline (byte-identical output) | **Works today** |
| County-print fulfillment (`tools/fulfill_order.py`) → rasters + license + manifest | **Works today** |
| Rights gate (`assert_sellable`, public-domain sources, PRISM block) | **Works today** |
| Reproducibility / release gates (`verify_determinism.py`, `release_gate.py`) | **Works today** |
| Expert control surface (`web/studio.html`) | **Works today** (internal) |
| Customer catalog / brief / proof / delivery web pages | **Prototype** (`experiments/`) |
| Operations dashboard / order / library web pages | **Prototype** (`experiments/`) |
| Email confirmation/proof/approval/delivery (real send + event records) | **Proposed** |
| Object storage, asset database, lineage/search, signed links | **Proposed** |
| Request/Order/Brief/Job/Asset/Delivery schemas & state machine | **Proposed** |
| Animation & report as *sellable* products | **Proposed** (behind revenue + rights gates) |

---

# Part 4 — Open decisions before production

These are product/operations questions with owners and answers required —
**not** coding tickets. Do not build past them:

1. **Sales channel** — direct site request, Etsy-style listing, or concierge
   email intake? (Determines where payment/tax/refund/platform rules live.)
2. **Proposal vs. order** — is a proposal binding, or does it become an order at
   manual payment / proof approval? Define before enabling "submit" language.
3. **Revision policy** — included revisions per product, and who may authorize
   an exception. (Proof UX currently assumes one bounded adjustment.)
4. **Print fulfillment** — partner, shipping geography, packaging, proof-to-
   production cutoff, and reprint/refund handling.
5. **Report/forecast language** — the exact approved customer-facing claim, and
   whether any forecast feature exists at all (method, uncertainty language,
   qualified reviewer, liability review, data source).
6. **Data retention** — retention/deletion policy for buyer emails, private
   proofs, and customer reference images, including a deletion-request process.
7. **Publication authority** — who may change public catalog examples and mark
   an asset `approved_public`.

---

# Quick reference

**Fulfill a county print (works today):**
```bash
.venv/bin/python tools/fulfill_order.py --order-id ORD-1001 \
  --region Washington --county Clark --style neon-basin --size 18x24 \
  --formats png pdf --add-ons svg commercial_license --huc4 1708
```

**Prove determinism / gate a release (works today):**
```bash
.venv/bin/python tools/verify_determinism.py --region Washington --county Wahkiakum
.venv/bin/python tools/release_gate.py --offline-only
```

**Supported regions:** Oregon · Washington · California · Idaho
**Sellable style:** `neon-basin` · **Sizes:** 12x16 / 18x24 / 24x36 ·
**Formats:** png / pdf · **Add-ons:** svg / commercial_license

**Sources:** USGS NHDPlus HR / NHD / WBD (public domain) + nClimGrid-Monthly
(public domain, attribution). **PRISM is never sellable.**

**Canonical design docs:**
`agent-os/specs/2026-09-05-customer-operations-experience/spec.md` ·
`.../workflow.mmd` · `experiments/concierge-ux/HANDOFF-TO-CLAUDE.md`
