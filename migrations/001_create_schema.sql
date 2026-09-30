-- Migration 001: Core operations ledger schema
-- Target: PostgreSQL >= 15
--
-- Roles (create manually before running migrations):
--   hydro_migrator   — runs migrations, owns tables
--   hydro_app_writer — application writes (INSERT/UPDATE/DELETE)
--   hydro_ops_readonly — Postico 2 read-only browsing
--   hydro_backup     — backup/PITR process only
--
-- Usage: python tools/migrate_ledger.py

-- Migration tracking table
CREATE TABLE IF NOT EXISTS _migrations (
    id          SERIAL PRIMARY KEY,
    filename    TEXT NOT NULL UNIQUE,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Geographic identity
CREATE TABLE places (
    place_id     TEXT PRIMARY KEY,
    region       TEXT NOT NULL,
    county       TEXT,
    huc4         TEXT,
    display_name TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_places_region ON places (region);

-- Customer requests (intake)
CREATE TABLE requests (
    request_id  TEXT PRIMARY KEY,  -- REQ-YYYYMMDD-####
    email       TEXT NOT NULL,
    product     TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'submitted',
    place_id    TEXT REFERENCES places(place_id),
    payload     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_request_id_format CHECK (request_id ~ '^REQ-\d{8}-\d{4}$'),
    CONSTRAINT chk_request_status CHECK (status IN (
        'submitted', 'accepted', 'rendering', 'proof_ready',
        'approved', 'fulfilled', 'revision_requested', 'render_failed',
        'payment_pending', 'paid'
    ))
);

-- Accepted commissions
CREATE TABLE orders (
    order_id    TEXT PRIMARY KEY,  -- ORD-YYYYMMDD-####
    request_id  TEXT NOT NULL REFERENCES requests(request_id),
    place_id    TEXT REFERENCES places(place_id),
    style       TEXT,
    recipe_digest TEXT,
    notes       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_order_id_format CHECK (order_id ~ '^ORD-\d{8}-\d{4}$')
);

-- Immutable brief snapshots
CREATE TABLE brief_revisions (
    brief_id    TEXT PRIMARY KEY,  -- BRF-<order>-rN
    order_id    TEXT NOT NULL REFERENCES orders(order_id),
    revision    INTEGER NOT NULL,
    content     JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_brief_revision_positive CHECK (revision >= 1),
    UNIQUE (order_id, revision)
);

-- Render attempts
CREATE TABLE render_jobs (
    job_id      TEXT PRIMARY KEY,  -- JOB-<order>-rN
    order_id    TEXT NOT NULL REFERENCES orders(order_id),
    brief_id    TEXT REFERENCES brief_revisions(brief_id),
    status      TEXT NOT NULL DEFAULT 'pending',
    recipe_digest TEXT,
    code_revision TEXT,
    input_sources JSONB,
    started_at  TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_job_status CHECK (status IN (
        'pending', 'running', 'succeeded', 'failed', 'cancelled'
    ))
);

CREATE INDEX idx_render_jobs_status ON render_jobs (status, created_at DESC);

-- Immutable generated assets
CREATE TABLE assets (
    asset_id        TEXT PRIMARY KEY,  -- AST-<order>-<role>-rN
    order_id        TEXT REFERENCES orders(order_id),
    render_job_id   TEXT REFERENCES render_jobs(job_id),
    analysis_run_id TEXT,  -- FK added in 002_analysis_evidence.sql
    role            TEXT NOT NULL,
    storage_key     TEXT,  -- relative path, never absolute
    checksum_sha256 TEXT,
    byte_count      BIGINT,
    width_px        INTEGER,
    height_px       INTEGER,
    media_type      TEXT,
    visibility      TEXT NOT NULL DEFAULT 'internal',
    rights_status   TEXT NOT NULL DEFAULT 'pending',
    source_attribution TEXT,
    retention_class TEXT,
    retain_until    TIMESTAMPTZ,
    deleted_at      TIMESTAMPTZ,
    detail          JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_asset_role CHECK (role IN (
        'source_reference', 'recipe', 'run_log', 'proof', 'final',
        'print', 'vector', 'report', 'figure', 'animation',
        'thumbnail', 'bundle', 'license', 'customer_reference'
    )),
    CONSTRAINT chk_visibility CHECK (visibility IN ('internal', 'approved_public')),
    CONSTRAINT chk_rights_status CHECK (rights_status IN ('pending', 'cleared', 'restricted')),
    CONSTRAINT uq_asset_checksum_per_order UNIQUE (order_id, checksum_sha256)
);

CREATE INDEX idx_assets_order_role ON assets (order_id, role, created_at DESC);
CREATE INDEX idx_assets_visibility_rights ON assets (visibility, rights_status, created_at DESC);
CREATE INDEX idx_assets_checksum ON assets (checksum_sha256);

-- Asset derivation graph
CREATE TABLE asset_lineage (
    id          SERIAL PRIMARY KEY,
    parent_id   TEXT NOT NULL REFERENCES assets(asset_id),
    child_id    TEXT NOT NULL REFERENCES assets(asset_id),
    relationship TEXT NOT NULL DEFAULT 'derived_from',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_no_self_lineage CHECK (parent_id != child_id),
    UNIQUE (parent_id, child_id)
);

-- Time-limited customer access grants
CREATE TABLE deliveries (
    delivery_id       TEXT PRIMARY KEY,  -- DLV-<order>-N
    order_id          TEXT NOT NULL REFERENCES orders(order_id),
    delivered_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    access_expires_at TIMESTAMPTZ NOT NULL,
    access_revoked_at TIMESTAMPTZ,
    asset_ids         TEXT[] NOT NULL,
    reason            TEXT,
    fee_waived        BOOLEAN NOT NULL DEFAULT false,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_expiry_after_delivery CHECK (access_expires_at > delivered_at)
);

CREATE INDEX idx_deliveries_expiry ON deliveries (access_expires_at)
    WHERE access_revoked_at IS NULL;

-- Append-only audit trail (polymorphic entity reference)
CREATE TABLE events (
    event_id    SERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL,  -- 'request', 'order', 'asset', 'delivery', etc.
    entity_id   TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    event_name  TEXT NOT NULL,
    actor       TEXT,
    detail      JSONB,

    CONSTRAINT chk_entity_type CHECK (entity_type IN (
        'request', 'order', 'brief', 'job', 'asset', 'delivery',
        'analysis_run', 'analysis_metric'
    ))
);

CREATE INDEX idx_events_entity ON events (entity_type, entity_id, occurred_at DESC);
