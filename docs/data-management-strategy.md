# Data Management Strategy for a Growing Hydro-Art Library

## Purpose

Hydro-Art will accumulate several distinct kinds of valuable records: customer
requests, deterministic render recipes, large generated assets, source and rights
evidence, operations history, and watershed-analysis results. They must be managed
as one lineage system without making the GIS pipeline depend on a live database or
putting large binaries in PostgreSQL.

This strategy assumes an internal, initially single-operator studio; PostgreSQL as
the operations ledger; Postico 2 as the human operator client; and a filesystem or
object store as the asset home. It expands Epoch 25 in the product roadmap.

## The operating model

Use three separate systems with explicit responsibilities:

| System | Authoritative for | Not responsible for |
| --- | --- | --- |
| Render recipe + fulfillment manifest | Reproducibility, source attribution, output checksum, render settings | Customer access, search, or storage location |
| PostgreSQL ledger | IDs, relationships, status, rights, visibility, retention, search, event history, analysis metadata | SVG/PNG/PDF/GIF bytes or permanent delivery URLs |
| Object storage or `library/` | Immutable files and backup copies | Business-state decisions or customer authorization |

This split protects the central product invariant: identical render inputs produce
identical bytes whether the ledger is enabled, unreachable, or entirely absent.

## The data domains to manage

### 1. Intake and customer work

Treat a request as an inquiry, not an order. A request may become an accepted
order; an order can have several immutable brief revisions; a brief may lead to
many render jobs; a job may produce many assets; a delivery grants time-limited
access to selected assets. These are separate records because they answer different
operational questions.

Do not use filenames as IDs. Preserve the current human-readable IDs:

```text
REQ-YYYYMMDD-####  inquiry
ORD-YYYYMMDD-####  accepted commission
BRF-<order>-rN     immutable brief revision
JOB-<order>-rN     one render attempt
AST-<order>-<role>-rN  immutable asset
DLV-<order>-N     one delivery event
```

### 2. Generated assets

Images, SVGs, PDFs, animations, report figures, thumbnails, print bundles, and
licenses should all be `assets`; the media type distinguishes them. Each has one
immutable storage key, byte count, SHA-256, dimensions/duration where applicable,
its parent asset if derived, and a role. An asset must never be overwritten in
place: a revised proof becomes a new asset with a lineage edge.

Recommended roles:

```text
source_reference | recipe | run_log | proof | final | print | vector |
report | figure | animation | thumbnail | bundle | license | customer_reference
```

### 3. Curated samples and marketing work

A gallery item is not a special filesystem folder. It is an asset (or a collection
of assets) with `visibility = approved_public`, a catalog label, optional featured
rank, explicit rights decision, source attribution, and a provenance link to the
render job or a documented external origin. The default for imports is `internal`.

This enables one source of truth for questions such as:

- Which public samples came from Oregon vs. Washington?
- Which examples use a waterbody preset or a given report version?
- Can this image be reused commercially?
- Which thumbnail belongs to this master PNG?

### 4. Analysis evidence

Watershed reports should preserve the evidence behind a claim, not only a finished
PDF. An `analysis_run` records scope, input-source versions, code/metric-definition
version, start/end years, validation status, and a digest of its input data. An
`analysis_metric` then records a named result, units, method/version, value or
structured result, and interpretation status.

Separate scientific/technical measures (for example trend slope or center-of-timing
shift) from business measures (conversion, proof turnaround, revision count). The
former need scientific provenance and validation; the latter need a stable event
definition and time zone.

## Storage layout and lifecycle

### Storage keys, not paths chosen by hand

Use predictable, write-once storage keys. A key should contain the durable entity
ID and asset role, not an editable customer name or an assumed public URL.

```text
library/
  requests/REQ-20260913-0001/intake/request.json
  orders/ORD-20260913-0001/
    briefs/BRF-ORD-20260913-0001-r1.json
    recipes/recipe-r1.yaml
    jobs/JOB-ORD-20260913-0001-r1/run-log.json
    proofs/AST-ORD-20260913-0001-proof-r1.jpg
    finals/AST-ORD-20260913-0001-final-r1.png
    reports/AST-ORD-20260913-0001-report-r1.pdf
    manifests/ORD-20260913-0001.manifest.json
    deliveries/DLV-ORD-20260913-0001-1.json
  catalog/AST-.../thumbnail.webp
```

Store the relative key in the ledger, not an absolute workstation path. This makes
NAS, local storage, and an S3-compatible object store interchangeable.

### Availability is not retention

The customer policy is: a delivered asset is available through the customer portal
for **90 days after `delivered_at`**. At 90 days, the application denies a new
download, records the expired access state, and offers a re-delivery/reorder path.

