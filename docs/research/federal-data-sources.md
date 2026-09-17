# Federal Bulk Data Sources for US Water Facilities

Comprehensive catalog of every major federal bulk download source for water facility data.
Compiled 2026-09-15 for hydro-art facility intelligence layer.

---

## 1. EPA Facility Registry Service (FRS)

The single federal master list linking facility records across all EPA programs.

### State Single-File CSV Download

- **URL:** <https://www.epa.gov/frs/epa-frs-facilities-state-single-file-csv-download>
- **Format:** ZIP containing one CSV per state.
- **Approximate Records:** ~1.5 million unique facilities nationally, linking ~2.0 million program interests.
- **Key Fields:** `REGISTRY_ID`, `PRIMARY_NAME`, `LOCATION_ADDRESS`, `CITY_NAME`, `STATE_CODE`, `POSTAL_CODE`, `LATITUDE83`, `LONGITUDE83`, `ACCURACY_VALUE`, `HUC_CODE`, `SIC_CODES`, `NAICS_CODES`, `INTEREST_TYPES` (program flags: AIR, NPDES, RCRA, SDWA, TRI, etc.).
- **Update Frequency:** Weekly (part of ECHO refresh cycle).
- **Notes:** Each state ZIP is a single flat CSV -- straightforward to ingest. Coordinates are NAD83.

### State Combined CSV Download (Multi-File)

- **URL:** <https://www.epa.gov/frs/epa-state-combined-csv-download-files>
- **Format:** ZIP containing multiple CSVs per state -- separate tables for facilities, interests, contacts, SIC codes, NAICS codes, alternative names.
- **Key Fields (facilities table):** Same core fields as single-file, plus `EPA_REGION`, `FEDERAL_FACILITY_CODE`, `TRIBAL_LAND_CODE`.
- **Key Fields (interests table):** `PGM_SYS_ACRNM` (program acronym), `PGM_SYS_ID` (program-specific ID), `INTEREST_TYPE`, `START_DATE`, `END_DATE`.
- **Notes:** Use combined files when you need to join program-specific IDs to facilities. The FRS `REGISTRY_ID` is the universal join key across all ECHO downloads.

### ECHO FRS Download

- **URL:** <https://echo.epa.gov/tools/data-downloads/frs-download-summary>
- **Format:** CSV in ZIP.
- **Data Dictionary:** <https://echo.epa.gov/system/files/FRS_summary.pdf>

### API

- **REST API docs:** <https://www.epa.gov/frs/facility-registry-service-frs-api>
- **Geospatial download service:** <https://www.epa.gov/frs/geospatial-data-download-service>

### Commercial Use Rights

Federal public domain. No restrictions on commercial redistribution. Attribute to EPA FRS.

---

## 2. EPA SDWIS / ECHO -- Safe Drinking Water Act (SDWA) Downloads

Public water system inventory, violations, enforcement, and compliance data.

### ECHO SDWA Data Downloads

- **URL:** <https://echo.epa.gov/tools/data-downloads/sdwa-download-summary>
- **Format:** ZIP containing multiple CSVs, one per table.
- **Approximate Records:** ~150,000 public water systems nationally (community, non-transient non-community, transient non-community).
- **Tables included:**
  - `SDWA_PUB_WATER_SYSTEMS` -- system inventory (PWSID, name, type, population served, source type, address, county, state).
  - `SDWA_VIOLATIONS` -- violation records by system and contaminant.
  - `SDWA_ENFORCEMENT_ACTIONS` -- formal/informal enforcement.
  - `SDWA_SITE_VISITS` -- inspection/site visit records.
  - `SDWA_LCR_SAMPLES` -- Lead and Copper Rule sample results.
  - `SDWA_SERVICE_AREAS` -- service area information.
