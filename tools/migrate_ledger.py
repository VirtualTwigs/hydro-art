"""Apply SQL migrations to the operations ledger database.

Reads ``DATABASE_URL`` from the environment (or ``--database-url`` flag),
applies unapplied ``.sql`` files from ``migrations/`` in order, and records
each in a ``_migrations`` table.

Usage::

    python tools/migrate_ledger.py
    python tools/migrate_ledger.py --database-url postgresql://user:pass@host/db
    python tools/migrate_ledger.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def discover_migrations(migrations_dir: Path) -> list[tuple[str, str]]:
    """Return (filename, sql) pairs for numbered .sql files, sorted."""
    files = sorted(migrations_dir.glob("*.sql"))
    numbered = [(f.name, f.read_text("utf-8")) for f in files if re.match(r"^\d{3}_", f.name)]
    return numbered


def applied_migrations(conn) -> set[str]:
    """Return set of already-applied migration filenames."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT filename FROM _migrations")
        return {row[0] for row in cur.fetchall()}
    except Exception:
        conn.rollback()
        return set()


def apply_migration(conn, filename: str, sql: str) -> None:
    """Apply a single migration and record it."""
    cur = conn.cursor()
    cur.execute(sql)
    cur.execute(
        "INSERT INTO _migrations (filename) VALUES (%s)",
        (filename,),
    )
    conn.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply ledger migrations")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL connection URL (default: $DATABASE_URL)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List pending migrations without applying",
    )
    args = parser.parse_args(argv)

    if not args.database_url:
        print("ERROR: DATABASE_URL not set and --database-url not provided.", file=sys.stderr)
        return 1

    migrations = discover_migrations(MIGRATIONS_DIR)
    if not migrations:
        print("No migration files found in migrations/")
        return 0

    if args.dry_run:
        print(f"Found {len(migrations)} migration(s):")
        for filename, _ in migrations:
            print(f"  {filename}")
        print("(dry-run — no changes applied)")
        return 0

    try:
        import psycopg  # lazy import
    except ImportError:
        print("ERROR: psycopg not installed. pip install psycopg[binary]", file=sys.stderr)
        return 1

    conn = psycopg.connect(args.database_url, autocommit=False)
    try:
        already = applied_migrations(conn)
        pending = [(f, sql) for f, sql in migrations if f not in already]

        if not pending:
            print("All migrations already applied.")
            return 0

        print(f"Applying {len(pending)} migration(s)...")
        for filename, sql in pending:
            print(f"  → {filename}...", end=" ")
            apply_migration(conn, filename, sql)
            print("done")

        print(f"Applied {len(pending)} migration(s) successfully.")
        return 0
    except Exception as exc:
        conn.rollback()
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
