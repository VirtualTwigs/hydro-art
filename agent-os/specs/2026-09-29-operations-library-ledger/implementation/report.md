# Implementation Report: Operations Library, Samples & Analysis Ledger

## Epoch 25, #99-#106

### Summary

Implemented the full operations ledger system: a PostgreSQL-backed repository
behind a protocol abstraction, with SQL migrations, operator views, a legacy
import tool, and integration wiring -- all while preserving the existing JSON
OrderStore as a zero-configuration fallback and keeping the offline test suite
fully green.

### What was built

**Group 1 (prior):** Domain model + OrderRepository protocol in src/ledger.py.

**Group 2 (prior):** migrations/001_create_schema.sql + tools/migrate_ledger.py.

**Group 3 -- PostgreSQL adapter (src/ledger_pg.py):**
- PgOrderRepository satisfying the OrderRepository protocol
- Lazy psycopg import inside __init__ (never at module top level)
- All queries parameterized (%s placeholders, no string interpolation)
- Transactional writes: record_asset inserts asset + event in one commit
- LedgerError on connection/transaction failure
- 13 tests in tests/test_ledger_pg.py, all using fake cursor/connection

**Group 4 -- Analysis evidence model:**
- migrations/002_analysis_evidence.sql: analysis_runs and analysis_metrics
  tables with FK constraints, validation status checks, year range checks
- Added record_analysis_run, record_analysis_metric, get_analysis_for_place
  to PgOrderRepository
- 6 new tests in tests/test_ledger.py (analysis validation, ops_ prefix
  separation, value flexibility)

**Group 5 -- Postico 2 views:**
- migrations/003_operator_views.sql: 8 read-only operator views
- ops_active_work, ops_completed_work, ops_delivery_expiry,
  ops_rights_gaps, ops_render_failures, ops_library_candidates,
  ops_analysis_evidence, ops_orphans
- All views exclude customer email from output columns
- 11 tests in tests/test_ledger_views.py (SQL parsing, column presence, privacy)

**Group 6 -- Legacy import tool (tools/import_legacy.py):**
- Reads Request JSON, fulfillment manifests, CatalogStore entries
- --dry-run (default) / --apply modes
- Idempotent: re-import produces skips, not duplicates
- Rights gate: refuses approved_public without rights_status=cleared
- sys.path.insert shim for direct python tools/import_legacy.py execution
- 9 tests in tests/test_import_legacy.py using fake repository

**Group 7 -- Integration wiring:**
- serve.py now uses repository_factory(DATABASE_URL) via _build_order_store()
- Falls back gracefully to JSON OrderStore when no URL or connection fails
- 5 tests in tests/test_ledger_integration.py

### Test results

- Full offline suite: 1734 passed, 0 failed, 72 warnings
- Recipe roundtrip: 11/11 passed
- No regressions from prior epochs

### Invariants preserved

- Offline-suite discipline: psycopg never imported at module top level in src/.
- Dependency direction: src/ never imports tools/ or web/.
- Determinism: No PIPELINE_STAGES changes. 2D default render byte-identical.
- Rights gate: Import tool enforces approved_public requires rights_status=cleared.
