# Requirements: Operations Library, Samples & Analysis Ledger (Epoch 25)

## Feature goal

Create an internal PostgreSQL operations ledger for tracking completed work,
sample curation, asset lineage, and analysis evidence -- searchable and auditable
via Postico 2 -- without making the render pipeline depend on a live database.
PostgreSQL is opt-in (`DATABASE_URL`); JSON-file persistence remains the default.

## Roadmap items (#99--#106)

### #99 -- Ledger boundary & migration contract
- Schema, migration policy, PostgreSQL version, roles, bootstrap, backup/restore.
- Repository protocol: `OrderStore` remains the default JSON/offline implementation.
- No `src/` module imports a PostgreSQL driver at load time. No ORM.

### #100 -- Core operations schema
- Migrations for `places`, `requests`, `orders`, `brief_revisions`, `render_jobs`,
  `assets`, `asset_lineage`, `deliveries`, and append-only `events`.
- Stable public IDs (`REQ-YYYYMMDD-####`, `ORD-*`, `BRF-*`, `JOB-*`, `AST-*`, `DLV-*`).
- State-transition validity, foreign keys, checksums, immutable storage keys.
- Delivery access window: `delivered_at` + 90 days, with `access_revoked_at`.
- Files are never BLOBs; URLs generated on demand.

### #101 -- Sample and completed-work catalog
- Assets with role, geography, recipe digest, render-job link, source attribution,
  rights status, visibility, dimensions, checksum, parent lineage.
- Default `internal`; `approved_public` requires an audited action.

### #102 -- PostgreSQL repository adapter
- Wire into operations/order routes only when `DATABASE_URL` is configured.
- Preserve JSON-store behavior when absent.
- Transactional writes, event recording.
- Ledger failure never alters/deletes a completed artifact.

### #103 -- Legacy import & reconciliation tool
- Idempotent `tools/` import of existing `output/orders/*.json`, fulfillment
  manifests, and selected gallery/market samples.
- Dry-run default, creates/updates/skips/conflicts report, checksum verification.
- Refuse public visibility without recorded rights.

### #104 -- Analysis evidence model
- `analysis_runs` and `analysis_metrics` linked to place, recipe/asset, input
  provenance, metric-definition version, validation status, result payload.
- Covers watershed-report observations and operational measures (proof turnaround,
  revision count, fulfillment time, conversion, re-render/determinism failures).
- Never presents derived business measures as source hydrology.

### #105 -- Postico 2 operator workspace & safe query pack
- Read-only SQL views for active requests, proof queue, completed work, public-ready
  samples, assets missing provenance/rights, failed jobs, operational metrics,
  expiring/expired deliveries.
- Least-privilege Postico connection; production mutation via application only.

### #106 -- Ledger test and verification pyramid
- Pure tests for IDs, state transitions, constraints, visibility/rights rules,
  lineage, import planning, JSON fallback (no database).
- Opt-in PostgreSQL integration tests (migrations, transactions, repository
  contract, ledger-on vs. ledger-off artifact hash identity).
- Keep PostgreSQL and Postico out of the offline Python suite.

## Constraints

- **Offline suite stays database-free.** No psycopg/database driver import at
  `src/` module top level. Tests never connect to a real database.
- **Render byte-identity.** A render must produce identical bytes whether the
  ledger is enabled or not.
- **No ORM.** Raw SQL with parameterized queries. Plain SQL migration files.
- **JSON OrderStore remains default.** PostgreSQL is opt-in via `DATABASE_URL`.
- **Privacy.** Customer email must not leak into gallery/sample views.
- **No pipeline change.** `PIPELINE_STAGES` is untouched.

## Out of scope

- Customer-facing portal or delivery page changes.
- Object storage (S3/MinIO) integration -- library stays on filesystem/NAS.
- Automatic render queue or job scheduling via the database.
- Row-level security or multi-tenant access control.
- WAL archiving, streaming replication, or PITR automation.
- Web UI for the operator workspace (Postico is the client).
- Changes to `src/fulfillment.py` pure logic or `GALLERY_MATRIX` source data.
- Payment/Stripe integration with the ledger.
- Partitioning of events or jobs tables.
