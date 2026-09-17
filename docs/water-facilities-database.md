# State Water-Facilities and Data-Center Database

## Decision and scope

Build a **U.S. 50-state plus District of Columbia** PostgreSQL/PostGIS database
of facilities that either provide, treat, discharge, withdraw, reuse, or are
likely to consume water at material scale. The first release should cover:

- public drinking-water systems and their service areas;
- publicly owned wastewater treatment works, sewersheds, and NPDES outfalls;
- dams and reservoirs that meet the National Inventory of Dams inclusion rules;
- industrial and other permitted discharge facilities;
- water-withdrawal, water-right, reuse, and reclaimed-water permits when a state
  publishes them; and
- data-center sites, their water-related permits or utility arrangements, and
  measured/reported water use when public.

Do **not** label every data center as a water user, or infer its water use from
its size. A data-center address is a candidate site; a permit, utility record,
environmental filing, or owner disclosure is needed to establish a water fact.
This distinction is essential because cooling technology and water source vary by
site. The Department of Energy notes that cooling-tower water use depends on IT
heat load and cooling-system efficiency, and defines water-use effectiveness
(WUE) as annual site water divided by IT energy.

## What can be collected nationally

Use these sources to create an auditable baseline for every state. Save every
download unchanged, including its URL, retrieval time, checksum, and source
version; derived facility rows must retain the source-row identifier.