That policy does **not** mean deleting the master at day 90. Asset retention is a
separate per-asset decision with an explicit `retention_class`, `retain_until`,
`deleted_at`, and deletion approval event. This distinction prevents accidental
loss of a paid customer’s source file and makes the policy explainable.

Use a portal endpoint such as `GET /deliveries/<id>/download/<asset_id>` to check
the ledger’s access window, revocation, and visibility first. If allowed, it creates
a fresh, short-lived object-store download grant. Do not email a 90-day presigned
object-store URL: S3 presigned URLs are intended for time-limited access, but CLI
and SDK URLs themselves can be valid only up to seven days.[^1]

Recommended delivery behavior:

| Time | Portal behavior | Storage behavior |
| --- | --- | --- |
| At delivery | Send customer to authenticated/tokenized delivery page | Master and delivery files remain hot |
| Days 1–60 | Generate a short-lived download grant after each authorization check | Normal storage |
| Day 60 | Send a single, optional access-expiry reminder | Normal storage |
| Days 61–90 | Same authorization path; show exact expiry | Normal storage |
| After day 90 | Return an honest expired-access response; do not leak object key | Keep or archive based on retention policy |
| Re-delivery | Operator records a new delivery, reason, fee/waiver, and new 90-day window | Never copy over the original asset |

### Storage classes should follow usage, not a calendar copied from link expiry

Start with hot storage for all active work. Once access patterns are known, transition
only large, infrequently accessed completed masters and source archives to cooler
storage. Object stores can transition or expire objects through lifecycle rules,
but expiration may be asynchronous and can permanently remove data in a
non-versioned bucket.[^2]

Practical initial policy:

| Class | Examples | Retention/access rule |
| --- | --- | --- |
| Hot operational | active requests, proofs, current delivery assets | Fast access; no automatic deletion |
| Warm completed | finals, manifests, licenses, public gallery originals | Keep online; review after 12 months |
| Cold archive | superseded proofs, source downloads, raw analysis inputs | Archive after 180–365 days only with restore procedure tested |
| Disposable | failed temporary renders, browser traces, transient intermediates | Delete after 14–30 days, subject to no linked investigation |

Do not create a lifecycle delete rule until a restore drill and a ledger reconciliation
report exist. Lifecycle rules apply to existing as well as new objects, so a mistaken
prefix can affect historical work.[^3]

## Ledger design

### Relational core; flexible fields at the edge

Put identity and decision-critical fields in normal columns: IDs, foreign keys,
state, timestamps, visibility, source/right status, checksum, storage key, and
retention fields. Use `jsonb` only for versioned or endpoint-specific payloads such
as render settings, analysis output, source metadata, or provider responses.

`jsonb` is appropriate for such flexible payloads because PostgreSQL can index and
query it, but it should not hide the fields that support day-to-day filtering or
integrity.[^4]

Core tables and their non-negotiable relations:

```text
places ────────< requests ────────< orders ────────< brief_revisions
                                    │                    │
                                    │                    └──────< render_jobs
                                    │                               │
                                    └──────< deliveries             └──────< assets
                                                                         │        │
analysis_runs ────────────────────────────────────────────────────────┘        └─< asset_lineage
       └──────< analysis_metrics
events ────────> any entity via entity type + ID (append-only audit trail)
```

The schema must enforce, not merely document: primary IDs; deduplicated asset
checksums scoped appropriately; valid visibility/rights values; a delivery expiry
after delivery creation; and foreign keys for lineage. PostgreSQL constraints and
foreign keys are designed to enforce these cross-row and cross-table relationships.[^5]

### Indexes that matter early

Create indexes only for actual operator workflows:

- `assets(order_id, role, created_at DESC)` for an order history.
- `assets(visibility, rights_status, created_at DESC)` for public-ready review.
- `assets(checksum_sha256)` for dedupe and integrity audits.
- `deliveries(access_expires_at)` with a partial index for open access windows.
- `render_jobs(status, created_at DESC)` for failures and queue work.
- `events(entity_type, entity_id, occurred_at DESC)` for audit histories.
- GIN indexes for deliberately queried `jsonb`, added after query evidence.

Do not partition initially. Monthly partitioning of high-volume `events` or job logs
can be introduced when table size and retention operations justify it. PostgreSQL
partitioning helps when queries target a small number of partitions and supports
per-partition indexing/retention operations; it is not a substitute for good keys
and indexes.[^6]

### Privacy and access

Use separate database roles:

- `hydro_app_writer`: application-only mutations; no superuser privileges.
- `hydro_ops_readonly`: Postico browsing and saved queries; no PII exports by
  default.
- `hydro_migrator`: migrations only, used in deployment.
- `hydro_backup`: backup/PITR process only.

