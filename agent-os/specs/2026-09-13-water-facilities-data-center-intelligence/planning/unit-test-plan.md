# Offline unit-test plan — water-facility and data-center intelligence

These tests are deliberately specified before implementation. They use small
synthetic fixtures only; no network, GDAL, live EPA/state data, or PostgreSQL is
permitted in the normal suite.

| Test module | Cases required before implementation |
| --- | --- |
| `tests/test_water_facility_models.py` | Reject invalid facility/relevance/quantity/display enums; preserve immutable source checksum and locator; reject a missing source for a quantified claim; reject inverted measurement periods; preserve source unit plus canonical converted value; distinguish valid time from system/retrieval time. |
| `tests/test_water_source_normalization.py` | Normalize one fixture each for FRS, SDWIS, ICIS-NPDES, DMR, CWNS/service area, NID, and USGS; retain every source key; NPDES/DMR discharge remains `discharged`, never `withdrawal`; service-area and USGS context cannot create a facility measurement; same fixture and parser version gives identical result. |
| `tests/test_state_source_registry.py` | Accept only the five declared access methods; require jurisdiction/program/URL/coverage/license/cadence; report an unverified or inactive source instead of silently excluding it; keep identical permit IDs in different authorities distinct. |
| `tests/test_water_facility_matching.py` | Exact authority ID wins; one high-score candidate links; equal close candidates enter review; similarly named neighbors do not merge; input ordering does not change a result; source names/addresses are retained. |
| `tests/test_water_evidence.py` | Metered evidence outranks permits and agreements; a generic operator claim cannot confirm a site; NAICS 518210 creates only `candidate`; authorized capacity cannot be reported as measured withdrawal; unsupported WUE cannot create water volume. |
| `tests/test_water_aggregation.py` | Sum only the requested measure type and quantity status; do not zero-fill absent quantities; retain `unavailable` count; filter period overlap correctly; group state/county/HUC results correctly; return source-date/caveat metadata. |
| `tests/test_facility_request.py` | Default image/report request has no facility component; a valid optional selection serializes a snapshot-pinned immutable manifest; unavailable/ambiguous/restricted results produce a customer-safe exclusion; candidate data centers retain their candidate label; a facility selection cannot change the base render recipe. |
| `tests/test_water_claims.py` | One document may support multiple reviewed claims and one claim may cite multiple documents; only reviewed `publishable_precise`/`publishable_generalized` claims enter the public view; generalized eligibility omits exact coordinates; changing a source retrieval time does not rewrite a claim's valid time. |
| `tests/test_data_alerts.py` | An alert applies only to its authority/program/geography/effective period; active alerts propagate to result caveats; expired/superseded alerts remain historically auditable but do not appear as active; no alert may silently change a measurement or confidence value. |

Opt-in integration tests, excluded from the normal suite, must cover migration
up/down, database constraints, spatial service-area intersection semantics, and
idempotent source-snapshot re-ingestion. A live-source smoke run verifies each
adapter separately and records its retrieved snapshot, rather than becoming a
brittle unit test.
