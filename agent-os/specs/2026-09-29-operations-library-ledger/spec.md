# Specification: Operations Library, Samples & Analysis Ledger

## Goal

Create an opt-in PostgreSQL operations ledger alongside the existing JSON
`OrderStore`, behind a repository protocol, so an operator can search, audit,
and trace completed work, asset lineage, sample curation, and analysis evidence
in Postico 2 -- without changing the render pipeline, its determinism, or its
offline-suite discipline.

## User Stories

- As the studio operator, I want to find a completed artwork by order, place,
  checksum, or sample label, trace its lineage (brief -> job -> assets ->
  delivery), and see whether its rights and provenance are complete.
- As the studio operator, I want the JSON file store to keep working identically
  when I have not configured `DATABASE_URL`, so existing workflows are not
  disrupted.
- As the studio operator, I want to browse operational views in Postico 2 --
  active work, expiring deliveries, rights gaps, render failures -- using
  read-only saved queries that I never need to author myself.

## Architecture Placement

- **Offline `src/` module(s):**
  - `src/ledger.py` -- repository protocol (`OrderRepository`), ID helpers,
    state-transition rules, entity dataclasses (Place, Asset, RenderJob,
    AnalysisRun, AnalysisMetric, etc.), visibility/rights enums, pure
    validation. No database driver import.
  - `src/ledger_pg.py` -- PostgreSQL repository implementation. Imports
    `psycopg` lazily inside methods, never at module top level. Instantiated
    only when `DATABASE_URL` is set.
  - `src/orders.py` -- existing `OrderStore` becomes the JSON implementation of
    the same protocol. Its public API does not change; it gains an optional
    protocol-compatible wrapper or remains the default when no `DATABASE_URL`.
- **Non-offline `tools/` entry point(s):**
  - `tools/migrate_ledger.py` -- apply SQL migrations to a target database.
  - `tools/import_legacy.py` -- idempotent import of existing JSON orders,
    manifests, and gallery samples into the PostgreSQL ledger (dry-run default).
- **Touches `PIPELINE_STAGES`?** No.
- **Injected seam reused/extended:** The `OrderStore` class in `src/orders.py`
  is already the injected persistence seam for orders. This spec introduces a
  `OrderRepository` protocol that `OrderStore` (JSON) and
  `PgOrderRepository` (PostgreSQL) both satisfy, and a factory function that
  returns the appropriate one based on environment.
- **Determinism impact:** 2D default output byte-identical. The ledger is a
  parallel bookkeeping system that records metadata about renders; it never
  participates in the render pipeline. A render with `DATABASE_URL` set
  produces the same artifact bytes as one without.

## Specific Requirements

**Repository protocol (`src/ledger.py`)**
- Define a `typing.Protocol` class `OrderRepository` with the methods that
  `OrderStore` already exposes: `create_request`, `get`, `list_all`,
  `update_status`, `set_job_id`, `add_event`, `add_note`.
- Add protocol methods for the new entity operations: `record_asset`,
  `record_delivery`, `record_render_job`, `record_analysis_run`,
  `record_analysis_metric`, `get_assets_for_order`, `get_delivery`.
- Entity dataclasses: `Place`, `Asset`, `AssetLineage`, `RenderJob`,
  `BriefRevision`, `Delivery`, `AnalysisRun`, `AnalysisMetric`, `LedgerEvent`.
- All dataclasses are frozen. All IDs follow the `docs/data-management-strategy.md`
  format (`REQ-YYYYMMDD-####`, `ORD-*`, `BRF-*-rN`, `JOB-*-rN`, `AST-*-<role>-rN`,
  `DLV-*-N`).
- `Asset` carries: `asset_id`, `order_id`, `render_job_id`, `role` (from a
  closed set: source_reference, recipe, run_log, proof, final, print, vector,
  report, figure, animation, thumbnail, bundle, license, customer_reference),
  `storage_key` (relative path, never absolute), `checksum_sha256`, `byte_count`,
  `width_px`, `height_px`, `media_type`, `visibility` (internal | approved_public),
  `rights_status` (pending | cleared | restricted), `source_attribution`,
  `created_at`, `retention_class`, `retain_until`, `deleted_at`.
- `Delivery` carries: `delivery_id`, `order_id`, `delivered_at`,
  `access_expires_at` (delivered_at + 90 days), `access_revoked_at`, `asset_ids`,
  `reason`, `fee_waived`.
- `LedgerEvent` is append-only: `event_id`, `entity_type`, `entity_id`,
  `occurred_at`, `event_name`, `actor`, `detail` (dict).
- Pure validation functions: `validate_asset_role`, `validate_visibility`,
  `validate_rights_status`, `validate_delivery_access` (returns expired/active/
  revoked), `validate_state_transition` (reuse `TRANSITIONS` from `src/orders.py`).
