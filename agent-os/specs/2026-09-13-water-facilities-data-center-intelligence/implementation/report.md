# Implementation Report — Water-Facility and Data-Center Intelligence (Epoch 27, #112-#119)

**Completed:** 2026-09-30 (offline implementation)
**Suite at close:** 1859 passed, 1 skipped (database marker), 0 failures
**Recipe roundtrip:** 11/11 green

## Summary

Built the pure, offline domain layer for a standalone water-facility and
data-center intelligence subsystem. Eight groups spanning schema, normalization,
adapters, matching, evidence, aggregation, customer requests, and data quality —
all implemented TDD-first with 125 new offline tests across 10 test modules.

This is **not** wired into `PIPELINE_STAGES` and does not affect default rendered
output. The PostGIS database, live source acquisition, and pilot-state smoke
tests are deferred to an environment with PostgreSQL and network access.

## Delivered artifacts

### Group 1 — Schema contract (#112)

- **`src/water_facility.py`** — 12 frozen dataclasses (`Facility`,
  `FacilityIdentifier`, `FacilityGeometry`, `WaterMeasurement`,
  `FacilityEvidence`, `WaterClaim`, `FacilityRelationship`, `ServiceArea`,
  `SourceSnapshot`, `SourceRecord`, `StateSourceEntry`, `DataAlert`), 5 enum
  frozensets, 5 validators, `WaterFacilityRepository` protocol. 37 tests.
- **`migrations/004_water_facility_schema.sql`** — 13 tables, 1 public view,
  CHECK constraints, PostGIS geometry + GiST indexes, documented rollback.
- **`tests/test_water_facility_migrations.py`** — opt-in `database` marker,
  4 integration tests (table creation, view, constraint rejection, uniqueness).
- **`pyproject.toml`** — `database` marker added to exclusion filter.

### Group 2 — National source normalizers (#113)

- **`src/water_source.py`** — 7 normalizers (FRS, SDWIS, NPDES, DMR, CWNS, NID,
  USGS) producing `NormalizedFacility`, `NormalizedMeasurement`, or
  `SourceContext`. DMR is hardcoded to `measure_type="discharged"` (never
  `withdrawal`). USGS returns `SourceContext` (never a facility measurement).
  17 tests.

### Group 3 — State source registry and adapters (#114)

- **`src/water_adapter.py`** — `StateSourceAdapter` protocol,
  `AdapterManifest`, `validate_registry_entry`, `build_adapter_manifest`.
  14 tests.

### Group 4 — Matching and evidence (#115)

- **`src/water_matching.py`** — `MatchCandidate`, `match_by_authority_id`,
  `score_candidate` (composite: name similarity, jurisdiction, haversine
  proximity), `resolve_matches` (threshold-based with ambiguity demotion).
  6 tests.
- **`src/water_evidence.py`** — `EVIDENCE_RANK` (metered > permit > agreement >
  disclosure > NAICS), `rank_evidence`, `determine_relevance`,
  `validate_quantity_claim` (rejects authorized-as-measured, WUE-only volume,
  NAICS-only confirmed). 9 tests.

### Group 5 — Aggregation (#116)

- **`src/water_aggregation.py`** — `AggregationResult`, `aggregate_measurements`
  (rejects cross-type/status aggregation), `facility_detail`, `apply_caveats`.
  11 tests.

### Group 7 — Customer facility requests (#118)

- **`src/facility_request.py`** — `FacilitySelection` (validates product surface
  + 5 treatments), `FacilityRequestManifest` (snapshot-pinned),
  `build_facility_manifest` (returns `None` for no-facility default),
  `review_gate` (approved vs excluded with customer-safe reasons),
  `FacilityExclusion`. 10 tests.

### Group 8 — Data quality and claims (#119)

- **`src/water_claims.py`** — `extract_claims` (evidence → review_required
  claims), `public_claims` (publishable only), `generalize_claim` (strips
  exact coords), `ClaimExtractionError`. 13 tests.
- **`src/data_alerts.py`** — `is_alert_active`, `active_alerts` (scoped
  filtering), `apply_alerts_to_result` (caveats without modifying values),
  `DataAlertError`. 12 tests.

## Invariants preserved

- **Offline suite unchanged.** `pytest -q` runs all 1859 tests; database tests
  excluded via `database` marker. No new GDAL/network/GIS imports at `src/`
  module load.
- **`PIPELINE_STAGES` untouched.** No pipeline change of any kind.
- **2D default output byte-identical.** No render-path code modified.
- **`src/` never imports `tools/` or `web/`.** All modules import only stdlib +
  other `src/` modules.

## Deferred items (need external environment)

- **2.4** Live EPA/USGS source snapshots — needs network access
- **3.3-3.4** Pilot state selection and live adapter pulls — needs source-rights audit
- **4.5** Manual auto-match audit — needs pilot data
- **5.3** PostGIS service-area intersection test — needs PostgreSQL
- **5.4** Pilot coverage readout — needs pilot data
- **6.2** Opt-in migration + re-ingestion smoke — needs PostgreSQL
- **6.3** Match precision audit — needs pilot data
- **7.6** Browser smoke test — needs running server + Chrome extension
- **8.5** PostGIS generalized-geometry tests — needs PostgreSQL

## New module inventory

| Module | Category | Tests |
|--------|----------|-------|
| `src/water_facility.py` | Domain models | 37 |
| `src/water_source.py` | Source normalizers | 17 |
| `src/water_adapter.py` | Adapter protocol | 14 |
| `src/water_matching.py` | Entity resolution | 6 |
| `src/water_evidence.py` | Evidence ranking | 9 |
| `src/water_aggregation.py` | Query layer | 11 |
| `src/facility_request.py` | Customer requests | 10 |
| `src/water_claims.py` | Claim extraction | 13 |
| `src/data_alerts.py` | Data quality | 12 |
| **Total** | | **125+4 opt-in** |
