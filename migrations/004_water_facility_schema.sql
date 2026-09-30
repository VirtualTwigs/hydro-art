-- Migration 004: Water-facility and data-center intelligence schema
-- Target: PostgreSQL >= 15 with PostGIS
--
-- Standalone subsystem: not the operations ledger.  Requires PostGIS for
-- geometry columns (facility_geometry, service_area).
--
-- Roles (same as ledger; create manually before running):
--   hydro_migrator   — runs migrations, owns tables
--   hydro_app_writer — application writes
--   hydro_ops_readonly — read-only browsing
--
-- Usage: python tools/migrate_ledger.py
-- Rollback: see DOWN section at the bottom of this file.

-- Ensure PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- -----------------------------------------------------------------------
-- Source provenance
-- -----------------------------------------------------------------------

CREATE TABLE source_snapshots (
    id                UUID PRIMARY KEY,
    source_family     TEXT NOT NULL,
    source_url        TEXT NOT NULL,
    retrieval_time    TIMESTAMPTZ NOT NULL,
    content_checksum  TEXT NOT NULL,
    parser_version    TEXT NOT NULL,
    record_count      INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_source_snapshots_family ON source_snapshots (source_family);

CREATE TABLE source_records (
    id                UUID PRIMARY KEY,
    snapshot_id       UUID NOT NULL REFERENCES source_snapshots (id),
    source_key        TEXT NOT NULL,
    content_checksum  TEXT NOT NULL,
    raw_payload       JSONB NOT NULL,
    UNIQUE (snapshot_id, source_key)
);

CREATE INDEX idx_source_records_snapshot ON source_records (snapshot_id);

-- -----------------------------------------------------------------------
-- State source registry
-- -----------------------------------------------------------------------

CREATE TABLE state_source_registry (
    id                    UUID PRIMARY KEY,
    jurisdiction          TEXT NOT NULL,
    program               TEXT NOT NULL,
    agency                TEXT NOT NULL,
    url                   TEXT NOT NULL,
    access_method         TEXT NOT NULL
        CHECK (access_method IN (
            'api', 'bulk_file', 'arcgis_service',
            'html_download', 'manual_record_request')),
    data_format           TEXT NOT NULL,
    coverage              TEXT NOT NULL,
    update_cadence        TEXT NOT NULL,
    license               TEXT NOT NULL,
    field_mapping_version TEXT NOT NULL,
    geometry_quality      TEXT NOT NULL,
    publication_lag_days  INTEGER,
    verified              BOOLEAN NOT NULL DEFAULT FALSE,
    last_verified         TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (jurisdiction, program)
);

CREATE INDEX idx_state_source_jurisdiction ON state_source_registry (jurisdiction);

-- -----------------------------------------------------------------------
-- Facilities
-- -----------------------------------------------------------------------

CREATE TABLE facilities (
    id                   UUID PRIMARY KEY,
    name                 TEXT NOT NULL,
    facility_class       TEXT NOT NULL
        CHECK (facility_class IN (
            'drinking_water', 'wastewater', 'industrial',
            'power_generation', 'data_center', 'agriculture',
            'mining', 'dam', 'other')),
    jurisdiction         TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'active',
    water_relevance      TEXT NOT NULL DEFAULT 'unknown'
        CHECK (water_relevance IN (
            'candidate', 'permitted_or_committed', 'confirmed', 'unknown')),
    identity_confidence  NUMERIC NOT NULL DEFAULT 0,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_facilities_jurisdiction ON facilities (jurisdiction);
CREATE INDEX idx_facilities_class ON facilities (facility_class);
CREATE INDEX idx_facilities_relevance ON facilities (water_relevance);

-- -----------------------------------------------------------------------
-- Facility identifiers (external authority + ID)
-- -----------------------------------------------------------------------

CREATE TABLE facility_identifiers (
    id                UUID PRIMARY KEY,
    facility_id       UUID NOT NULL REFERENCES facilities (id),
    authority         TEXT NOT NULL,
    external_id       TEXT NOT NULL,
    source_record_id  UUID REFERENCES source_records (id),
    UNIQUE (authority, external_id)
);

CREATE INDEX idx_facility_identifiers_facility ON facility_identifiers (facility_id);

-- -----------------------------------------------------------------------
-- Facility geometry (PostGIS)
-- -----------------------------------------------------------------------

CREATE TABLE facility_geometry (
    id                UUID PRIMARY KEY,
    facility_id       UUID NOT NULL REFERENCES facilities (id),
    geom              geometry NOT NULL,
    crs               TEXT NOT NULL DEFAULT 'EPSG:4326',
    method            TEXT NOT NULL,
    accuracy_m        NUMERIC,
    source_record_id  UUID REFERENCES source_records (id),
    valid_time_start  TIMESTAMPTZ NOT NULL,
    valid_time_end    TIMESTAMPTZ
);

CREATE INDEX idx_facility_geometry_facility ON facility_geometry (facility_id);
CREATE INDEX idx_facility_geometry_geom ON facility_geometry USING GIST (geom);

-- -----------------------------------------------------------------------
-- Water measurements (bitemporal)
-- -----------------------------------------------------------------------

CREATE TABLE water_measurements (
    id                UUID PRIMARY KEY,
    facility_id       UUID NOT NULL REFERENCES facilities (id),
    measure_type      TEXT NOT NULL
        CHECK (measure_type IN (
            'withdrawal', 'delivered', 'consumed',
            'discharged', 'authorized_capacity')),
    quantity_status   TEXT NOT NULL
        CHECK (quantity_status IN (
            'measured', 'reported', 'authorized', 'unavailable')),
    value             NUMERIC,
    source_unit       TEXT NOT NULL,
    canonical_value   NUMERIC,
    canonical_unit    TEXT NOT NULL,
    conversion_method TEXT NOT NULL,
    confidence        NUMERIC NOT NULL DEFAULT 0,
    period_start      TIMESTAMPTZ NOT NULL,
    period_end        TIMESTAMPTZ NOT NULL,
    valid_time_start  TIMESTAMPTZ NOT NULL,
    valid_time_end    TIMESTAMPTZ NOT NULL,
    system_time       TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_record_id  UUID REFERENCES source_records (id),
    CHECK (period_start <= period_end),
    CHECK (valid_time_start <= valid_time_end)
);

CREATE INDEX idx_water_measurements_facility ON water_measurements (facility_id);
CREATE INDEX idx_water_measurements_type ON water_measurements (measure_type);
CREATE INDEX idx_water_measurements_period ON water_measurements (period_start, period_end);

-- -----------------------------------------------------------------------
-- Evidence
-- -----------------------------------------------------------------------

CREATE TABLE facility_evidence (
    id                UUID PRIMARY KEY,
    facility_id       UUID NOT NULL REFERENCES facilities (id),
    source_url        TEXT,
    file_key          TEXT,
    row_locator       TEXT,
    publisher         TEXT NOT NULL,
    publication_date  TIMESTAMPTZ,
    retrieval_date    TIMESTAMPTZ NOT NULL,
    review_status     TEXT NOT NULL DEFAULT 'unreviewed'
        CHECK (review_status IN ('unreviewed', 'reviewed', 'rejected')),
    content_checksum  TEXT NOT NULL
);

CREATE INDEX idx_facility_evidence_facility ON facility_evidence (facility_id);

-- -----------------------------------------------------------------------
-- Water claims (bitemporal, evidence-backed)
-- -----------------------------------------------------------------------

CREATE TABLE water_claims (
    id                    UUID PRIMARY KEY,
    facility_id           UUID NOT NULL REFERENCES facilities (id),
    subject               TEXT NOT NULL,
    predicate             TEXT NOT NULL,
    value                 NUMERIC,
    unit                  TEXT NOT NULL,
    measure_type          TEXT NOT NULL
        CHECK (measure_type IN (
            'withdrawal', 'delivered', 'consumed',
            'discharged', 'authorized_capacity')),
    quantity_status       TEXT NOT NULL
        CHECK (quantity_status IN (
            'measured', 'reported', 'authorized', 'unavailable')),
    display_eligibility   TEXT NOT NULL DEFAULT 'internal_only'
        CHECK (display_eligibility IN (
            'internal_only', 'review_required',
            'publishable_precise', 'publishable_generalized', 'excluded')),
    confidence            NUMERIC NOT NULL DEFAULT 0,
    valid_time_start      TIMESTAMPTZ NOT NULL,
    valid_time_end        TIMESTAMPTZ NOT NULL,
    system_time           TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewer              TEXT,
    review_time           TIMESTAMPTZ,
    CHECK (valid_time_start <= valid_time_end)
);

CREATE INDEX idx_water_claims_facility ON water_claims (facility_id);
CREATE INDEX idx_water_claims_eligibility ON water_claims (display_eligibility);

-- Junction: claim ↔ evidence (many-to-many)
CREATE TABLE water_claim_evidence (
    claim_id     UUID NOT NULL REFERENCES water_claims (id),
    evidence_id  UUID NOT NULL REFERENCES facility_evidence (id),
    PRIMARY KEY (claim_id, evidence_id)
);

-- -----------------------------------------------------------------------
-- Facility relationships
-- -----------------------------------------------------------------------

CREATE TABLE facility_relationships (
    id                   UUID PRIMARY KEY,
    source_facility_id   UUID NOT NULL REFERENCES facilities (id),
    target_facility_id   UUID NOT NULL REFERENCES facilities (id),
    relationship_type    TEXT NOT NULL,
    evidence_id          UUID REFERENCES facility_evidence (id),
    valid_time_start     TIMESTAMPTZ NOT NULL,
    valid_time_end       TIMESTAMPTZ
);

CREATE INDEX idx_facility_rel_source ON facility_relationships (source_facility_id);
CREATE INDEX idx_facility_rel_target ON facility_relationships (target_facility_id);

-- -----------------------------------------------------------------------
-- Service areas (PostGIS)
-- -----------------------------------------------------------------------

CREATE TABLE service_areas (
    id                UUID PRIMARY KEY,
    facility_id       UUID NOT NULL REFERENCES facilities (id),
    geom              geometry NOT NULL,
    crs               TEXT NOT NULL DEFAULT 'EPSG:4326',
    method            TEXT NOT NULL
        CHECK (method IN ('published', 'modeled')),
    source_record_id  UUID REFERENCES source_records (id),
    valid_time_start  TIMESTAMPTZ NOT NULL,
    valid_time_end    TIMESTAMPTZ
);

CREATE INDEX idx_service_areas_facility ON service_areas (facility_id);
CREATE INDEX idx_service_areas_geom ON service_areas USING GIST (geom);

-- -----------------------------------------------------------------------
-- Data alerts
-- -----------------------------------------------------------------------

CREATE TABLE data_alerts (
    id               UUID PRIMARY KEY,
    authority        TEXT NOT NULL,
    program          TEXT NOT NULL,
    geography        TEXT,
    severity         TEXT NOT NULL
        CHECK (severity IN ('info', 'warning', 'critical')),
    message          TEXT NOT NULL,
    source_url       TEXT,
    effective_start  TIMESTAMPTZ NOT NULL,
    effective_end    TIMESTAMPTZ,
    superseded_by    UUID REFERENCES data_alerts (id),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_data_alerts_authority ON data_alerts (authority, program);

-- -----------------------------------------------------------------------
-- Public claim view (only publishable claims reach customers)
-- -----------------------------------------------------------------------

CREATE OR REPLACE VIEW public_water_claims AS
SELECT
    wc.id,
    wc.facility_id,
    f.name AS facility_name,
    f.facility_class,
    f.jurisdiction,
    wc.subject,
    wc.predicate,
    wc.value,
    wc.unit,
    wc.measure_type,
    wc.quantity_status,
    wc.display_eligibility,
    wc.confidence,
    wc.valid_time_start,
    wc.valid_time_end,
    wc.reviewer,
    wc.review_time
FROM water_claims wc
JOIN facilities f ON f.id = wc.facility_id
WHERE wc.display_eligibility IN ('publishable_precise', 'publishable_generalized');

-- -----------------------------------------------------------------------
-- DOWN (rollback — run in reverse order)
-- -----------------------------------------------------------------------
-- DROP VIEW IF EXISTS public_water_claims;
-- DROP TABLE IF EXISTS data_alerts;
-- DROP TABLE IF EXISTS service_areas;
-- DROP TABLE IF EXISTS facility_relationships;
-- DROP TABLE IF EXISTS water_claim_evidence;
-- DROP TABLE IF EXISTS water_claims;
-- DROP TABLE IF EXISTS facility_evidence;
-- DROP TABLE IF EXISTS water_measurements;
-- DROP TABLE IF EXISTS facility_geometry;
-- DROP TABLE IF EXISTS facility_identifiers;
-- DROP TABLE IF EXISTS facilities;
-- DROP TABLE IF EXISTS state_source_registry;
-- DROP TABLE IF EXISTS source_records;
-- DROP TABLE IF EXISTS source_snapshots;
