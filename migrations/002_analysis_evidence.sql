-- Migration 002: Analysis evidence model
-- Target: PostgreSQL >= 15
--
-- Adds tables for recording analysis runs and their computed metrics,
-- linked to places and optionally to render jobs and assets.
-- Business metrics use an 'ops_' method prefix to stay disjoint from
-- hydrology metrics.

-- Analysis runs (scoped to a place and time range)
CREATE TABLE analysis_runs (
    run_id            TEXT PRIMARY KEY,
    place_id          TEXT NOT NULL REFERENCES places(place_id),
    recipe_digest     TEXT,
    code_revision     TEXT,
    input_sources     JSONB,
    start_year        INTEGER NOT NULL,
    end_year          INTEGER NOT NULL,
    metric_version    TEXT NOT NULL,
    validation_status TEXT NOT NULL DEFAULT 'draft',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewer          TEXT,
    notes             TEXT,

    CONSTRAINT chk_analysis_years CHECK (end_year >= start_year),
    CONSTRAINT chk_validation_status CHECK (validation_status IN (
        'draft', 'validated', 'reference_only', 'unvalidated'
    ))
);

CREATE INDEX idx_analysis_runs_place ON analysis_runs (place_id, created_at DESC);
CREATE INDEX idx_analysis_runs_status ON analysis_runs (validation_status, created_at DESC);

-- Individual metrics from an analysis run
CREATE TABLE analysis_metrics (
    metric_id             TEXT PRIMARY KEY,
    run_id                TEXT NOT NULL REFERENCES analysis_runs(run_id),
    name                  TEXT NOT NULL,
    units                 TEXT NOT NULL,
    method                TEXT NOT NULL,
    method_version        TEXT NOT NULL,
    value                 JSONB,
    interpretation_status TEXT NOT NULL DEFAULT 'draft',
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_interpretation_status CHECK (interpretation_status IN (
        'draft', 'validated', 'unvalidated', 'reference_only'
    ))
);

CREATE INDEX idx_analysis_metrics_run ON analysis_metrics (run_id, created_at DESC);
CREATE INDEX idx_analysis_metrics_method ON analysis_metrics (method, name);

-- Add FK from assets to analysis_runs (column already exists in 001 as TEXT)
ALTER TABLE assets
    ADD CONSTRAINT fk_assets_analysis_run
    FOREIGN KEY (analysis_run_id) REFERENCES analysis_runs(run_id);
