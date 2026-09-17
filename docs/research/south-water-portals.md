# Southern / Border State Water Data Portals

Research catalog for Arkansas, Oklahoma, and Texas water facility data sources.
Compiled 2026-09-15 for hydro-art facility intelligence layer.

---

## Arkansas

### Agency

**Arkansas Department of Agriculture -- Natural Resources Division** (formerly ANRC)
manages water rights, allocation, and groundwater protection.
**Arkansas Department of Energy & Environment -- Division of Environmental Quality (DEQ)**
manages drinking water, NPDES, and water quality.

### 1. Water Rights / Withdrawal Permit Database

- **Agency:** Arkansas Dept. of Agriculture, Natural Resources Division
- **URL:** <https://agriculture.arkansas.gov/natural-resources/water-management/groundwater-protection-and-management-program/water-use-registration/>
- **Access:** Online registration portal; non-domestic users withdrawing >= 50,000 gal/day (groundwater) or >= 1 acre-foot/yr (surface) must report monthly withdrawals Oct 1 -- Mar 1 each year.
- **Format:** Web form lookup; no public bulk CSV/shapefile advertised. County-level registration maps determine contact (conservation district vs. department direct).
- **Notes:** Arkansas follows a "reasonable use" riparian doctrine for surface water. Groundwater is regulated via the critical-area / non-critical-area framework under ANRC rules (Title III, ANRC-138.00).

### 2. Drinking Water Program Portal

- **Agency:** Arkansas Department of Health (ADH) -- Engineering Division
- **URL:** EPA SDWIS Federal search covers AR systems: <https://enviro.epa.gov/envirofacts/sdwis/>
- **Access:** No state-run "Drinking Water Watch" equivalent found. ADH manages public water system permitting; compliance data flows through federal SDWIS/ECHO.
- **Format:** Query via EPA Envirofacts or ECHO SDWA downloads (CSV).

### 3. Wastewater / NPDES Portal

- **Agency:** Arkansas DEQ -- Water Division
- **URL:** <https://www.adeq.state.ar.us/water/permits/>
- **Access:** DEQ ePortal for online submission and tracking of General NPDES and No-Discharge permits. Individual NPDES permits handled through the Individual Permits Branch.
- **DMR Submission:** Required electronically via NetDMR since Dec 2016.
- **Bulk Data:** National ICIS-NPDES downloads from ECHO cover AR facilities (see federal-data-sources.md).

### 4. Groundwater Well Registry

- **URL:** No centralized state well registry with public bulk download identified.
- **Alternative:** USGS Arkansas Groundwater-Quality Network provides a web map interface linked to NWIS and EPA STORET: <https://pubs.usgs.gov/fs/2013/3042/>
- **Format:** Interactive map; download via NWIS web services.

### 5. Bulk Download Availability

Limited. Arkansas does not publish a single state-level bulk download of water rights or well records. Best federal proxies: EPA FRS state CSV, ECHO SDWA/NPDES downloads.

### 6. Commercial Use Rights

USGS/EPA data: federal public domain. State-submitted data through federal portals inherits federal terms. Direct state data: no explicit commercial license found; verify with ADH/DEQ before redistribution.

---

## Oklahoma

### Agency

**Oklahoma Water Resources Board (OWRB)** manages water rights, permitting, groundwater wells, and data.
**Oklahoma Department of Environmental Quality (ODEQ)** manages drinking water and NPDES discharge permits.

### 1. Water Rights / Withdrawal Permit Database

- **Agency:** OWRB
- **URL (interactive map):** <https://maps.owrb.ok.gov/arcgis/rest/services/Water_Rights/Water_Rights/MapServer>
- **URL (open data hub):** <https://home-owrb.opendata.arcgis.com/datasets/water-use-permits-in-oklahoma>
- **Pending permits:** <https://home-owrb.opendata.arcgis.com/datasets/pending-water-permits-in-oklahoma>
- **Access:** ArcGIS Open Data Hub -- download as CSV, Shapefile, GeoJSON, KML.
- **Format:** Shapefile / CSV / GeoJSON via ArcGIS Hub; REST MapServer for programmatic access.
- **Key fields:** Permit number, owner, source (GW/SW), authorized amount, location (lat/lon), basin, status.
- **Notes:** Oklahoma uses a prior-appropriation system for both surface and groundwater. OWRB issues permits for all non-domestic use.

### 2. Drinking Water Program Portal

- **Agency:** ODEQ -- Water Quality Division, Drinking Water Branch
- **URL:** <http://sdwis.deq.state.ok.us/DWW/> (Oklahoma Drinking Water Watch)
- **Access:** Web search by PWS ID, county, or system name.
- **Format:** HTML display; no direct bulk download from state portal. Use EPA ECHO SDWA downloads for bulk.
- **OWRB viewer:** <https://www.owrb.ok.gov/maps/pmg/ViewerInfo_PWSS.html>