- **Key Fields (water systems):** `PWSID`, `PWS_NAME`, `PWS_TYPE_CODE`, `PRIMARY_SOURCE_CODE`, `POPULATION_SERVED_COUNT`, `CITY_SERVED`, `COUNTY_SERVED`, `STATE_CODE`, `PRIMACY_AGENCY_CODE`.
- **Update Frequency:** Quarterly (from SDWIS Federal database).
- **Data Dictionary:** <https://echo.epa.gov/tools/data-downloads/sdwa-download-summary> (scroll to element dictionary).

### Envirofacts SDWIS

- **URL:** <https://enviro.epa.gov/envirofacts/sdwis/>
- **Access:** RESTful API with output in CSV, JSON, Excel, XML.
- **Notes:** Better for targeted queries (single system, single state) than full national download.

### Commercial Use Rights

Federal public domain. SDWIS data is reported by state primacy agencies to EPA; no commercial restrictions.

---

## 3. EPA ICIS-NPDES -- Clean Water Act Discharge Permits

National Pollutant Discharge Elimination System permit, outfall, compliance, and monitoring data.

### ICIS-NPDES Facility/Permit Downloads

- **URL:** <https://echo.epa.gov/tools/data-downloads/icis-npdes-download-summary>
- **Format:** ZIP containing multiple CSVs.
- **Approximate Records:** ~400,000+ permitted facilities nationally.
- **Tables included:**
  - `ICIS_FACILITIES` -- facility identification, address, location.
  - `ICIS_PERMITS` -- permit details (effective/expiration dates, permit type, major/minor status).
  - `ICIS_LIMIT_SETS` -- permit limit groupings.
  - `ICIS_PIPE_SCHEDULE_EXCEEDANCES` -- compliance schedule tracking.
  - `ICIS_INSPECTIONS` -- inspection records.
  - `ICIS_FORMAL_ACTIONS` -- enforcement actions.
  - `ICIS_INFORMAL_ACTIONS` -- informal enforcement.
- **Key Fields:** `NPDES_ID` (permit number), `FACILITY_NAME`, `FACILITY_TYPE_CODE`, `SIC_CODES`, `LATITUDE`, `LONGITUDE`, `CWP_STATUS`, `PERMIT_EFFECTIVE_DATE`, `PERMIT_EXPIRATION_DATE`.
- **Update Frequency:** Weekly.

### Discharge Points (Outfalls) Download

- **URL:** <https://echo.epa.gov/tools/data-downloads/icis-npdes-discharge-points-download-summary>
- **Format:** ZIP containing `NPDES_OUTFALLS_LAYER.csv`.
- **Contents:** Location of permitted discharge points/outfalls with facility, permit, and compliance data.
- **Key Fields:** `NPDES_ID`, `PERM_FEATURE_NMBR` (outfall ID), `LATITUDE`, `LONGITUDE`, `FACILITY_NAME`, `STATE_CODE`.
- **Update Frequency:** Weekly.
- **Notes:** This is the key spatial dataset -- point geometries for every permitted outfall in the US.

### DMR (Discharge Monitoring Report) Downloads

- **URL:** <https://echo.epa.gov/tools/data-downloads/icis-npdes-dmr-and-limit-data-set>
- **DMR summary:** <https://echo.epa.gov/tools/data-downloads/icis-npdes-dmr-summary>
- **Limit summary:** <https://echo.epa.gov/tools/data-downloads/icis-npdes-limit-summary>
- **Format:** ZIP per fiscal year; each contains `npdes_dmr_fyXXXX.csv`.
- **Available years:** FY2009 through present.
- **Contents:** Actual discharge monitoring values reported by permittees -- pollutant concentrations, flow rates, limit exceedances.
- **Key Fields:** `NPDES_ID`, `PERM_FEATURE_NMBR`, `MONITORING_PERIOD_END_DATE`, `PARAMETER_CODE`, `PARAMETER_DESC`, `LIMIT_VALUE_QUALIFIER`, `LIMIT_VALUE_STANDARD_UNITS`, `DMR_VALUE_STANDARD_UNITS`, `EXCEEDANCE_PCT`.
- **Update Frequency:** Quarterly per fiscal year file; weekly for current-year data.
- **Notes:** Files are large (hundreds of MB per year). Essential for pollutant loading analysis.

