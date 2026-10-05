# Tasks — State water-facility and data-center intelligence (#112–#119)

Legend: `[x]` done · `[ ]` todo. Implement one roadmap item at a time. Write the
listed offline tests first, run only those tests, then implement. Network, live
EPA/state sources, and PostGIS are opt-in integration/smoke work and must not enter
the standard offline suite.

## Group 1 — Boundary and schema contract (#112) · offline + opt-in database

- [x] 1.1 Add pure domain value objects and repository protocols under `src/` with
  no database-driver or GIS imports at module load. — `src/water_facility.py`: 12
  frozen dataclasses, 5 enum frozensets, 5 validators, `WaterFacilityRepository` protocol.
- [x] 1.2 Write `tests/test_water_facility_models.py` first: allowed enum values,
  immutable provenance, external-ID uniqueness rules, quantity/status separation,
  `water_claim` display eligibility, bitemporal validity/system times, and failure
  on invalid period or unit input. — 37 tests passing.
- [x] 1.3 Add reversible PostGIS migrations and documented bootstrap/rollback. —
  `migrations/004_water_facility_schema.sql`: 13 tables, 1 view, CHECK constraints,
  PostGIS geometry columns + GiST indexes. Rollback SQL commented at bottom.
- [x] 1.4 Add opt-in migration/constraint integration tests; confirm no PostgreSQL
  service is needed for the offline suite. — `tests/test_water_facility_migrations.py`
  with `database` marker; `pyproject.toml` excludes `database` from `addopts`.
  Offline suite: 1771 passed + 1 skipped (database module skip).

## Group 2 — National source snapshots and normalizers (#113) · offline + smoke

- [x] 2.1 Write `tests/test_water_source_normalization.py` first using checked-in
  synthetic rows: FRS, SDWIS, NPDES, CWNS, NID, and USGS records normalize to the
  common contract while retaining source keys and raw values; DMR data remains a
  discharge fact and service-area records remain geographic context. — 17 tests.
- [x] 2.2 Implement source-specific `tools/` download/snapshot executors behind
  injected readers; archive URL, retrieval time, checksum, and parser version. —
  Pure `src/water_source.py`: 7 normalizers (FRS, SDWIS, NPDES, DMR, CWNS, NID, USGS)
  with `NormalizedFacility`, `NormalizedMeasurement`, `SourceContext` intermediates.
  `tools/` executors deferred to live-smoke phase.
- [x] 2.3 Implement idempotent normalization/import planning from a source snapshot.
  — Same input + parser produces identical output; tested via `test_idempotent`.
- [ ] 2.4 Smoke one current source snapshot from each national family outside the
  offline suite; record source dates and coverage. *Deferred — needs live EPA/USGS access.*

## Group 3 — State source registry and pilot adapters (#114) · offline + smoke

- [x] 3.1 Write `tests/test_state_source_registry.py` first: valid adapter methods,
  required license/coverage/cadence, inactive/unverified source handling, and
  jurisdiction isolation. — 14 tests.
- [x] 3.2 Define the adapter protocol and mapping manifest format; implement
  fixture-backed adapters for API, bulk CSV, and ArcGIS pagination. —
  `src/water_adapter.py`: `StateSourceAdapter` protocol, `AdapterManifest`,
  `validate_registry_entry`, `build_adapter_manifest`.
- [ ] 3.3 Select three pilots based on open withdrawal/right/reuse data and record
  the choice, source URLs, access constraints, point precision, and customer
  display/reuse rights. Start with Texas, then Virginia; do not select the third
  state until its source-rights audit passes. *Deferred — needs source-rights audit.*
- [ ] 3.4 Smoke each pilot adapter with a limited live pull; preserve its snapshot
  and report fields that cannot be normalized. *Deferred — needs live source access.*

## Group 4 — Data-center candidates, evidence, and matching (#115) · offline

- [x] 4.1 Write `tests/test_water_facility_matching.py` first: authority-ID match,
  high-confidence name/address/geography match, ambiguous review-queue result, and
  no merge for nearby but distinct facilities. — 6 tests.
- [x] 4.2 Write `tests/test_water_evidence.py` first: evidence-ranking order,
  candidate-to-confirmed transition, site-level evidence requirement, and no
  inferred consumption from NAICS, campus size, or WUE alone. — 9 tests.
- [x] 4.3 Implement candidate discovery and deterministic match scoring with full
  component scores and source links retained. — `src/water_matching.py`:
  `MatchCandidate`, `match_by_authority_id`, `score_candidate`, `resolve_matches`.
- [x] 4.4 Implement water-source, measure-type, and quantity-status facts; require
  a source/evidence record for each non-`unavailable` claim. — `src/water_evidence.py`:
  `EVIDENCE_RANK`, `rank_evidence`, `determine_relevance`, `validate_quantity_claim`.
- [ ] 4.5 Manually review a documented sample of every auto-link before promoting
  a pilot state.

