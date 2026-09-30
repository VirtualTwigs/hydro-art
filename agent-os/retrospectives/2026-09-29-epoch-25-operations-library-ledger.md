# Epoch 25 Retrospective — Operations Library, Samples & Analysis Ledger

**Date:** 2026-09-29
**Items:** #99–#106
**Suite at close:** 1734 passed (93 new tests)

## What shipped

An opt-in PostgreSQL operations ledger behind a `repository_factory` / `OrderRepository`
protocol. The JSON `OrderStore` remains the default — PostgreSQL activates only when
`DATABASE_URL` is set. The entire system is a parallel bookkeeping layer; the render
pipeline is completely untouched.

**Domain model (`src/ledger.py`):** 9 frozen entity dataclasses (`Place`, `Asset`,
`AssetLineage`, `RenderJob`, `BriefRevision`, `Delivery`, `AnalysisRun`, `AnalysisMetric`,
`LedgerEvent`), ID format validators, value validators (roles, visibility, rights status,
delivery access), `OrderRepository` protocol, and `repository_factory`.

**PostgreSQL adapter (`src/ledger_pg.py`):** `PgOrderRepository` with lazy `psycopg` import,
parameterized queries only, transactional writes (asset + lineage + event in one commit),
`LedgerError` on failure. Never blocks a render.

**Migrations:** 3 SQL files — core schema (9 tables, 6 indexes, constraints), analysis
evidence (2 tables), and 8 operator views for Postico 2 browsing. Email excluded from all
views.

**Tools:** `tools/migrate_ledger.py` (apply migrations), `tools/import_legacy.py`
(idempotent JSON→ledger import, dry-run default, rights gate).

**Integration:** `serve.py` reads `DATABASE_URL` from environment, falls back to
`OrderStore` on absence or connection failure.

## What went well

- **Protocol pattern is clean.** `OrderRepository` as a `runtime_checkable` Protocol
  means `OrderStore` satisfies it without any code changes to `src/orders.py`. The
  factory is the only decision point.
- **Offline discipline held perfectly.** 93 new tests, all offline. The PG adapter tests
  use a fake psycopg connection — no database needed. SQL files tested via parsing.
- **Migration tool is simple.** Plain numbered `.sql` files, no ORM, no framework. The
  `_migrations` tracker table is created by the first migration itself.

## What to watch

- **No real PG connection tested yet.** The offline tests verify SQL construction and
  protocol satisfaction, but the adapter hasn't been run against a live PostgreSQL
  instance. First real use should include a migration + import dry-run.
- **Delivery access window.** The 90-day access model is implemented in the schema and
  `validate_delivery_access`, but no automated expiry enforcement exists — it's a check,
  not a cron job.
- **Import tool scope.** `tools/import_legacy.py` handles existing JSON orders and
  catalog entries. It does not yet import analysis runs or render performance data.