### 3. Wastewater / NPDES Portal

- **Agency:** ODEQ
- **URL (permit applications):** <https://applications.deq.ok.gov/nviro/nform/>
- **URL (stored permits):** <https://applications.deq.ok.gov/permitspublic/storedpermits/>
- **NPDES outfalls map service:** <https://owrb.csa.ou.edu/server/rest/services/Layers/NPDES_Outfalls/MapServer>
- **Access:** Individual permit PDFs via ODEQ portal; outfall locations via ArcGIS REST service.
- **Bulk Data:** National ICIS-NPDES downloads from ECHO cover OK facilities.

### 4. Groundwater Well Registry

- **Agency:** OWRB
- **URL (open data):** <https://home-owrb.opendata.arcgis.com/maps/d96fcad9d6514429a986e06dfcc45e57> (Oklahoma Groundwater Wells)
- **URL (data & maps):** <https://owrb.ok.gov/maps/pmg/owrbdata_gw.html>
- **Access:** Interactive map viewer; downloads available as Geodatabase (ZIP), Shapefile (ZIP), Data Table (ZIP).
- **Format:** Shapefile, Geodatabase, CSV tables.
- **Notes:** Database includes well logs. Locations are self-reported and may have accuracy limitations.

### 5. Bulk Download Availability

Good. OWRB Open Data Hub provides multiple datasets (water use permits, groundwater wells, pending permits) in standard GIS formats. ODEQ drinking water data best accessed via federal ECHO.

### 6. Commercial Use Rights

OWRB Open Data Hub: standard ArcGIS Hub terms, generally open for reuse. Verify ODEQ-specific data terms. Federal proxies (ECHO/FRS) are public domain.

---

## Texas (Priority State)

### Agency

**Texas Commission on Environmental Quality (TCEQ)** manages surface water rights, drinking water, and NPDES (TPDES) permits.
**Texas Water Development Board (TWDB)** manages groundwater data, water planning, and the state water use survey.
**Groundwater Conservation Districts (GCDs)** regulate groundwater locally under the "rule of capture" doctrine, modified by GCD permitting.

### 1. Water Rights / Withdrawal Permit Database

#### TCEQ Water Rights Data Files

- **URL:** <https://www.tceq.texas.gov/permitting/water_rights/wr-permitting/wrwud>
- **Access:** Direct download of compressed data files (7ZIP format).
- **Contents:** All active and inactive surface water rights permits and water supply contracts.
- **Key fields:** Water right holder, basin, authorized amount, priority date, permit type, status.
- **Format:** Delimited text files with data dictionary.
- **Notes:** Files are comprehensive -- every certificated, permitted, and contracted surface water right in Texas. Contact: wras@tceq.texas.gov.

#### TCEQ Water Rights Viewer (Interactive)

- **URL:** <https://www.tceq.texas.gov/gis/water-rights-viewer>
- **Access:** Web-based ArcGIS map application.
- **Capabilities:**
  - Location of authorized water rights diversion/storage points
  - Copy of the water right document and Adjudication Final Determination
  - Current ownership records
  - Recent water use data (self-reported)
  - TCEQ-adopted environmental flow standards
- **Notes:** Best tool for per-right spatial lookup. Does not support bulk export; use the data files above for bulk.

#### GIS Diversion Points

- **URL (TCEQ GIS Data Hub):** <https://gis-tceq.opendata.arcgis.com/>
- **URL (raw datasets):** <https://www.tceq.texas.gov/agency/data/lookup-data/download-data.html>
- **Access:** ArcGIS Open Data Hub for interactive exploration; raw dataset downloads for bulk.
- **Format:** Shapefile / GeoJSON / CSV via ArcGIS Hub; compressed files via raw download page.
- **Contents:** Surface Water Rights Diversion Points layer -- point geometries for every permitted diversion location with permit attributes.
- **Key fields:** Permit number, owner, lat/lon, basin, authorized volume, diversion type.

#### Self-Reported Water Use Data

- **URL:** <https://www.tceq.texas.gov/permitting/water_rights/wr-permitting/wrwud>
- **Access:** Download water use data files by time period.
- **Periods available:** Pre-1990, 1990--1999, 2000--2014, and subsequent reporting years.
- **Format:** Spreadsheet/delimited text with field dictionary.
- **Contents:** Annual water use amounts reported by water right holders in non-watermaster areas. Data is self-reported (not metered in most cases).
- **Annual reporting:** Water right holders must report water use annually. TCEQ provides Excel templates for electronic submission.
- **Contact:** Water Rights Compliance Assurance Team, 512-239-4600.

#### Water Availability Models (WAM)

- **URL:** <https://www.tceq.texas.gov/permitting/water_rights/wr_technical-resources/wam.html>
- **Access:** Download WAM datasets by river basin.
- **Format:** Model input/output files.
- **Notes:** Basin-level simulation models used for water rights permitting decisions. Useful for supply/demand analysis but not a facility database.

