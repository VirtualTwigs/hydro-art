# Specification: State water-facility and data-center intelligence (Epoch 27)

## Goal

Create a standalone, internal PostgreSQL/PostGIS database for the 50 states and
District of Columbia. It must answer where regulated water facilities and
data-center candidates are, what public evidence connects a site to water, and
which quantities are measured, reported, or merely authorized. It must preserve
raw-source provenance and never substitute an estimate or a geographic overlap
for documented facility water use.

This work implements roadmap #112–#119 and follows
`docs/water-facilities-database.md`. It is separate from the operations ledger
(#99–#106), has no customer-facing authorization, and does not change the 2D
render pipeline or require a database for an offline render.

## User stories

- As an analyst, I can list the facilities in a state with a stable identity,
  source links, refresh dates, and confidence labels.
- As an analyst, I can distinguish a data-center candidate from a site with a
  permit, utility commitment, or measured water use.
- As a reviewer, I can inspect the exact source snapshot and input row behind a
  facility, match, permit, or quantity.
- As an operator, I can see which jurisdictions and source classes are current,
  available, or not yet verified rather than receiving fabricated coverage.
- As a customer, I can request selected facility classes or named facilities as
  context in an image or evidence-backed report, and receive an honest indication
  when the requested information cannot be published.

## Scope

### National baseline (#113)

Load, archive, normalize, and link these public source families for all states/DC:

- EPA FRS facility identity and program identifiers;
- EPA SDWIS public-water systems;
- EPA ICIS-NPDES facilities, permits, and discharge points;
- EPA CWNS public wastewater facilities and sewersheds;
- USACE National Inventory of Dams; and
- USGS county/state/HUC water-use context.

National context data is never treated as site-level consumption. NPDES discharge
data is never treated as intake, withdrawal, or consumption absent a separate
source that says so.

### State adapters (#114)

Each state/DC source is described before collection in `state_source_registry`:
agency, program, URL, access method, data format, coverage, update cadence,
license, field mapping, geometry quality, publication lag, and verification time.
Adapters support `api`, `bulk_file`, `arcgis_service`, `html_download`, and
`manual_record_request`. The first implementation is exactly three pilot states;
the pilot choice must be recorded with source-access rationale.

### Data centers (#115)

Candidate discovery may use NAICS 518210, operator site listings, local planning
and permitting records, and open map data. It does not establish water use. A
water-relevance claim requires facility-specific evidence, ranked:

1. metered annual/monthly potable or reclaimed-water volume;
2. withdrawal/right/appropriation permit naming the site or operator;
3. wastewater, cooling, pretreatment, or environmental permit with water detail;
4. municipal development/utility capacity agreement; or
5. explicit site-level operator disclosure.

## Data contract (#112)

Use UUID primary keys and external identifiers as unique alternate keys. Migrations
are small, append-only, and reversible. Store raw downloaded files outside the
database; database records contain immutable content checksum, retrieval metadata,
and a durable source-file key. No raw file is stored as a BLOB.

| Entity | Grain / invariants |
| --- | --- |
| `facility` | One real-world site; canonical name, class, jurisdiction, status, and reviewable match confidence. |
| `facility_identifier` | One authority + identifier; unique per authority, never replaces the facility UUID. |
| `facility_geometry` | One versioned point/polygon with CRS, method, accuracy, source, and validity period. |
| `permit` | One source permit/application; authority + permit identifier unique; status and dates retained. |
| `water_measurement` | One value for one period and measure type; `NUMERIC` volume plus source unit, canonical unit, conversion method, and confidence. |
| `facility_evidence` | One source document/record; URL/file key, row/page locator, publisher, dates, review status. |
| `water_claim` | One reviewed assertion extracted from evidence; subject, predicate, value/unit, measure/status, validity, confidence, display eligibility, reviewer decision. |
| `facility_relationship` | Directed, evidence-backed relationship such as `served_by` or `discharges_to`; no inferred customer relationship. |
| `service_area` | Versioned provider area geometry with `published` or `modeled` method. |
| `source_snapshot` / `source_record` | Immutable retrieval and source-row provenance, checksum, parser version, and raw payload. |
| `state_source_registry` | One versioned source configuration and availability status for a jurisdiction/program. |

Allowed water measure types are `withdrawal`, `delivered`, `consumed`,
`discharged`, and `authorized_capacity`. Quantity status is `measured`,
`reported`, `authorized`, or `unavailable`. No aggregation may combine different
measure types or quantity statuses without an explicit analyst-selected rule.

Every mutable entity is bitemporal: `valid_time` describes when the underlying
fact applies and `system_time` records when the system retrieved or revised it.
`water_claim` is the only public-facing assertion layer; source documents may
support multiple claims and a claim may cite multiple source records. A claim's
customer display eligibility is one of `internal_only`, `review_required`,
`publishable_precise`, `publishable_generalized`, or `excluded`.

## Entity resolution and confidence

1. Prefer authority IDs (FRS, PWS, NPDES, state permit) for joins.
2. Otherwise score normalized name/owner, address, jurisdiction, and distance.
3. Automatically link only above a documented high-confidence threshold.
4. Route every ambiguous link to a review queue retaining both source records,
   component scores, decision, reviewer, and decision time.
5. Retain all source names and addresses; a canonical field does not overwrite
   source content.

Public results must show `identity_confidence`, `water_relevance`,
`quantity_status`, and `last_source_check`.

## Query layer (#116)

Provide versioned SQL views or parameterized repository queries for state, county,
and HUC results. Each quantity result groups measured, reported, and authorized
values separately and includes a count of unquantified facilities. Results include
source date, evidence links, and coverage caveats. Spatial service-area matching
returns a `within_service_area` relationship only; it cannot assert the facility is
a customer or quantify its use.

## Data quality, caveats, and display (#119)

Ingest source and jurisdiction alerts into a versioned `data_alert` model with
affected authority/program, geography, period, severity, source link, and display
guidance. Query results inherit applicable alerts and surface claim-level source
date, precision, confidence, quantity status, and caveat. A precise internal point
may be shown publicly only when its claim is `publishable_precise`; generalized
claims are rendered at the approved watershed, grid, or area level. The public
renderer reads only the approved claim view and cannot bypass these controls.

## Customer facility requests (#118)

Facility information is an explicit, optional request component for image and
report products. It is not enabled by default, and an identical request without a
facility option produces the existing image/report behavior.

The request form must collect product surface (`image` or `report`), the existing
geographic scope, requested facility classes, optional named facility/operator
search terms, and intended treatment: `visual_context` (overlay/legend only) or
`evidence_backed_report` (annotated findings with provenance). It must make clear
that availability and public evidence vary by jurisdiction.

Submission creates an immutable, versioned facility-request manifest linked to the
existing request/brief or report-run provenance. It records selection filters,
database/source snapshot versions, resolved facility IDs, exclusions, reviewer
decision, and public-display status.

1. Images may show only reviewed, publishable locations with neutral class labels;
   they may not imply consumption, permit status, or ownership beyond evidence.
2. Reports may make facility water claims only with evidence, measure type,
   quantity status, source date, and provenance.
3. Ambiguous, unverified, non-public, or restricted records are excluded from
   public output unless a reviewer approves a non-assertive, rights-compliant use.
   The customer receives a safe explanation without restricted details.
4. Data-center candidates retain their candidate label and cannot be presented as
   confirmed water users.
5. Facility selections are post-base overlays/annotations. They do not change
   `PIPELINE_STAGES`, base render geometry, or default image bytes.

The customer interface offers three distinct products rather than one generic
toggle: `water_infrastructure_context` (neutral display),
`named_facility_research_note` (reviewed source appendix), and
`water_evidence_overlay` (reviewed claims only). Each has its own eligibility and
review rule; the image/report request records which product was selected.

## Non-goals

- A claim that every data center is water intensive or uses potable water.
- Estimated site consumption from IT load, square footage, MW capacity, or WUE
  without compatible site-level inputs and disclosed boundaries.
- A complete national withdrawal-permit file; state coverage is explicitly staged.
- Browser scraping where a documented bulk download/API or a record request is
  more reliable.
- Automatically placing non-public, ambiguous, or unreviewed facilities in a
  customer asset.
- Database drivers, network calls, PostGIS, or heavy GIS imports at `src/` module
  load time.

## Testing and verification (#117)

All normal unit tests are pure and offline: fakes provide downloaded rows,
geocoding/matching candidates, file metadata, and repositories. PostGIS migration,
constraint, spatial, and idempotent-ingestion tests are opt-in integration tests.
The test inventory in `planning/unit-test-plan.md` is a prerequisite to
implementation; no implementation task is complete until its listed focused tests
pass.