### Commercial Use Rights

Federal public domain. Freely redistributable with attribution.

---

## 4. EPA CWNS 2022 -- Clean Watersheds Needs Survey

Capital needs assessment for publicly owned wastewater treatment works.

- **URL:** <https://www.epa.gov/cwns/clean-watersheds-needs-survey-cwns-2022-report-and-data>
- **Data dashboard / CSV download:** <https://sdwis.epa.gov/ords/sfdw_pub/r/sfdw/cwns_pub/data-download>
- **Format:** CSV download from interactive dashboard; PDF report.
- **Approximate Records:** 17,544 publicly owned treatment works (POTWs) as of Jan 2022.
- **Key Fields:** Facility name, CWNS number, state, population served, treatment level, design flow, needs category, estimated cost.
- **Coverage:** Facilities serving 270.4 million Americans (82% of US population).
- **Total Needs Reported:** $630.1 billion (20-year capital needs as of Jan 1, 2022).
- **Update Frequency:** Conducted every 4 years (quadrennial to Congress). 2022 is the latest cycle.
- **Notes:** Best source for wastewater treatment capacity and infrastructure investment needs. Complements ICIS-NPDES permit data with planning/engineering data.

### Commercial Use Rights

Federal public domain. Published as a Report to Congress; freely redistributable.

---

## 5. EPA Sewersheds -- Wastewater Service Area Geometries

Modeled and collected polygon boundaries of wastewater treatment plant service areas.

- **URL:** <https://www.epa.gov/cwns/sewersheds>
- **GitHub (methods/code):** <https://github.com/USEPA/Sewersheds>
- **Format:** Polygon shapefile / geodatabase.
- **Approximate Records:** 17,084 sewersheds nationally.
  - 3,192 from authoritative public sources (state/local GIS data).
  - 13,892 modeled using machine learning (hexagonal grid, ~0.11 km^2 resolution).
- **Key Fields:** CWNS facility ID, facility name, state, service area polygon, data source (authoritative vs. modeled), population served.
- **Update Frequency:** Published with CWNS cycle; supplemental updates possible.
- **Contact:** CWNS@epa.gov (include "sewersheds map" in subject).

### Commercial Use Rights

Federal public domain. Modeled boundaries carry accuracy disclaimers but no commercial restrictions.

---

## 6. EPA Community Water System Service Area Boundaries

National polygon dataset of drinking water service areas linked to PWSID.

- **URL:** <https://www.epa.gov/ground-water-and-drinking-water/public-water-system-service-areas>
- **Boundaries detail:** <https://www.epa.gov/ground-water-and-drinking-water/community-water-system-service-area-boundaries>
- **Data standard (PDF):** <https://www.epa.gov/system/files/documents/2024-04/cws-service-area-boundaries-data-standard.pdf>
- **State summaries (PDF):** <https://www.epa.gov/system/files/documents/2024-04/cws-service-area-boundaries-state-dataset-summaries.pdf>
- **HydroShare mirror:** <https://www.hydroshare.org/resource/20b908d73a784fc1a097a3b3f2b58bfb/>
- **Format:** Polygon GeoJSON / Shapefile / Geodatabase.
- **Approximate Records:** ~44,000 community water system service areas covering ~99% of reported CWS population.
- **Provenance:**
  - ~60% from authoritative sources (states, water systems).
  - ~40% modeled by EPA using building footprints, population density, and service connections.
- **Key Fields:** `PWSID`, `PWS_NAME`, `STATE_CODE`, `POPULATION_SERVED`, `SOURCE_TYPE`, `DATA_SOURCE` (authoritative vs. modeled), service area polygon.
- **Origin:** Built on the SimpleLab/EPIC/Internet of Water Coalition provisional dataset (2022), refined by EPA.
- **Update Frequency:** Initial release 2024; ongoing updates planned.
- **Notes:** The `PWSID` field joins directly to SDWIS/ECHO SDWA data. This is the definitive spatial layer for "who gets water from where."