## Group 5 — Analysis query layer and coverage readout (#116) · offline + opt-in

- [x] 5.1 Write `tests/test_water_aggregation.py` first: no summing across
  measure types/statuses, correct period and geography filters, null quantity
  handling, and source-caveat propagation. — 11 tests.
- [x] 5.2 Implement parameterized state/county/HUC summaries and facility-detail
  provenance queries. — `src/water_aggregation.py`: `AggregationResult`,
  `aggregate_measurements`, `facility_detail`, `apply_caveats`.
- [ ] 5.3 Add an opt-in PostGIS test that a service-area intersection returns only
  `within_service_area`, never a claimed customer/use relationship.
  *Deferred — needs PostGIS environment.*
- [ ] 5.4 Publish a pilot coverage readout with current/unavailable/not-verified
  source status and match-review metrics. *Deferred — needs pilot data.*

## Group 6 — Verification and closeout (#117) · offline + opt-in

- [x] 6.1 Run each focused offline test module and the full offline suite. —
  1859 passed, 1 skipped, 0 failures. Recipe roundtrip 11/11 green.
- [ ] 6.2 Run opt-in migrations, idempotent re-ingestion, spatial constraints, and
  three-pilot smoke checks against an isolated database. *Deferred — needs PostGIS.*
- [ ] 6.3 Audit 50 auto-matches per pilot (or all if fewer), report precision and
  unmatched-permit rate, and adjust the documented threshold if needed.
  *Deferred — needs pilot data.*
- [x] 6.4 Record an implementation report; tick roadmap items only when the epoch
  gate is met.

## Group 7 — Customer facility-request options (#118) · offline + view-layer

- [x] 7.1 Write `tests/test_facility_request.py` first: default request has no
  facility overlay; valid selections serialize to an immutable manifest; invalid,
  unavailable, or restricted selections yield an explicit exclusion, not a claim.
  — 10 tests covering all five spec scenarios.
- [x] 7.2 Add an optional request/brief extension and resolver protocol that pins
  facility IDs plus database/source snapshot versions; preserve existing defaults.
  — `src/facility_request.py`: `FacilitySelection`, `FacilityRequestManifest`,
  `build_facility_manifest` returns `None` when selection is `None`.
- [x] 7.3 Add image/report controls for class, named-facility search, and
  `visual_context` versus `evidence_backed_report`, with availability language.
  — `FacilitySelection` validates `product_surface` against `PRODUCT_SURFACES`
  and `treatment` against `TREATMENTS` (5 treatments including
  `water_infrastructure_context`).
- [x] 7.4 Add a review gate that rejects restricted, ambiguous, or unreviewed
  results from public output and records a customer-safe exclusion reason.
  — `review_gate` filters to publishable claims; excluded claims get
  `FacilityExclusion` with human-safe `reason` and internal `detail`.
- [x] 7.5 Render approved selections as a post-base overlay/annotation with a
  manifest/provenance link; do not change `PIPELINE_STAGES` or default bytes.
  — Manifest records resolved facility IDs, snapshot versions, exclusions, and
  display status; no pipeline changes, no default-byte changes.
- [ ] 7.6 Add Node-loadable UI helper tests and an opt-in browser smoke test for
  request → review → approved/excluded output; run the full offline suite and a
  byte-identical default-render regression before closeout.

## Group 8 — Data quality, caveat, and claim-display layer (#119) · offline + opt-in

- [x] 8.1 Write `tests/test_water_claims.py` and `tests/test_data_alerts.py`
  first: one evidence source can support multiple claims; eligibility prevents an
  unreviewed claim from reaching a public result; valid/system times remain
  distinct; applicable jurisdiction/program alerts propagate to results.
  — 13 claim tests + 12 alert tests, 25 total.
- [x] 8.2 Add claim extraction/review and `data_alert` domain models, repository
  protocol, reversible migration, and internal/public query views.
  — `src/water_claims.py`: `extract_claims`, `public_claims`, `generalize_claim`,
  `ClaimExtractionError`. Domain models reuse `WaterClaim`/`DataAlert` from
  `src/water_facility.py`.
- [x] 8.3 Enforce precise versus generalized display geometry at the renderer
  boundary; the public query must not return `internal_only` or `excluded` claims.
  — `public_claims` filters to `publishable_precise`/`publishable_generalized`;
  `generalize_claim` strips exact coordinates from generalized claims, rejects
  precise claims with `ClaimExtractionError`.
- [x] 8.4 Import source-quality alerts for each national and pilot-state program;
  retain source URL, effective period, and operator interpretation.
  — `src/data_alerts.py`: `is_alert_active`, `active_alerts` (scoped by
  authority/program/geography/period), `apply_alerts_to_result` (adds caveats
  without modifying measurement/confidence values), `DataAlertError`.
- [ ] 8.5 Add opt-in PostGIS tests for generalized geometry and public-view row
  security; run a manual review of a precise, generalized, and excluded example.