| Need | Primary source | Cadence / useful fields | Important limit |
| --- | --- | --- | --- |
| Regulated facility identity and cross-program IDs | [EPA Facility Registry Service (FRS)](https://www.epa.gov/frs/epa-frs-facilities-state-single-file-csv-download) | Monthly state CSV; FRS ID, name, address, coordinates, NAICS/SIC, program IDs | It is a registry, not proof of withdrawal or consumption. |
| Drinking-water systems | [EPA SDWIS / ECHO download](https://echo.epa.gov/tools/data-downloads/sdwa-download-summary) | Quarterly; PWS ID, system type, population served, violations, enforcement, service-area linkage | PWSs are suppliers, not each customer facility. |
| Wastewater facilities and permitted outfalls | [EPA ICIS-NPDES discharge points](https://echo.epa.gov/tools/data-downloads/icis-npdes-discharge-points-download-summary) and [ECHO downloads](https://echo.epa.gov/tools/data-downloads) | Facility/permit identity, outfall coordinates, compliance, monitored discharge records | A discharge permit does not quantify intake water use. |
| Dams and reservoirs | [USACE National Inventory of Dams](https://nid.sec.usace.army.mil/nid/) | API and GIS service; dam ID, owner, location, hazard, purpose and structural fields | An inventory of qualifying dams, not a complete inventory of every small structure or live release data. |
| POTW capacity, treatment, reuse, and served population | [2022 Clean Watersheds Needs Survey](https://www.epa.gov/cwns/clean-watersheds-needs-survey-cwns-2022-report-and-data) | State or national CSV; flow, treatment level, discharge type, needs and projects | A dated planning/survey snapshot, not live operations. |
| Wastewater service geography | [EPA sewersheds](https://www.epa.gov/cwns/sewersheds) | POTW endpoint and service-area geometry | Modeled or compiled boundaries; preserve the boundary method. |
| State/county/HUC water-use context | [USGS Water Use Data](https://www.usgs.gov/mission-areas/water-resources/science/accessing-water-use-data) | County, state, HUC, withdrawal vs. consumptive use; use as a context layer | Not facility-level and not data-center-specific. |

The FRS download is the identity spine: it contains state-level files with
facility name, address, geography, program associations, and SIC/NAICS. Link
NPDES and SDWIS records to it when possible, but retain original identifiers;
names and addresses change and cross-system matches are not always one-to-one.

## How to collect water information for each state

There is no authoritative national file of facility-level withdrawal permits.
Water allocation is generally administered by state agencies, so the database
needs one configured state adapter per jurisdiction rather than a fragile,
one-off national scrape.

For each state plus DC, record these fields in `state_source_registry` before
ingestion:

```text
jurisdiction_code, agency_name, program_name, source_url, access_method,
format, update_frequency, coverage, license, permit_identifier_field,
facility_identifier_field, geometry_quality, publication_lag, retrieval_notes,
active, last_verified_at
```

The adapter should try these sources in this order:

1. The state water-rights or withdrawal-permit register, including surface water,
   groundwater, temporary/emergency permits, and transfers.
2. State NPDES/industrial pretreatment, reclaimed-water, and cooling-tower or
   water-quality permit portals. Prefer the state record over a duplicate federal
   record when it has the permit application, authorized quantity, source, or
   receiving-water detail.
3. State drinking-water and wastewater GIS portals, utility service-area files,
   and annual utility reports.
4. State environmental-review, air-permit, and water-supply applications for
   planned large loads, including data centers.
5. Local planning commission agendas, site plans, building permits, development
   agreements, utility board packets, and water/sewer availability letters.

Store an access method (`api`, `bulk_file`, `arcgis_service`, `html_download`,
`manual_record_request`) rather than pretending all states support the same
pipeline. A source is only "production-ready" after a sample extract can be
re-run, has a stable key or documented deduplication rule, and its license and
refresh behavior are recorded.

## Data-center acquisition and verification

Use a two-pass approach.

**Pass 1 — discover candidates.** Start with FRS records coded NAICS 518210
(Computing Infrastructure Providers, Data Processing, Web Hosting, and Related
Services), then supplement from operator site directories, local development
records, and open map points. Treat every result as `candidate` until reviewed;
NAICS can be missing, stale, or assigned at a parent-company level.

**Pass 2 — prove water relevance.** Match candidate sites against the state
adapter records and collect the supporting document. Accept any of the following
as evidence, ranked from strongest to weakest:

1. metered annual/monthly water or reclaimed-water volume in a filing or utility
   report;
2. a withdrawal/right/appropriation permit naming the site or operator;
3. a wastewater, cooling-tower, industrial pretreatment, or environmental permit
   that specifies source, discharge, or authorized flow;
4. a municipal development agreement or utility capacity commitment; or
5. an operator disclosure that is explicitly site-level.

Keep water source (`potable_utility`, `reclaimed`, `surface`, `groundwater`,
`onsite_reuse`, `unknown`) and measure type (`withdrawal`, `delivered`,
`consumed`, `discharged`, `authorized_capacity`) separate. Never combine them in
one "water use" column. Store WUE only with the reporting period, numerator and
denominator boundary, and an evidence link; it cannot be converted reliably into
total water use without the corresponding IT-energy value.

## Recommended relational model

Use PostGIS for facility and service-area geometry. This is a data-domain schema,
separate from Hydro-Art's operations ledger: it may be imported from a standalone
database or a versioned analytical warehouse and must not make the rendering
pipeline depend on a live database.

```text
source_snapshot ─< source_record ─< facility_evidence >─ facility
                                           │                 │
state_source_registry ─────────────────────┘                 ├─< facility_identifier
                                                              ├─< facility_geometry
                                                              ├─< permit
                                                              ├─< water_measurement
                                                              ├─< facility_relationship
                                                              └─< service_area
```

Minimum table responsibilities:

| Table | Grain | Required contents |
| --- | --- | --- |
| `facility` | One real-world site | UUID, canonical name, facility class, state/county/FIPS, status, canonical point, match confidence |
| `facility_identifier` | One external identifier | Facility UUID, authority (`FRS`, `SDWIS`, `NPDES`, state), identifier, validity dates, uniqueness by authority + identifier |
| `permit` | One issued/application record | Authority, permit ID, kind, status, facility UUID, issue/expiry dates, source document |
| `water_measurement` | One measured/authorized value and period | Facility/permit UUID, measure type, volume, unit, start/end date, source type, water source, confidence |
| `facility_evidence` | One claim/document | Claim type, URL/file key, page/row locator, publisher, published/retrieved times, review status |
| `service_area` | One geometry/version | Provider facility UUID, area type, geometry, method (`published`/`modeled`), vintage, source |
| `facility_relationship` | One directed relationship | e.g. `served_by`, `discharges_to`, `uses_reclaimed_water_from`, `parent_company_of`; confidence and evidence |
| `source_snapshot` / `source_record` | One retrieval / source row | Immutable provenance, raw row payload, checksum, parser version, source key |

Use `NUMERIC` plus an explicit unit (prefer canonical `m3/day` only for derived
analysis) instead of floating-point volume. A record with a permitted maximum is
not an observation: set `measure_type = authorized_capacity`, not `withdrawal`.

## Entity resolution rules

1. Use authority IDs first: FRS ID, PWS ID, NPDES ID, and the state permit ID are
   durable joins but remain identifiers, not the facility primary key.
2. Otherwise match within one state on normalized owner/name, address, and a
   small geographic tolerance. Preserve both source names and never overwrite
   them with the canonical name.
3. Auto-merge only high-confidence matches. Put ambiguous matches in a review
   queue with both source records, distance, name score, and reviewer decision.
4. Model a campus as a parent facility with child buildings/sites only when the
   evidence supports that relationship. Do not merge neighboring utility and
   data-center points solely because they share a parcel.

## First release plan

1. Load FRS, SDWIS, ICIS-NPDES, NID, CWNS, sewersheds, and USGS contextual data
   for all states/DC. Publish a completeness report by state and source date.
2. Implement and validate adapters for three pilot states selected for data-center
   activity and open permit data. Start with the jurisdiction's documented bulk
   export/API rather than browser automation.
3. Add data-center candidates, conduct evidence-based matching, and manually
   review every claimed water connection or water-use measurement in the pilots.
4. Measure precision: sample 50 auto-matches per state, track false merges and
   unmatched permits, then adjust matching thresholds before scaling.
5. Add the remaining state adapters in batches, retaining a visible "not
   available / not yet verified" status instead of filling gaps with estimates.

## Quality gates and user-facing labels

Every facility result should expose the following labels:

```text
identity_confidence: high | medium | low
water_relevance: confirmed | permitted_or_committed | candidate | unknown
quantity_status: measured | reported | authorized | unavailable
last_source_check: ISO 8601 timestamp
```

This lets analysis answer two different questions honestly: "Where are likely
water-intensive sites?" and "Which sites have publicly evidenced water volumes?"
The second will initially be much smaller, especially for data centers.

## Analysis enabled after the baseline exists

- Count confirmed/candidate data centers by state, water source, and watershed.
- Sum measured, reported, and authorized quantities **separately** by state,
  county, HUC, utility, and reporting year.
- Identify data centers inside a public-water-system or POTW service area, while
  labelling this as a service-area relationship rather than proof of customer use.
- Compare permitted/observed volumes with USGS county/HUC context without
  attributing the aggregate USGS value to any individual facility.
- Flag locations where a proposed or permitted data center coincides with a
  constrained supply, drought indicator, or wastewater-reuse opportunity, once
  those contextual datasets and their vintages are added.
