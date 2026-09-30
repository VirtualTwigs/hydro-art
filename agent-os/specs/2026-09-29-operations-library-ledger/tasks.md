# Tasks — Operations Library, Samples & Analysis Ledger (Epoch 25, #99–#106)

## Group 1 — Domain model & repository protocol (#99, #106 partial)

Tests first, then implementation. All pure/offline — no database.

- [x] 1.1 Write `tests/test_ledger.py` Group 1 (entity dataclasses + ID helpers + validation) — ~18 tests
  - `Place`, `Asset`, `AssetLineage`, `RenderJob`, `BriefRevision`, `Delivery`, `AnalysisRun`, `AnalysisMetric`, `LedgerEvent` frozen dataclasses
  - ID format validators: `validate_request_id`, `validate_order_id`, `validate_asset_id`, `validate_delivery_id`
  - `validate_asset_role` against closed role set
  - `validate_visibility` (internal | approved_public)
  - `validate_rights_status` (pending | cleared | restricted)
  - `validate_delivery_access` returns expired/active/revoked
  - `LedgerError` exception
- [x] 1.2 Implement `src/ledger.py`: entity dataclasses, ID helpers, validators, `LedgerError`, `ASSET_ROLES`, `VISIBILITY_VALUES`, `RIGHTS_STATUSES`
- [x] 1.3 Write `tests/test_ledger.py` Group 2 (repository protocol + factory) — ~6 tests
  - `OrderRepository` protocol definition
  - `repository_factory(None)` returns `OrderStore`
  - `repository_factory("postgresql://...")` returns `PgOrderRepository` (import check only, no connection)
  - Protocol compatibility: `OrderStore` satisfies `OrderRepository`
- [x] 1.4 Implement `OrderRepository` protocol in `src/ledger.py`, `repository_factory`
- [x] 1.5 Run Group 1+2 tests — all green

## Group 2 — SQL migrations & migration tool (#99, #100)

- [x] 2.1 Create `migrations/001_create_schema.sql`: `_migrations` tracker table, `places`, `requests`, `orders`, `brief_revisions`, `render_jobs`, `assets`, `asset_lineage`, `deliveries`, `events` tables with constraints, indexes, and role documentation
- [x] 2.2 Write `tests/test_migrate_ledger.py` — ~4 tests (migration file parsing, ordering, SQL syntax validation, idempotency check on `_migrations` table logic)
- [x] 2.3 Implement `tools/migrate_ledger.py`: read `DATABASE_URL`, apply unapplied `.sql` files, record in `_migrations`
- [x] 2.4 Run Group 2 tests — all green

## Group 3 — PostgreSQL adapter (#102)

- [x] 3.1 Write `tests/test_ledger_pg.py` — ~12 tests (all offline, using fakes/mocks for psycopg)
  - `PgOrderRepository.__init__` lazily imports psycopg
  - `create_request` builds correct INSERT
  - `get` builds correct SELECT
  - `update_status` validates transition before UPDATE
  - `record_asset` transactional: asset INSERT + lineage INSERT + event INSERT
  - `record_delivery` sets `access_expires_at` = `delivered_at` + 90 days
  - `get_assets_for_order` returns `list[Asset]`
  - `validate_delivery_access` returns correct status for active/expired/revoked
  - `LedgerError` on connection failure
  - Parameterized queries (no string interpolation)
- [x] 3.2 Implement `src/ledger_pg.py`: `PgOrderRepository` satisfying `OrderRepository` protocol, lazy `psycopg` import, parameterized queries, transactional writes
- [x] 3.3 Run Group 3 tests — all green

## Group 4 — Analysis evidence model (#104)

- [x] 4.1 Create `migrations/002_analysis_evidence.sql`: `analysis_runs`, `analysis_metrics` tables with FK to `places`, `render_jobs`, `assets`; method/version columns; validation status constraints
- [x] 4.2 Write `tests/test_ledger.py` Group 3 (analysis model) — ~6 tests
  - `AnalysisRun` and `AnalysisMetric` validation
  - Business vs. hydrology metric separation (`ops_*` prefix)
  - `validation_status` constraints (draft | validated | reference_only | unvalidated)
- [x] 4.3 Add analysis methods to `PgOrderRepository`: `record_analysis_run`, `record_analysis_metric`, `get_analysis_for_place`
- [x] 4.4 Run Group 4 tests — all green

## Group 5 — Postico 2 views (#105)

- [x] 5.1 Create `migrations/003_operator_views.sql`: 8 read-only views (`ops_active_work`, `ops_completed_work`, `ops_delivery_expiry`, `ops_rights_gaps`, `ops_render_failures`, `ops_library_candidates`, `ops_analysis_evidence`, `ops_orphans`)
- [x] 5.2 Write `tests/test_ledger_views.py` — ~8 tests (SQL syntax validation, column lists, email exclusion check via SQL parsing)
- [x] 5.3 Run Group 5 tests — all green

## Group 6 — Legacy import tool (#103)

- [x] 6.1 Write `tests/test_import_legacy.py` — ~8 tests (offline, using fake repository)
  - Reads `Request` JSON files and creates ledger records
  - Reads fulfillment manifests for asset checksums
  - Reads `CatalogStore` entries for sample records
  - Dry-run produces counts without mutations
  - Idempotent: re-import produces no duplicates
  - Refuses `approved_public` without `rights_status=cleared`
  - Checksum mismatch warning
- [x] 6.2 Implement `tools/import_legacy.py`: `--dry-run` (default) / `--apply`, `--orders-dir`, `--catalog-file`, creates/updates/skips/conflicts report
- [x] 6.3 Run Group 6 tests — all green

## Group 7 — Integration & close (#106, #153)

- [x] 7.1 Wire `repository_factory` into `src/server.py` startup (reads `DATABASE_URL` from env, passes to factory)
- [x] 7.2 Write integration tests — ~4 tests
  - `server.py` uses `OrderStore` when no `DATABASE_URL`
  - `server.py` uses `PgOrderRepository` when `DATABASE_URL` set (mock connection)
  - JSON fallback: full order lifecycle without database
  - Render byte-identity: same recipe produces same hash with and without ledger
- [x] 7.3 Run full offline test suite — all green, no regressions
- [x] 7.4 Run recipe roundtrip — all green
- [x] 7.5 Write `implementation/report.md`