### 2. Drinking Water Program Portal

- **Agency:** TCEQ -- Public Drinking Water Program
- **URL (Drinking Water Viewer):** <https://dwv.tceq.texas.gov/>
- **URL (program home):** <https://www.tceq.texas.gov/drinkingwater>
- **Access:** Web search by PWS ID, name, county, or location. Replaced the former "Drinking Water Watch" (DWW).
- **Contents:** Chemical/microbial sample results, compliance schedules, monitoring requirements, violations, enforcement actions, facilities/contracts/inventory.
- **Format:** HTML display with per-system detail pages.
- **Bulk:** No state bulk download found. Use EPA ECHO SDWA download for bulk TX drinking water data.
- **Contact:** 512-239-1071, PDWS@tceq.texas.gov.

### 3. Wastewater / TPDES Portal

- **Agency:** TCEQ (Texas operates its own program, TPDES, in lieu of federal NPDES)
- **URL (GIS Data Hub):** <https://gis-tceq.opendata.arcgis.com/>
- **URL (raw data downloads):** <https://www.tceq.texas.gov/agency/data/lookup-data/download-data.html>
- **Access:** TCEQ raw dataset downloads include wastewater permit and outfall data. GIS Data Hub provides spatial layers.
- **Bulk:** National ICIS-NPDES downloads from EPA ECHO cover TX TPDES facilities.
- **Notes:** TPDES permits are the Texas equivalent of NPDES. Same federal reporting requirements apply.

### 4. Groundwater Well Registry

- **Agency:** TWDB
- **URL (downloads):** <https://www.twdb.texas.gov/groundwater/data/gwdbrpt.asp>
- **URL (GIS well locations):** <https://txwaterdatahub.org/dataset/groundwater-database-well-locations>
- **URL (interactive viewer):** <https://txwaterdatahub.org/application/groundwater-data-viewer>
- **Access:** Entire Groundwater Database (GWDB) available for download; shapefile of well locations updated nightly via Texas Water Data Hub.
- **Format:** Shapefile, database export.
- **Contents:** Selected water wells, springs, oil/gas test wells, water levels, water quality.
- **Key fields:** Well ID, location (lat/lon), depth, aquifer, water level records, quality parameters.
- **Caveat:** Most well locations are not verified by state staff and may be inaccurate.
- **BRACS GIS Data:** <https://www.twdb.texas.gov/groundwater/bracs/GISdata.asp> -- study-area datasets in NAD83 Albers projection.
- **Well/Plugging Reports:** <https://www.twdb.texas.gov/groundwater/data/well-reports-test.asp>
- **Driller Reports:** <https://www.twdb.texas.gov/groundwater/data/drillersdb.asp>

### 5. Bulk Download Availability

Excellent. Texas provides the most comprehensive bulk download ecosystem of the three states:

| Dataset | Source | Format | Bulk? |
|---|---|---|---|
| Surface water rights | TCEQ data files | Delimited text (7ZIP) | Yes |
| Diversion points (GIS) | TCEQ GIS Data Hub | Shapefile/GeoJSON/CSV | Yes |
| Self-reported water use | TCEQ data files | Spreadsheet | Yes |
| Drinking water systems | TCEQ DWV / EPA ECHO | HTML / CSV | Partial (ECHO) |
| Wastewater permits | TCEQ raw downloads / EPA ECHO | CSV | Yes |
| Groundwater wells | TWDB GWDB | Shapefile/DB export | Yes |
| Water districts (GIS) | TCEQ GIS Data Hub | Shapefile | Yes |

### 6. Commercial Use Rights

- **TCEQ data:** Texas state government data is generally public record under the Texas Public Information Act. No explicit commercial restriction found on TCEQ data downloads. Verify per-dataset terms.
- **TWDB data:** Public record. Groundwater database downloads carry a disclaimer about location accuracy but no commercial restriction.
- **Federal proxies (EPA/USGS):** Public domain, freely usable with attribution.
- **Recommendation:** Safe to use for commercial products with source attribution. Document provenance per asset.

---

## Cross-State Comparison

| Capability | AR | OK | TX |
|---|---|---|---|
| Water rights bulk download | No | Yes (OWRB Hub) | Yes (TCEQ files) |
| GIS diversion/well points | No | Yes (Shapefile) | Yes (Shapefile) |
| Drinking water portal | Federal only | DWW (lookup) | DWV (lookup) |
| NPDES/wastewater bulk | Federal only | Federal + REST | TCEQ + Federal |
| Groundwater well registry | No state bulk | Yes (OWRB Hub) | Yes (TWDB) |
| Overall data maturity | Low | Medium | High |

Texas is the clear priority for state-level integration; Oklahoma is viable via the OWRB Open Data Hub; Arkansas data is best accessed through federal sources (EPA FRS, ECHO).