### Commercial Use Rights

Federal public domain. The underlying SimpleLab/EPIC dataset was released as open data; EPA's version inherits federal public domain status.

---

## 7. USACE National Inventory of Dams (NID)

Congressionally authorized database of dams in the United States.

### Web Portal

- **URL:** <https://nid.sec.usace.army.mil/>
- **Interactive map:** <https://nid.sec.usace.army.mil/nid/>

### API

- **Base URL:** `https://nid.sec.usace.army.mil/api`
- **Swagger docs:** <https://nid.sec.usace.army.mil/api/developer>
- **Access:** RESTful API using standard HTTP verbs, headers, status codes.
- **Format:** JSON responses; supports filtering by state, county, owner, hazard class, etc.

### GIS Services

- **FeatureServer:** <https://geospatial.sec.usace.army.mil/dls/rest/services/NID/National_Inventory_of_Dams_Public_Service/FeatureServer>
- **MapServer:** <https://geospatial.sec.usace.army.mil/dls/rest/services/NID/National_Inventory_of_Dams_Public_Service/MapServer>
- **ArcGIS Hub:** <https://geospatial-usace.opendata.arcgis.com/datasets/1632cb2bb23046569fbf2bc144f06764_0>

### Bulk Download

- **URL (ArcGIS Hub):** <https://geospatial-usace.opendata.arcgis.com/datasets/1632cb2bb23046569fbf2bc144f06764_0>
- **Formats:** CSV, KML, GeoJSON, Shapefile (ZIP), GeoTIFF, PNG.
- **Approximate Records:** ~92,000 dams nationally.
- **Key Fields:** `DAM_NAME`, `NID_ID`, `STATE`, `COUNTY`, `RIVER`, `LATITUDE`, `LONGITUDE`, `DAM_HEIGHT`, `MAX_STORAGE`, `NORMAL_STORAGE`, `NID_STORAGE`, `PURPOSES` (flood control, water supply, hydroelectric, recreation, etc.), `OWNER_TYPE`, `HAZARD_POTENTIAL`, `CONDITION_ASSESSMENT`, `YEAR_COMPLETED`, `DAM_TYPE`, `INSPECTION_DATE`.
- **Update Frequency:** Annual (states submit data; USACE publishes updated national dataset).

### Commercial Use Rights

Federal public domain. NID is a congressionally mandated public database maintained by USACE. No commercial restrictions. Some dam-specific security information may be redacted.

---

## 8. USGS Water Use Data

National compilation of water use estimates by source, category, state, and county.

### Water Use Data for the Nation (NWIS)

- **URL:** <https://waterdata.usgs.gov/>
- **Catalog entry:** <https://catalog.data.gov/dataset/usgs-water-use-data-for-the-nation-national-water-information-system-nwis>
- **Access guide:** <https://www.usgs.gov/mission-areas/water-resources/science/accessing-water-use-data/>

### County-Level Compilations (5-Year)

- **URL (2015):** <https://www.usgs.gov/data/estimated-use-water-united-states-county-level-data-2015>
- **URL (2020):** Available through Water Data for the Nation and Data Companion.
- **Format:** Tab-delimited text files, Excel, CSV.
- **Approximate Records:** ~3,200 counties x ~15 use categories = ~48,000 rows per compilation year.
- **Available Years:** 1950, 1955, 1960, 1965, 1970, 1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020.
- **Key Fields:** `STATE`, `COUNTY_FIPS`, `YEAR`, category-specific withdrawal columns (public supply, domestic, irrigation, thermoelectric, industrial, mining, livestock, aquaculture) in Mgal/day, by source (surface water, groundwater, reclaimed).
- **Update Frequency:** Every 5 years (quinquennial compilation).