- `repository_factory(database_url: str | None = None) -> OrderRepository` --
  returns `PgOrderRepository` when URL is provided, `OrderStore` otherwise.

**PostgreSQL adapter (`src/ledger_pg.py`)**
- Implements `OrderRepository` protocol against PostgreSQL.
- `psycopg` (v3) imported lazily inside `__init__` or individual methods, never
  at module top level.
- All writes are transactional: asset creation + lineage insertion + event
  recording happen in one transaction.
- On connection failure or transaction error, raise a `LedgerError` (new
  exception in `src/ledger.py`). The caller (e.g., a `tools/` script) catches
  and logs; a render pipeline run is never aborted by a ledger failure.
- Parameterized queries only (`%s` placeholders, no string interpolation).
- Connection pooling is not required initially (single-operator use).

**SQL migrations (`migrations/`)**
- Plain `.sql` files in `migrations/` directory, numbered sequentially:
  `001_create_places.sql`, `002_create_core_tables.sql`, etc.
- `tools/migrate_ledger.py` reads `DATABASE_URL`, applies unapplied migrations
  in order, records applied migrations in a `_migrations` table.
- No down-migrations initially; rollback is "restore from backup."
- Target PostgreSQL >= 15.
- Tables: `places`, `requests`, `orders`, `brief_revisions`, `render_jobs`,
  `assets`, `asset_lineage`, `deliveries`, `events`.
- `places` stores geographic identity: `place_id`, `region`, `county` (nullable),
  `huc4` (nullable), `display_name`.
- `assets` has a `UNIQUE` constraint on `checksum_sha256` scoped to `order_id`
  (same file in different orders is fine; same hash within one order is a dupe).
- `events` uses `entity_type` + `entity_id` (polymorphic FK pattern, no
  physical FK) to link to any entity.
- `visibility` and `rights_status` use `CHECK` constraints against the closed
  value sets.
- Indexes per `docs/data-management-strategy.md`: `assets(order_id, role,
  created_at DESC)`, `assets(visibility, rights_status, created_at DESC)`,
  `assets(checksum_sha256)`, `deliveries(access_expires_at)` partial for open
  windows, `render_jobs(status, created_at DESC)`, `events(entity_type,
  entity_id, occurred_at DESC)`.

**Database roles**
- Document four roles in migration comments: `hydro_app_writer`,
  `hydro_ops_readonly`, `hydro_migrator`, `hydro_backup`.
- The migration script creates tables under the migrator role.
- The `ops_*` views grant `SELECT` to `hydro_ops_readonly`.
- Role creation is documented but not automated (operator creates roles
  manually in their PostgreSQL instance).

**Sample and catalog integration**
- `CatalogStore` (Epoch 33, `src/catalog.py`) remains the operational catalog
  for artwork curation. The ledger does not replace it.
- When PostgreSQL is available, `tools/import_legacy.py` can optionally read
  `CatalogStore` entries and create corresponding `Asset` + `LedgerEvent`
  records in the ledger, linking by `entry_id` stored in `Asset.detail` (jsonb).
- `GALLERY_MATRIX` in `src/gallery.py` remains the curated source data for the
  public gallery. The ledger records provenance for rendered gallery assets but
  does not become the gallery's source of truth.

**Analysis evidence model**
- `AnalysisRun`: `run_id`, `place_id`, `recipe_digest`, `code_revision`,
  `input_sources` (jsonb), `start_year`, `end_year`, `metric_version`,
  `validation_status` (draft | validated | reference_only), `created_at`,
  `reviewer`, `notes`.
- `AnalysisMetric`: `metric_id`, `run_id`, `name`, `units`, `method`,
  `method_version`, `value` (jsonb), `interpretation_status`
  (draft | validated | unvalidated | reference_only), `created_at`.
- An asset with role `report` or `figure` can link to an `analysis_run_id`.
- Business metrics (proof turnaround, conversion rate) are `AnalysisMetric`
  rows with a distinct `method` prefix (`ops_*`), never mixed with hydrology
  metrics in the same run.

**Postico 2 views (`migrations/views/`)**
- SQL view definitions stored alongside migrations.
- Eight views per `docs/data-management-strategy.md`:
  `ops_active_work`, `ops_completed_work`, `ops_delivery_expiry`,
  `ops_rights_gaps`, `ops_render_failures`, `ops_library_candidates`,
  `ops_analysis_evidence`, `ops_orphans`.
- `ops_active_work`: requests/orders not yet fulfilled, with age.
- `ops_delivery_expiry`: deliveries with `access_expires_at` in next 30 days
  or already expired.
- `ops_rights_gaps`: assets where `rights_status != 'cleared'` or
  `source_attribution IS NULL`.
