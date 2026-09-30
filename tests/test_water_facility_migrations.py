"""Opt-in integration tests for water-facility PostGIS migrations.

These tests require a running PostgreSQL instance with PostGIS and are
excluded from the normal offline suite via the ``database`` marker.

Run with: ``pytest -m database tests/test_water_facility_migrations.py``

Requires ``DATABASE_URL`` env var pointing to a test database.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.database

# Skip the entire module if no DATABASE_URL
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL not set — skipping database tests", allow_module_level=True)


def _connect():
    """Lazy-import psycopg and connect."""
    import psycopg  # type: ignore[import-untyped]  # pragma: no cover

    return psycopg.connect(DATABASE_URL)  # pragma: no cover


def _read_migration() -> str:
    """Read the water-facility migration SQL."""
    from pathlib import Path  # pragma: no cover

    return (Path(__file__).resolve().parent.parent / "migrations" / "004_water_facility_schema.sql").read_text()  # pragma: no cover


class TestMigrationUp:
    """Apply the migration and verify tables/indexes exist."""

    def test_migration_creates_tables(self):  # pragma: no cover
        conn = _connect()
        try:
            with conn.cursor() as cur:
                # Apply migration
                sql = _read_migration()
                cur.execute(sql)
                conn.commit()

                # Check core tables exist
                cur.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name IN (
                        'facilities', 'facility_identifiers',
                        'facility_geometry', 'water_measurements',
                        'facility_evidence', 'water_claims',
                        'water_claim_evidence', 'facility_relationships',
                        'service_areas', 'source_snapshots',
                        'source_records', 'state_source_registry',
                        'data_alerts'
                    )
                    ORDER BY table_name
                """)
                tables = {row[0] for row in cur.fetchall()}
                expected = {
                    "facilities", "facility_identifiers",
                    "facility_geometry", "water_measurements",
                    "facility_evidence", "water_claims",
                    "water_claim_evidence", "facility_relationships",
                    "service_areas", "source_snapshots",
                    "source_records", "state_source_registry",
                    "data_alerts",
                }
                assert tables == expected, f"Missing tables: {expected - tables}"
        finally:
            conn.close()

    def test_public_claims_view_exists(self):  # pragma: no cover
        conn = _connect()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name FROM information_schema.views
                    WHERE table_schema = 'public'
                    AND table_name = 'public_water_claims'
                """)
                assert cur.fetchone() is not None
        finally:
            conn.close()

    def test_facility_class_constraint(self):  # pragma: no cover
        """Invalid facility_class should be rejected by CHECK constraint."""
        conn = _connect()
        try:
            with conn.cursor() as cur:
                fid = str(uuid.uuid4())
                with pytest.raises(Exception):
                    cur.execute(
                        """INSERT INTO facilities
                           (id, name, facility_class, jurisdiction)
                           VALUES (%s, %s, %s, %s)""",
                        (fid, "Bad Facility", "spaceship", "TX"),
                    )
                conn.rollback()
        finally:
            conn.close()

    def test_identifier_authority_uniqueness(self):  # pragma: no cover
        """Duplicate (authority, external_id) should be rejected."""
        conn = _connect()
        try:
            with conn.cursor() as cur:
                fac_id = str(uuid.uuid4())
                cur.execute(
                    """INSERT INTO facilities
                       (id, name, facility_class, jurisdiction)
                       VALUES (%s, %s, %s, %s)""",
                    (fac_id, "Test Plant", "wastewater", "TX"),
                )
                id1 = str(uuid.uuid4())
                id2 = str(uuid.uuid4())
                cur.execute(
                    """INSERT INTO facility_identifiers
                       (id, facility_id, authority, external_id)
                       VALUES (%s, %s, %s, %s)""",
                    (id1, fac_id, "EPA_FRS", "12345"),
                )
                with pytest.raises(Exception):
                    cur.execute(
                        """INSERT INTO facility_identifiers
                           (id, facility_id, authority, external_id)
                           VALUES (%s, %s, %s, %s)""",
                        (id2, fac_id, "EPA_FRS", "12345"),
                    )
                conn.rollback()
        finally:
            conn.close()