### National Water Data Companion

- **URL:** <https://www.usgs.gov/special-topics/integrated-water-availability-assessments/national-water-availability-assessment-0>
- **Access:** Interactive web tool with API download capability.
- **Contents:** Monthly water use estimates 2000--2020; model-based supply and demand estimates.

### Water Use by Category Reports

- **URL:** <https://www.usgs.gov/mission-areas/water-resources/science/total-water-use>
- **Contents:** Narrative summaries with embedded data tables. Per-category breakdowns (public supply, irrigation, thermoelectric, industrial).

### Commercial Use Rights

Federal public domain (USGS). Freely redistributable with attribution. Standard USGS disclaimer on accuracy of estimates.

---

## 9. EPA ECHO Bulk Downloads -- All Tables

ECHO (Enforcement and Compliance History Online) is the single largest federal portal for environmental compliance data. It aggregates data from multiple EPA source systems.

### ECHO Exporter (Master Facility File)

- **URL:** <https://echo.epa.gov/tools/data-downloads>
- **Format:** Single large ZIP containing CSV.
- **Approximate Records:** ~1.5 million regulated facilities.
- **Key Fields (130+ columns):** `REGISTRY_ID` (FRS), `FAC_NAME`, `FAC_STREET`, `FAC_CITY`, `FAC_STATE`, `FAC_ZIP`, `FAC_COUNTY`, `FAC_FIPS_CODE`, `FAC_LAT`, `FAC_LONG`, `FAC_ACCURACY_VALUE`, `AIR_FLAG`, `NPDES_FLAG`, `SDWA_FLAG`, `RCRA_FLAG`, `TRI_FLAG`, `AIR_IDS`, `NPDES_IDS`, `SDWA_IDS`, `RCRA_IDS`, inspection counts, violation counts, penalty amounts, compliance status.
- **Update Frequency:** Weekly.
- **Notes:** File is too large for Excel; use Access, PostgreSQL, or GIS software. The `REGISTRY_ID` joins to all program-specific downloads.

### Program-Specific Downloads (all at echo.epa.gov/tools/data-downloads)