Keep customer email, correspondence, and private references out of general gallery
views. If multiple staff or contractors later need access, add Postgres row-level
security or read-only purpose-built views rather than distributing writer
credentials. Row-level security can restrict rows returned or changed per role and
defaults to deny when enabled without a policy.[^7]

## Workflows that prevent disorder

### Intake to completed work

1. Validate intake; create a `request` and an append-only `request_created` event.
2. Accept it into an `order`; snapshot the customer brief as revision 1.
3. Create a render job with exact recipe digest, code revision, input source set,
   and target output roles.
4. Render to a temporary staging prefix; calculate SHA-256 and validate expected
   format/dimensions before ledger publication.
5. Move/write the finalized asset under its immutable key; create the asset record
   and asset-to-job lineage in one ledger transaction.
6. Create a proof or final delivery only after rights, attribution, and visibility
   checks succeed.
7. Generate customer access on demand, not as a permanent link saved in the DB.

The essential invariant is “file first, verified, then referenced.” Never create a
final asset row that points to a file still being written. If storage write succeeds
but the DB transaction fails, an orphan scanner quarantines the object; if the DB
commit succeeds but storage is inaccessible, health checks flag the asset as
unavailable rather than silently substituting another file.

### Sample creation workflow

1. Render or ingest a candidate as `internal`.
2. Attach source attribution, rights decision, checksum, and thumbnail lineage.
3. Run a public-release checklist: no customer identity, no restricted climate
   source, no private notes/logs, correct title/alt text, approved crop.
4. Record an explicit `visibility_changed` event that identifies the approver.
5. Publish only the derived public assets; keep masters private by default.

### Analysis workflow

1. Freeze input scope and provider versions.
2. Write structured machine-readable result data plus human-facing figures.
3. Attach each figure and report to its `analysis_run`.
4. Record validation outcome, methodology/version, known limitations, and reviewer.
5. Prohibit a web claim from using a metric marked `draft`, `unvalidated`, or
   `reference_only`.

## Integrity, backup, and recovery

### Every file has two integrity records

Record the application SHA-256 in PostgreSQL and attach/use an object-store
checksum at upload. Object stores such as S3 can validate upload/download checksums
and calculate integrity reports for stored objects; this supports a periodic
ledger-to-storage audit instead of trusting an ETag.[^8]

Run three checks:

| Cadence | Check | Success condition |
| --- | --- | --- |
| Per upload | byte count, SHA-256, media probe | file matches intended asset record |
| Daily | ledger/storage existence reconciliation | no missing, unknown, or mutable referenced files |
| Monthly | sampled restore and checksum verification | restored object and manifest match ledger |

### Backups are a restore capability, not a checkbox

For the first small deployment, take encrypted daily database backups and retain a
documented restore runbook. When customer operations become material, add base
backups plus WAL archiving for point-in-time recovery, offsite copies, and a
quarterly restore exercise. PostgreSQL WAL archiving supports recovery to a chosen
point after a base backup, but requires intentionally managing base backups and WAL
retention.[^9]

Back up database and assets independently, then prove a cross-system restore:

1. Restore a ledger snapshot to an isolated database.
2. Restore one order’s manifest and all referenced assets to an isolated prefix.
3. Compare checksums and lineage.
4. Confirm expired customer access remains denied in the restored environment.

## Operator views and useful questions

Postico is best used for read-only curated views, not manual production edits. Keep
the SQL that defines those views and the saved query pack in version control.

Start with these views:

| View | Operational question |
| --- | --- |
| `ops_active_work` | What is waiting for acceptance, proof, approval, or fulfillment? |
| `ops_completed_work` | Which complete works are available, archived, or missing a manifest? |
| `ops_delivery_expiry` | Which customers lose access in 30 days; which links are expired? |
| `ops_rights_gaps` | Which assets cannot be delivered or published safely? |
| `ops_render_failures` | What failed repeatedly by region, endpoint, or code revision? |
| `ops_library_candidates` | Which internal samples have all public-release prerequisites? |
| `ops_analysis_evidence` | Which reports have validated source inputs and reviewed metrics? |
| `ops_orphans` | Which files lack a ledger record; which records lack an object? |

Operational metrics should be calculated from immutable events, not mutable current
status:

- Median and 90th-percentile time from accepted → proof ready.
- Revision count from proof ready → approved.
- Render failure rate by endpoint and input version.
- Re-render rate after delivery.
- Gallery coverage by region, product, style, and rights status.
- Number of assets approaching a retention-review date.

## Scale triggers

Avoid speculative infrastructure. Upgrade when evidence crosses a threshold.

