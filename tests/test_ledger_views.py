"""Tests for migrations/003_operator_views.sql — Postico 2 operator views.

Validates SQL syntax, expected view names, column presence, and privacy
(email exclusion). All tests are offline — they parse the SQL file, no
database connection required.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

VIEWS_SQL_PATH = Path(__file__).resolve().parent.parent / "migrations" / "003_operator_views.sql"

# Read once at module level (it's a static file, no I/O seam needed).
_SQL = VIEWS_SQL_PATH.read_text("utf-8")
_SQL_UPPER = _SQL.upper()

EXPECTED_VIEWS = (
    "ops_active_work",
    "ops_completed_work",
    "ops_delivery_expiry",
    "ops_rights_gaps",
    "ops_render_failures",
    "ops_library_candidates",
    "ops_analysis_evidence",
    "ops_orphans",
)


class TestViewsFileExists:
    def test_file_exists(self):
        assert VIEWS_SQL_PATH.is_file()

    def test_file_non_empty(self):
        assert len(_SQL.strip()) > 0


class TestAllViewsDefined:
    def test_all_eight_views_present(self):
        """All 8 expected views are defined with CREATE OR REPLACE VIEW."""
        for view in EXPECTED_VIEWS:
            pattern = rf"CREATE\s+OR\s+REPLACE\s+VIEW\s+{view}\s+AS"
            assert re.search(pattern, _SQL, re.IGNORECASE), (
                f"View {view} not found in 003_operator_views.sql"
            )

    def test_no_unexpected_views(self):
        """Only the 8 expected views are defined."""
        found = re.findall(
            r"CREATE\s+OR\s+REPLACE\s+VIEW\s+(\w+)\s+AS",
            _SQL,
            re.IGNORECASE,
        )
        assert set(found) == set(EXPECTED_VIEWS), (
            f"Unexpected views: {set(found) - set(EXPECTED_VIEWS)}"
        )


class TestEmailExclusion:
    def test_no_email_in_select_columns(self):
        """Views must not expose customer email in output columns.

        We check that 'email' does not appear as a selected column alias
        or bare column reference in any view's SELECT list.
        """
        # Split into per-view blocks
        view_blocks = re.split(
            r"CREATE\s+OR\s+REPLACE\s+VIEW",
            _SQL,
            flags=re.IGNORECASE,
        )
        for block in view_blocks[1:]:  # skip preamble
            # Extract the SELECT portion (between AS and the first FROM)
            select_match = re.search(
                r"AS\s+SELECT\s+(.*?)FROM\s",
                block,
                re.IGNORECASE | re.DOTALL,
            )
            if select_match:
                select_clause = select_match.group(1)
                # email should not appear as a column reference
                # (r.email, email, etc.)
                assert not re.search(
                    r'\bemail\b',
                    select_clause,
                    re.IGNORECASE,
                ), f"View exposes 'email' column: {block[:80]}..."


class TestViewColumnPresence:
    def test_active_work_has_required_columns(self):
        """ops_active_work must include request_id, status, region, age."""
        block = _extract_view_block("ops_active_work")
        for col in ("request_id", "status", "region", "age"):
            assert col in block.lower(), (
                f"ops_active_work missing column: {col}"
            )

    def test_rights_gaps_has_rights_columns(self):
        """ops_rights_gaps must include rights_status, source_attribution."""
        block = _extract_view_block("ops_rights_gaps")
        for col in ("rights_status", "source_attribution"):
            assert col in block.lower(), (
                f"ops_rights_gaps missing column: {col}"
            )

    def test_delivery_expiry_has_expiry_status(self):
        """ops_delivery_expiry must include expiry_status or equivalent."""
        block = _extract_view_block("ops_delivery_expiry")
        assert "expiry_status" in block.lower() or "expired" in block.lower()

    def test_analysis_evidence_has_validation_status(self):
        """ops_analysis_evidence must include validation_status."""
        block = _extract_view_block("ops_analysis_evidence")
        assert "validation_status" in block.lower()


class TestSqlSyntax:
    def test_views_use_select(self):
        """Every view body is a SELECT statement."""
        for view in EXPECTED_VIEWS:
            block = _extract_view_block(view)
            assert "SELECT" in block.upper(), (
                f"View {view} does not contain SELECT"
            )

    def test_no_python_interpolation(self):
        """No Python string interpolation patterns in SQL."""
        assert "{}" not in _SQL
        assert ".format(" not in _SQL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_view_block(view_name: str) -> str:
    """Extract the SQL block for a named view."""
    pattern = rf"(CREATE\s+OR\s+REPLACE\s+VIEW\s+{view_name}\s+AS\s+.*?)(?=CREATE\s+OR\s+REPLACE\s+VIEW|\Z)"
    match = re.search(pattern, _SQL, re.IGNORECASE | re.DOTALL)
    assert match, f"Could not extract view block for {view_name}"
    return match.group(1)