- `ops_library_candidates`: internal assets with all public-release prerequisites
  met (rights cleared, attribution present, checksum present, thumbnail linked).
- Views exclude `email` from customer-facing columns; join on `order_id` only
  when the operator needs to correlate.

**Legacy import tool (`tools/import_legacy.py`)**
- Reads `output/orders/REQ-*.json` files (existing `Request` format).
- Reads fulfillment manifests (`*.manifest.json`) for checksum/deliverable data.
- Reads `catalog/catalog.json` (Epoch 33 `CatalogStore` format) for sample
  entries.
- Dry-run by default (`--dry-run` / `--apply`).
- Output: creates/updates/skips/conflicts count, per-record detail log.
- Refuse to set `visibility = approved_public` on any asset without a recorded
  `rights_status = cleared` and non-null `source_attribution`.
- Idempotent: re-running with the same data produces no new records or errors.
- Checksum verification: if a referenced file exists on disk, compute SHA-256
  and compare against the manifest; warn on mismatch.

**JSON fallback preservation**
- `OrderStore` in `src/orders.py` continues to work identically when
  `DATABASE_URL` is absent.
- `repository_factory(None)` returns an `OrderStore` instance.
- No code path in `src/` checks `DATABASE_URL` at import time. The factory is
  called explicitly by `tools/` scripts and `src/server.py` at startup.

**Privacy**
- Customer `email` is stored in `requests` (and in JSON `Request` files) but
  excluded from all `ops_*` views by default.
- Gallery/sample queries never join to `email`.
- `ops_active_work` and `ops_completed_work` show `order_id` and `region`/
  `county`/`style` but not customer identity.

## Existing Code to Leverage

**`src/orders.py` -- OrderStore**
- Already implements the full order lifecycle: `create_request`, `get`,
  `list_all`, `update_status`, `set_job_id`, `add_event`, `add_note`.
- Uses `STATUSES` and `TRANSITIONS` dicts for state-machine enforcement.
- JSON-file persistence with thread locking.
- The `Request` dataclass and `OrderEvent` dataclass define the existing data
  shape. The protocol must be compatible with this shape.

**`src/fulfillment.py` -- Order, DeliverablePlan, manifest**
- `Order`, `Deliverable`, `DeliverablePlan` are frozen dataclasses.
- `fulfillment_manifest` produces a deterministic provenance record with
  checksums. This is the source for import into the ledger's `assets` table.
- `assert_sellable` enforces the PRISM Rights gate -- reuse, do not duplicate.
- `attribution_line` produces the deterministic source-credit string.

**`src/gallery.py` -- GALLERY_MATRIX and gallery_ledger**
- `GALLERY_MATRIX` is the curated selection tuple. It remains the source of
  truth for which items are in the public gallery.
- `gallery_ledger` produces a per-asset rights + provenance ledger dict. The
  PostgreSQL ledger records equivalent data but does not replace this function.

**`src/catalog.py` -- CatalogEntry and CatalogStore**
- `CatalogEntry` tracks render identity, version, status lifecycle, and display
  metadata. The import tool reads this for sample/catalog asset records.
- `CatalogStore` is JSON-file-backed. The PostgreSQL ledger is a parallel
  system, not a replacement.

**`src/analytics.py` -- compute_analytics**
- Pure function over order event logs. Business metrics computed here (proof
  acceptance rate, render time, payment conversion) map to `ops_*` method
  `AnalysisMetric` rows in the ledger, keeping the pure function for offline
  computation and the ledger for historical storage.

## Rights & Determinism Notes

- No new data sources are introduced. All data in the ledger originates from
  USGS NHDPlus HR / NHD / WBD (public domain) and nClimGrid-Monthly (public
  domain). The ledger records source attribution but does not fetch new data.
- The PRISM Rights gate (`fulfillment.assert_sellable`) is unchanged. The
  ledger records the `rights_status` but does not re-implement the gate.
- The default 2D render stays byte-identical. The ledger is a parallel
  bookkeeping system. No `PIPELINE_STAGES` change. No `Settings` change. No
  `RunContext` change. A `build.py` run never reads or writes the ledger.
- `psycopg` (v3) is added to `requirements.txt` (lazy-imported, like the GIS
  stack). It is never imported at `src/` module top level.

## Out of Scope

- Customer-facing delivery portal or web page changes.
- Object storage (S3/MinIO) integration -- `library/` stays on filesystem/NAS.
- Automatic render queue or job scheduling via the database.
- Row-level security or multi-tenant access control.
- WAL archiving, streaming replication, or PITR automation.
- Web UI for the operator workspace (Postico 2 is the client).
- Changes to `src/fulfillment.py` pure logic or `GALLERY_MATRIX` source data.
- Payment/Stripe field migration into the ledger.
- Table partitioning for events or jobs.
- Connection pooling or async database access.
