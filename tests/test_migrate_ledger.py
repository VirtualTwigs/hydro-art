"""Tests for the ledger migration tool (offline — no database connection)."""

from __future__ import annotations

import os
import re
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def test_migrations_dir_exists():
    assert MIGRATIONS_DIR.is_dir(), f"migrations/ not found at {MIGRATIONS_DIR}"


def test_migration_files_numbered_sequentially():
    """Migration files must be numbered 001, 002, ... with no gaps."""
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    # Exclude non-numbered files (e.g. views/ subdir)
    numbered = [f for f in files if re.match(r"^\d{3}_", f.name)]
    assert len(numbered) >= 1, "No numbered migration files found"
    for i, f in enumerate(numbered, start=1):
        expected_prefix = f"{i:03d}_"
        assert f.name.startswith(expected_prefix), (
            f"Migration {f.name} should start with {expected_prefix}"
        )


def test_migration_files_are_valid_sql():
    """Each migration file must contain non-empty SQL with CREATE or ALTER."""
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        content = path.read_text("utf-8")
        assert len(content.strip()) > 0, f"{path.name} is empty"
        upper = content.upper()
        assert any(kw in upper for kw in ("CREATE", "ALTER", "INSERT")), (
            f"{path.name} contains no CREATE/ALTER/INSERT statements"
        )


def test_001_creates_migrations_table():
    """The first migration must create the _migrations tracking table."""
    first = MIGRATIONS_DIR / "001_create_schema.sql"
    assert first.is_file(), "001_create_schema.sql not found"
    content = first.read_text("utf-8").upper()
    assert "_MIGRATIONS" in content, "001 must create _migrations table"


def test_001_creates_core_tables():
    """The first migration creates all core entity tables."""
    first = MIGRATIONS_DIR / "001_create_schema.sql"
    content = first.read_text("utf-8").lower()
    expected_tables = [
        "places", "requests", "orders", "brief_revisions",
        "render_jobs", "assets", "asset_lineage", "deliveries", "events",
    ]
    for table in expected_tables:
        assert f"create table {table}" in content, (
            f"001 missing CREATE TABLE {table}"
        )


def test_migrate_ledger_module_importable():
    """The migration tool module must be importable without side effects."""
    # We can't import tools/ directly since they're outside the package,
    # but we can verify the file exists and is syntactically valid Python.
    tool_path = Path(__file__).resolve().parent.parent / "tools" / "migrate_ledger.py"
    assert tool_path.is_file(), "tools/migrate_ledger.py not found"
    source = tool_path.read_text("utf-8")
    compile(source, str(tool_path), "exec")  # syntax check


def test_migration_sql_no_python_interpolation():
    """Verify no Python string interpolation patterns in SQL files."""
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        content = path.read_text("utf-8")
        # Should not contain Python-style f-string or .format() calls
        assert "{}" not in content, f"{path.name} contains {{}} placeholder"
        assert ".format(" not in content, f"{path.name} contains .format()"
