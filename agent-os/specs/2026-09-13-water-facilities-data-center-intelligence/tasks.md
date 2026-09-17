# Tasks — State water-facility and data-center intelligence (#112–#119)

Legend: `[x]` done · `[ ]` todo. Implement one roadmap item at a time. Write the
listed offline tests first, run only those tests, then implement. Network, live
EPA/state sources, and PostGIS are opt-in integration/smoke work and must not enter
the standard offline suite.

## Group 1 — Boundary and schema contract (#112) · offline + opt-in database

- [ ] 1.1 Add pure domain value objects and repository protocols under `src/` with
  no database-driver or GIS imports at module load.
- [ ] 1.2 Write `tests/test_water_facility_models.py` first: allowed enum values,
  immutable provenance, external-ID uniqueness rules, quantity/status separation,
  `water_claim` display eligibility, bitemporal validity/system times, and failure
  on invalid period or unit input.
- [ ] 1.3 Add reversible PostGIS migrations and documented bootstrap/rollback.
- [ ] 1.4 Add opt-in migration/constraint integration tests; confirm no PostgreSQL
  service is needed for the offline suite.

## Group 2 — National source snapshots and normalizers (#113) · offline + smoke

- [ ] 2.1 Write `tests/test_water_source_normalization.py` first using checked-in
  synthetic rows: FRS, SDWIS, NPDES, CWNS, NID, and USGS records normalize to the
  common contract while retaining source keys and raw values; DMR data remains a
  discharge fact and service-area records remain geographic context.
- [ ] 2.2 Implement source-specific `tools/` download/snapshot executors behind
  injected readers; archive URL, retrieval time, checksum, and parser version.
- [ ] 2.3 Implement idempotent normalization/import planning from a source snapshot.
- [ ] 2.4 Smoke one current source snapshot from each national family outside the
  offline suite; record source dates and coverage.

## Group 3 — State source registry and pilot adapters (#114) · offline + smoke

- [ ] 3.1 Write `tests/test_state_source_registry.py` first: valid adapter methods,
  required license/coverage/cadence, inactive/unverified source handling, and
  jurisdiction isolation.
- [ ] 3.2 Define the adapter protocol and mapping manifest format; implement
  fixture-backed adapters for API, bulk CSV, and ArcGIS pagination.
- [ ] 3.3 Select three pilots based on open withdrawal/right/reuse data and record
  the choice, source URLs, access constraints, point precision, and customer
  display/reuse rights. Start with Texas, then Virginia; do not select the third
  state until its source-rights audit passes.
- [ ] 3.4 Smoke each pilot adapter with a limited live pull; preserve its snapshot
  and report fields that cannot be normalized.

## Group 4 — Data-center candidates, evidence, and matching (#115) · offline

- [ ] 4.1 Write `tests/test_water_facility_matching.py` first: authority-ID match,
  high-confidence name/address/geography match, ambiguous review-queue result, and
  no merge for nearby but distinct facilities.
- [ ] 4.2 Write `tests/test_water_evidence.py` first: evidence-ranking order,
  candidate-to-confirmed transition, site-level evidence requirement, and no
  inferred consumption from NAICS, campus size, or WUE alone.
- [ ] 4.3 Implement candidate discovery and deterministic match scoring with full
  component scores and source links retained.
- [ ] 4.4 Implement water-source, measure-type, and quantity-status facts; require
  a source/evidence record for each non-`unavailable` claim.
- [ ] 4.5 Manually review a documented sample of every auto-link before promoting
  a pilot state.

## Group 5 — Analysis query layer and coverage readout (#116) · offline + opt-in

- [ ] 5.1 Write `tests/test_water_aggregation.py` first: no summing across
  measure types/statuses, correct period and geography filters, null quantity
  handling, and source-caveat propagation.
- [ ] 5.2 Implement parameterized state/county/HUC summaries and facility-detail
  provenance queries.
- [ ] 5.3 Add an opt-in PostGIS test that a service-area intersection returns only
  `within_service_area`, never a claimed customer/use relationship.
- [ ] 5.4 Publish a pilot coverage readout with current/unavailable/not-verified
  source status and match-review metrics.

## Group 6 — Verification and closeout (#117) · offline + opt-in

- [ ] 6.1 Run each focused offline test module and the full offline suite.
- [ ] 6.2 Run opt-in migrations, idempotent re-ingestion, spatial constraints, and
  three-pilot smoke checks against an isolated database.
- [ ] 6.3 Audit 50 auto-matches per pilot (or all if fewer), report precision and
  unmatched-permit rate, and adjust the documented threshold if needed.
- [ ] 6.4 Record an implementation report; tick roadmap items only when the epoch
  gate is met.

## Group 7 — Customer facility-request options (#118) · offline + view-layer

- [ ] 7.1 Write `tests/test_facility_request.py` first: default request has no
  facility overlay; valid selections serialize to an immutable manifest; invalid,
  unavailable, or restricted selections yield an explicit exclusion, not a claim.
- [ ] 7.2 Add an optional request/brief extension and resolver protocol that pins
  facility IDs plus database/source snapshot versions; preserve existing defaults.
- [ ] 7.3 Add image/report controls for class, named-facility search, and
  `visual_context` versus `evidence_backed_report`, with availability language.
- [ ] 7.4 Add a review gate that rejects restricted, ambiguous, or unreviewed
  results from public output and records a customer-safe exclusion reason.
- [ ] 7.5 Render approved selections as a post-base overlay/annotation with a
  manifest/provenance link; do not change `PIPELINE_STAGES` or default bytes.
- [ ] 7.6 Add Node-loadable UI helper tests and an opt-in browser smoke test for
  request → review → approved/excluded output; run the full offline suite and a
  byte-identical default-render regression before closeout.

## Group 8 — Data quality, caveat, and claim-display layer (#119) · offline + opt-in

- [ ] 8.1 Write `tests/test_water_claims.py` and `tests/test_data_alerts.py`
  first: one evidence source can support multiple claims; eligibility prevents an
  unreviewed claim from reaching a public result; valid/system times remain
  distinct; applicable jurisdiction/program alerts propagate to results.
- [ ] 8.2 Add claim extraction/review and `data_alert` domain models, repository
  protocol, reversible migration, and internal/public query views.
- [ ] 8.3 Enforce precise versus generalized display geometry at the renderer
  boundary; the public query must not return `internal_only` or `excluded` claims.
- [ ] 8.4 Import source-quality alerts for each national and pilot-state program;
  retain source URL, effective period, and operator interpretation.
- [ ] 8.5 Add opt-in PostGIS tests for generalized geometry and public-view row
  security; run a manual review of a precise, generalized, and excluded example.
