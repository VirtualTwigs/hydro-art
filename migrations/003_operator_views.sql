-- Migration 003: Operator views for Postico 2
-- Target: PostgreSQL >= 15
--
-- Eight read-only views for the ops workspace. All exclude customer
-- email from output columns for privacy.
--
-- Intended consumer: hydro_ops_readonly role via Postico 2.

-- 1. Active work: requests/orders not yet fulfilled, with age
CREATE OR REPLACE VIEW ops_active_work AS
SELECT
    r.request_id,
    r.product,
    r.status,
    o.order_id,
    o.style,
    p.region,
    p.county,
    p.display_name,
    r.created_at,
    r.updated_at,
    now() - r.created_at AS age
FROM requests r
LEFT JOIN orders o ON o.request_id = r.request_id
LEFT JOIN places p ON p.place_id = COALESCE(o.place_id, r.place_id)
WHERE r.status NOT IN ('fulfilled', 'paid');

-- 2. Completed work: fulfilled orders with asset counts
CREATE OR REPLACE VIEW ops_completed_work AS
SELECT
    r.request_id,
    r.product,
    o.order_id,
    o.style,
    p.region,
    p.county,
    p.display_name,
    r.updated_at AS fulfilled_at,
    (SELECT count(*) FROM assets a WHERE a.order_id = o.order_id) AS asset_count,
    (SELECT count(*) FROM deliveries d WHERE d.order_id = o.order_id) AS delivery_count
FROM requests r
JOIN orders o ON o.request_id = r.request_id
LEFT JOIN places p ON p.place_id = COALESCE(o.place_id, r.place_id)
WHERE r.status IN ('fulfilled', 'paid');

-- 3. Delivery expiry: deliveries expiring in 30 days or already expired
CREATE OR REPLACE VIEW ops_delivery_expiry AS
SELECT
    d.delivery_id,
    d.order_id,
    d.delivered_at,
    d.access_expires_at,
    d.access_revoked_at,
    d.reason,
    d.fee_waived,
    CASE
        WHEN d.access_revoked_at IS NOT NULL THEN 'revoked'
        WHEN d.access_expires_at <= now() THEN 'expired'
        ELSE 'expiring_soon'
    END AS expiry_status,
    d.access_expires_at - now() AS time_remaining
FROM deliveries d
WHERE d.access_expires_at <= now() + interval '30 days'
   OR d.access_revoked_at IS NOT NULL;

-- 4. Rights gaps: assets missing rights clearance or attribution
CREATE OR REPLACE VIEW ops_rights_gaps AS
SELECT
    a.asset_id,
    a.order_id,
    a.role,
    a.visibility,
    a.rights_status,
    a.source_attribution,
    a.media_type,
    a.created_at
FROM assets a
WHERE a.rights_status != 'cleared'
   OR a.source_attribution IS NULL;

-- 5. Render failures: failed render jobs
CREATE OR REPLACE VIEW ops_render_failures AS
SELECT
    rj.job_id,
    rj.order_id,
    rj.status,
    rj.error_message,
    rj.started_at,
    rj.completed_at,
    rj.recipe_digest,
    rj.code_revision,
    rj.created_at
FROM render_jobs rj
WHERE rj.status = 'failed';

-- 6. Library candidates: internal assets ready for public approval
CREATE OR REPLACE VIEW ops_library_candidates AS
SELECT
    a.asset_id,
    a.order_id,
    a.role,
    a.storage_key,
    a.checksum_sha256,
    a.media_type,
    a.visibility,
    a.rights_status,
    a.source_attribution,
    a.created_at
FROM assets a
WHERE a.visibility = 'internal'
  AND a.rights_status = 'cleared'
  AND a.source_attribution IS NOT NULL
  AND a.checksum_sha256 IS NOT NULL
  AND a.deleted_at IS NULL;

-- 7. Analysis evidence: analysis runs with validation status
CREATE OR REPLACE VIEW ops_analysis_evidence AS
SELECT
    ar.run_id,
    ar.place_id,
    p.region,
    p.county,
    p.display_name,
    ar.metric_version,
    ar.validation_status,
    ar.start_year,
    ar.end_year,
    ar.reviewer,
    ar.created_at,
    (SELECT count(*) FROM analysis_metrics am WHERE am.run_id = ar.run_id) AS metric_count
FROM analysis_runs ar
LEFT JOIN places p ON p.place_id = ar.place_id;

-- 8. Orphans: assets without render job or order link
CREATE OR REPLACE VIEW ops_orphans AS
SELECT
    a.asset_id,
    a.order_id,
    a.render_job_id,
    a.role,
    a.storage_key,
    a.checksum_sha256,
    a.media_type,
    a.created_at
FROM assets a
WHERE a.render_job_id IS NULL
   OR a.order_id IS NULL;