| Signal | Upgrade |
| --- | --- |
| One operator, under ~10,000 assets | Postgres + object storage + daily backup; no partitioning or queue cluster |
| More than ~100 GB or large video/GIF uploads | Multipart upload, explicit checksum verification, upload staging, asset-size quotas |
| More than ~100 new jobs/day or concurrent renders | Durable job queue, idempotency keys, worker leases, separate job log/event retention |
| More than ~1 million events or slow time-range queries | Time-partition events/jobs; archive old partitions after tested restore |
| Multiple staff or contractors | Read-only operational views, least-privilege roles, RLS where tenant boundaries matter |
| Customer self-service | Authenticated delivery portal, on-demand short-lived grants, download audit events, abuse/rate controls |
| Multi-region or reporting-heavy operations | Read replica/warehouse only after operational DB query profiling demonstrates need |

## Ideas that create leverage

1. **Recipe fingerprint as the universal join key.** Hash canonical render settings,
   code revision, and source manifest. Use it to find duplicate work, prove a
   re-render, and group gallery variants.
2. **Contact sheets as managed assets.** Generate monthly browse sheets and catalog
   them; use them to curate large image sets without loading full-resolution files.
3. **Automatic derivative graph.** Every thumbnail, crop, proof, social image, PDF,
   and source master has an explicit parent edge. This makes “where did this come
   from?” a query rather than detective work.
4. **Quarantine, not delete, for uncertain imports.** Unknown rights, malformed
   metadata, and duplicate candidates remain searchable but undeliverable until
   resolved.
5. **Release packets.** A public gallery release is a versioned collection with a
   manifest, approvals, captions, assets, and rollback status.
6. **Reproducibility cards.** For every final, create a compact internal HTML/JSON
   card containing title, location, recipe, sources, checksum, art settings, and
   asset graph. It becomes the fastest support and reprint tool.
7. **Exception ledger.** Model manual actions—free re-delivery, asset deletion,
   public-visibility approval, customer-requested removal, rights override—as
   explicit events with actor and rationale.
8. **Data-quality score for every asset.** Score presence of checksum, source,
   attribution, recipe, dimensions, rights, visibility decision, and parent
   lineage. Use it to prioritize cleanup rather than trying to perfect everything.
9. **Demand-aware render library.** Aggregate request geography/style combinations
   and flag high-demand combinations lacking a pre-rendered public sample.
10. **Capacity forecast from actual bytes.** Track byte counts by media type,
    storage class, and age; estimate storage growth from observed monthly ingest
    rather than assumptions.

## Recommended implementation order

1. Finish Epoch 25 #99: data dictionary, migration policy, lifecycle vocabulary,
   backup/restore and 90-day access policy.
2. Implement #100 and #101: core schema plus assets/lineage and constraints.
3. Implement #102: optional Postgres repository without changing JSON fallback or
   render byte output.
4. Implement #105 early enough to make Postico useful from day one.
5. Implement #103 with dry-run import and reconciliation before bulk ingestion.
6. Implement #104 after a real report output format is stable.
7. Implement #106 last as the verification gate, including an actual restore drill.

The first operational milestone is modest: one completed render can be found by
order, place, checksum, or sample label; its lineage and rights are intelligible;
its customer delivery expires in 90 days without deleting the master; and a restore
exercise can recreate the complete record.

## Sources

[^1]: Amazon Web Services. ["Download and upload objects with presigned URLs"](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html). Access and expiration limits for S3 presigned URLs.
[^2]: Amazon Web Services. ["Setting an S3 Lifecycle configuration on a bucket"](https://docs.aws.amazon.com/AmazonS3/latest/userguide/how-to-set-lifecycle-configuration-intro.html). Lifecycle transitions, expiration, and asynchronous processing.
[^3]: Amazon Web Services. ["Managing the lifecycle of objects"](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html). Lifecycle rules apply to existing objects and deletion behavior.
[^4]: PostgreSQL Global Development Group. ["JSON Types"](https://www.postgresql.org/docs/current/datatype-json.html). `jsonb` processing and indexing behavior.
[^5]: PostgreSQL Global Development Group. ["Constraints"](https://www.postgresql.org/docs/current/ddl-constraints.html). Primary keys, uniqueness, and foreign-key integrity.
[^6]: PostgreSQL Global Development Group. ["Table Partitioning"](https://www.postgresql.org/docs/current/ddl-partitioning.html). Declarative partitioning, partition pruning, and tradeoffs.
[^7]: PostgreSQL Global Development Group. ["Row Security Policies"](https://www.postgresql.org/docs/current/ddl-rowsecurity.html). Role-dependent row access and default-deny behavior.
[^8]: Amazon Web Services. ["Checking object integrity in Amazon S3"](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity.html). Upload/download checksums and at-rest integrity reports.
[^9]: PostgreSQL Global Development Group. ["Continuous Archiving and Point-in-Time Recovery (PITR)"](https://www.postgresql.org/docs/current/continuous-archiving.html). WAL archiving, base backups, and point-in-time restoration.