| Dataset | Summary URL | Contents | Update |
|---|---|---|---|
| **FRS** | [FRS summary](https://echo.epa.gov/tools/data-downloads/frs-download-summary) | Facility registry, cross-program linkage | Weekly |
| **ICIS-NPDES** | [NPDES summary](https://echo.epa.gov/tools/data-downloads/icis-npdes-download-summary) | CWA permits, facilities, compliance | Weekly |
| **NPDES Outfalls** | [Outfalls summary](https://echo.epa.gov/tools/data-downloads/icis-npdes-discharge-points-download-summary) | Discharge point locations | Weekly |
| **NPDES DMRs** | [DMR summary](https://echo.epa.gov/tools/data-downloads/icis-npdes-dmr-and-limit-data-set) | Monitoring reports by fiscal year | Quarterly |
| **NPDES Limits** | [Limits summary](https://echo.epa.gov/tools/data-downloads/icis-npdes-limit-summary) | Permit limit values | Weekly |
| **SDWA** | [SDWA summary](https://echo.epa.gov/tools/data-downloads/sdwa-download-summary) | Drinking water systems, violations | Quarterly |
| **ICIS-Air** | [Air summary](https://echo.epa.gov/tools/data-downloads/icis-air-download-summary) | CAA stationary source compliance | Weekly |
| **Air Emissions** | [Emissions summary](https://echo.epa.gov/tools/data-downloads/air-emissions-download-summary) | Criteria pollutant emissions | Annual |
| **RCRAInfo** | [RCRA summary](https://echo.epa.gov/tools/data-downloads/rcrainfo-download-summary) | Hazardous waste handlers, compliance | Weekly |
| **TRI** | [TRI summary](https://echo.epa.gov/tools/data-downloads/tri-download-summary) | Toxic Release Inventory reports | Annual |
| **ICIS-FE&C** | [FE&C summary](https://echo.epa.gov/tools/data-downloads/icis-fec-download-summary) | Federal enforcement and compliance | Weekly |

### Web Services (API)

- **URL:** <https://echo.epa.gov/tools/web-services>
- **Format:** REST API returning JSON/CSV/XML.
- **Notes:** Useful for programmatic queries and incremental updates; bulk downloads are better for initial loads.

### Commercial Use Rights

Federal public domain. All ECHO data is freely redistributable. Weekly refresh means data is near-current.

---

## 10. USGS National Water Availability Assessment (NWAA)

Integrated assessment of water quantity, quality, and use at national and regional scales.

### Report

- **URL:** <https://www.usgs.gov/special-topics/integrated-water-availability-assessments/national-water-availability-assessment>
- **Format:** PDF + interactive Key Findings website.
- **Contents:** Scientific summary and interpretation of water supply, demand, quality, and ecological flows.

### Data Companion

- **URL:** <https://www.usgs.gov/special-topics/integrated-water-availability-assessments/national-water-availability-assessment-0>
- **Access:** Interactive mapper + API/web service download.
- **Format:** CSV, JSON via API; interactive visualization online.
- **Contents:** Model-based estimates of:
  - Natural water supply (streamflow, groundwater recharge)
  - Water demand by sector
  - Ecological flow requirements
  - Water stress indicators
- **Spatial resolution:** HUC-based (HUC8 and HUC12 watersheds).
- **Key Fields:** HUC ID, water supply estimate, water demand estimate, water stress index, ecological flow metric, time period.

### National Water Census (Parent Program)

- **URL:** <https://www.usgs.gov/programs/water-availability-and-use-science-program/national-water-census>
- **ScienceBase catalog:** <https://www.sciencebase.gov/catalog/item/5151f07ee4b0f0b3d011a817>
- **Contents:** Research products, models, and data underlying the NWAA. Includes:
  - National Hydrologic Model (NHM) outputs
  - Water budget estimates
  - Streamflow statistics
  - Groundwater availability studies

### Commercial Use Rights

Federal public domain (USGS). All data products freely redistributable with standard USGS attribution and accuracy disclaimers.

---

## Quick Reference: Join Keys Across Datasets

| From | To | Join Key |
|---|---|---|
| FRS | Any ECHO download | `REGISTRY_ID` |
| ECHO SDWA | CWS Service Areas | `PWSID` |
| ECHO SDWA | Envirofacts SDWIS | `PWSID` |
| ECHO NPDES | NPDES Outfalls | `NPDES_ID` |
| ECHO NPDES | DMR data | `NPDES_ID` + `PERM_FEATURE_NMBR` |
| CWNS | Sewersheds | `CWNS_NUMBER` |
| NID | FRS | Match by `LATITUDE`/`LONGITUDE` or name (no direct ID link) |
| USGS Water Use | Census/NHD | `COUNTY_FIPS`, `HUC` |
| NWAA Data Companion | NHD/WBD | `HUC8` / `HUC12` |

---

## Recommended Ingestion Order

1. **EPA FRS state CSVs** -- master facility spine with coordinates and program flags.
2. **ECHO SDWA** -- drinking water systems joined via `PWSID`.
3. **CWS Service Area Boundaries** -- spatial polygons joined via `PWSID`.
4. **ICIS-NPDES Outfalls** -- discharge point locations with permit data.
5. **EPA Sewersheds** -- wastewater service area polygons linked to CWNS.
6. **USACE NID** -- dam locations and attributes.
7. **USGS Water Use** -- county-level withdrawal estimates for demand context.
8. **CWNS 2022** -- treatment plant capacity and infrastructure needs.
9. **DMR data** -- pollutant monitoring (large; load by fiscal year as needed).
10. **NWAA Data Companion** -- watershed-level supply/demand context.
