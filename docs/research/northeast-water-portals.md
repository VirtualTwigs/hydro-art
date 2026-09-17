# Northeast US Water Rights, Permits, and Facility Data Portals

Research compiled 2026-09-15 covering 11 Northeastern states: CT, DE, ME, MD, MA, NH, NJ, NY, PA, RI, VT.

> **Context.** Eastern states follow the riparian doctrine (reasonable use), not western prior-appropriation.
> Large withdrawals typically require permits; smaller uses are registered or unrestricted.
> All state SDWIS/drinking-water data also flows to EPA's federal SDWIS; all NPDES/discharge
> monitoring also appears in EPA ECHO/ICIS. The portals below are the *state-level* systems that
> carry richer local detail.

---

## Summary Matrix

| State | Water Rights Agency | Withdrawal Permit DB | Drinking Water Portal | Wastewater/NPDES Portal | Well Registry | Bulk Download |
|-------|-------------------|---------------------|----------------------|------------------------|---------------|---------------|
| CT | DEEP | PDF/Excel list | DPH compliance reports | DEEP portal (delegated) | data.ct.gov (Open Data) | Partial (Excel, GIS shapefiles) |
| DE | DNREC Div. of Water | DNREC portal | DHSS Drinking Water Watch | DNREC NPDES portal | DNREC Well Viewer + FirstMap | Yes (FirstMap ArcGIS Hub) |
| ME | DEP | DEP SWUP reports | ME CDC DWP | DEP Waste Discharge (MEPDES) | MGS Well Database (ArcGIS Hub) | Yes (MGS shapefiles, 50k+ wells) |
| MD | MDE Water Supply | WSIP Withdrawal Portal | MDE Water Supply | MDE Wastewater Permits | MGS / MDE WSIPS | Partial (iMap GIS Catalog) |
| MA | MassDEP | EEA ePlace Portal | MassDEP DWRS | MassDEP (delegated) | MassDEP Well DB + MassGIS | Yes (MassGIS shapefiles) |
| NH | NHDES | NHDES permits (PDF list) | NHDES OneStop / Geodata | EPA-administered (not delegated) | NHDES Geodata Portal (ArcGIS Hub) | Yes (ArcGIS feature layers) |
| NJ | NJDEP Water Supply | NJDEP DataMiner | NJDEP Drinking Water Watch | NJDEP DWQ (NJPDES, delegated) | NJDEP DataMiner + ePermitting | Yes (DataMiner, NJ-GeoWeb, Open Data) |
| NY | NYSDEC | DECinfo Locator | NYS Water Quality Portal | NYSDEC SPDES (delegated) | NYS GIS Clearinghouse | Yes (GIS Clearinghouse shapefiles) |
| PA | DEP | DEP eFACTS | PA DWRS / PADWIS | DEP Wastewater Reports | PaGWIS (DCNR) via PaGEODE | Yes (PASDA shapefiles, ArcGIS Hub) |
| RI | DEM OWR | OWR Permit Portal | DEM / DOH | DEM RIPDES (delegated) | RI WUNDR (URI/RIGS) | Partial (WUNDR download) |
| VT | DEC (ANR) | ANR Online | DEC Drinking Water Watch | DEC Discharge Permits (delegated) | ANR Well Driller Reports DB | Partial (ANR Atlas, dashboards) |

---

## Connecticut (CT)

### Agency
**CT Department of Energy and Environmental Protection (DEEP)** -- Water Diversion Program.
Drinking water regulated separately by the **CT Department of Public Health (DPH)**.

### Water Withdrawal / Diversion Permits
- **Program:** Water Diversion Program -- permits required for withdrawals >50,000 GPD from surface or groundwater.
- **Database URL:** https://portal.ct.gov/DEEP/Water/Diversions/Water-Diversion-Permits
- **Access method:** PDF and Excel download of all consumptive diversion permits and registrations (updated periodically).
- **Format:** PDF list, Excel spreadsheet.
- **Bulk download:** Yes -- Excel file of all permits/registrations available from the program page.

### Drinking Water Program
- **Agency:** CT DPH, Drinking Water Section (DWS).
- **Portal:** https://portal.ct.gov/dph/environmental-health/environmental-public-health-tracking/water-quality
- **Access method:** Annual compliance reports (PDF); data also submitted quarterly to federal SDWIS/FED.
- **Format:** PDF reports; no public interactive query tool identified beyond federal SDWIS.

### Wastewater / NPDES
- **Program:** CT is a delegated NPDES state; DEEP issues permits.
- **Portal:** https://portal.ct.gov/deep/water-regulating-and-discharges/industrial-wastewater
- **Access method:** Permit documents available through DEEP portal; electronic DMR submission required.
- **Bulk download:** Individual permits viewable; no consolidated downloadable database identified.

### Groundwater Well Registry
- **Database:** Wells in Connecticut -- CT Open Data Portal.
- **URL:** https://data.ct.gov/Environment-and-Natural-Resources/Wells-in-Connecticut/wphv-ux6v
- **Access method:** Open Data portal with API, CSV, and map view. Contains wells submitted online since Jan 2021.
- **Format:** CSV, JSON, GeoJSON via Socrata API.
- **Bulk download:** Yes -- full dataset downloadable from data.ct.gov.

### GIS / Bulk Data
- **CT ECO:** https://maps.cteco.uconn.edu/download/ -- environmental/natural resource GIS layers (shapefile, GDB, KML, CSV).
- **CT DEEP GIS Open Data:** https://ct-deep-gis-open-data-website-ctdeep.hub.arcgis.com/ -- ArcGIS Hub with downloadable layers.
- **CT Geodata Portal:** https://geodata.ct.gov/

### Commercial Use
CT Open Data is published under open terms. Federal USGS/EPA source data is public domain. No specific redistribution restriction identified on the state open data portal, but verify terms of use for each dataset.

---

## Delaware (DE)

### Agency
**DE Dept. of Natural Resources and Environmental Control (DNREC)** -- Division of Water, Water Supply Section.

### Water Allocation Permits
- **Program:** Water Allocation permits required for withdrawals >50,000 GPD.
- **Database URL:** https://dnrec.delaware.gov/water/commercial-government/water-allocation/
- **Access method:** Online reporting portal; permit applications and public notices on DNREC website.
- **Format:** Web portal, PDF notices.
- **Bulk download:** Not publicly available as a consolidated download; contact DNREC Water Allocation (DNREC_Water_Allocation@delaware.gov, 302-739-9945).

### Drinking Water Program
- **Agency:** DE Division of Public Health (DHSS) -- Office of Drinking Water.
- **Portal:** Drinking Water Watch system (managed by DHSS).
- **Access method:** Searchable web viewer for public water system records.

### Wastewater / NPDES
- **Program:** DNREC issues individual NPDES permits for surface water discharges.
- **Portal:** https://dnrec.delaware.gov/water/commercial-government/npdes/individual/
- **Access method:** Digital DNREC ePermitting system for applications; permit documents available online.

### Groundwater Well Registry
- **DNREC Well Viewer:** https://dnrec.delaware.gov/water/residential/well-permits/viewer/
  - Map-based tool for well locations. Data from FirstMap and DRBC.
- **FirstMap (ArcGIS Hub):** https://de-firstmap-delaware.hub.arcgis.com/
  - Permitting and monitoring layers, water data layers.
- **Access method:** Interactive map viewer; GIS layers downloadable from FirstMap Hub.
- **Format:** ArcGIS feature layers; shapefile/GeoJSON export from Hub.

### GIS / Bulk Data
- **DNREC Geospatial Data:** https://dnrec.delaware.gov/water/digital-resources/geospatial-data/
- **DNREC Open Data:** https://dnrec.delaware.gov/dnrec-open-data/
- **DE FirstMap Data:** https://de-firstmap-delaware.hub.arcgis.com/pages/data
- **Format:** Shapefile, GDB, feature service via ArcGIS Hub.

### Commercial Use
FirstMap data is published for public use. Federal source data is public domain. Check individual dataset metadata for specific license terms.

---

## Maine (ME)

### Agency
**ME Dept. of Environmental Protection (DEP)** -- Sustainable Water Use Program (SWUP).
Drinking water under **ME CDC (DHHS)**.
Geological/well data under **ME Geological Survey (DACF)**.

### Water Withdrawal Permits
- **Program:** Reporting thresholds: 20,000 GPD for rivers/streams; 50,000 GPD for groundwater (>500 ft from surface water).
- **Portal:** https://www.maine.gov/dep/water/swup/report.html
- **Access method:** Annual reporting to DEP; aggregated watershed data in legislative reports (PDF).
- **Format:** PDF reports; individual reports confidential.
- **Bulk download:** No public consolidated permit database identified.

### Drinking Water Program
- **Agency:** Maine CDC Drinking Water Program (DWP).
- **Portal:** https://www.maine.gov/dhhs/mecdc/environmental-health/water/index.htm
- **Access method:** Searchable database of subsurface wastewater disposal system designs by town.
- **GIS:** DEP GIS Unit provides public water supply well/intake locations via Google Earth KML.
  - https://www.maine.gov/dep/gis/datamaps/DWP_Wells/index.html

### Wastewater / MEPDES
- **Program:** Maine is a delegated NPDES state (MEPDES).
- **Portal:** https://www.maine.gov/dep/water/wd/index.html
- **Access method:** NetDMR for electronic discharge monitoring reports; permit documents on DEP site.

### Groundwater Well Registry
- **Maine Geological Survey Water Well Database:**
  - **URL:** https://www.maine.gov/dacf/mgs/pubs/digital/well.htm
  - **ArcGIS Hub:** https://maine-water-well-database-maine.hub.arcgis.com/
  - **MGS Open Data:** https://mgs-maine.opendata.arcgis.com/
  - **Records:** 50,000+ located wells (since 1987 Well Information Law).
  - **Access method:** Download from MGS digital data page or ArcGIS Hub.
  - **Format:** Shapefile, feature layer; includes depth, yield, overburden thickness, well type.
  - **Bulk download:** Yes -- full dataset downloadable.

### Commercial Use
Maine Geological Survey data is published for public use. Federal source data is public domain. Standard government data reuse terms apply.

---

## Maryland (MD)

### Agency
**MD Dept. of the Environment (MDE)** -- Water Supply Program (WSP), Water and Science Administration.
Geological data under **MD Geological Survey (MGS)**.

### Water Appropriation Permits
- **Program:** Water Appropriation and Use Permit required for withdrawals >10,000 GPD.
- **Portal:** https://mde.maryland.gov/programs/water/water_supply/pages/waterappropriationsorusepermits.aspx
- **Reporting Portal:** https://wsipwithdrawalportal.mde.state.md.us/ (WSIP -- electronic water use reporting).
- **Access method:** Web portal for permitted users; public notices of new applications on MDE site.
- **Managed permits:** ~6,900 active (6,000 groundwater, remainder surface water).
- **Bulk download:** Not identified as a public bulk download; Open MDE page provides some searchable data.

### Drinking Water Program
- **Agency:** MDE Water Supply Program.
- **Portal:** https://mde.maryland.gov/programs/water/water_supply/Pages/index.aspx
- **WSIPS Database:** Custom database with Map View access to internal GIS + external databases.
- **Aquifer Information System (AIS):** Joint MDE/USGS/MGS tool -- aquifer surfaces, borehole data, hydraulic properties, well records, geophysical logs.
- **Access method:** Web viewer; some data accessible through Open MDE.

### Wastewater / NPDES
- **Program:** Maryland is a delegated NPDES state.
- **Portal:** https://mde.maryland.gov/programs/water/wwp/pages/index.aspx
- **Access method:** Permit documents and compliance data via Open MDE.
- **Open MDE:** https://mde.maryland.gov/Pages/Open-MDE.aspx -- searchable permit/compliance data.

### Groundwater Well Registry
- **MGS Groundwater Use:** https://www.mgs.md.gov/groundwater/wateruse.html
- **Maryland GIS Data Catalog (iMap):** https://data.imap.maryland.gov/
- **Access method:** iMap provides GIS layers for download; MGS provides groundwater data and maps.
- **Format:** Various GIS formats via iMap (shapefile, feature service).
- **Bulk download:** Partial -- available through iMap GIS Catalog.

### Commercial Use
iMap data published under Maryland open data terms. Federal data is public domain. Check specific dataset licenses.

---

## Massachusetts (MA)

### Agency
**MA Dept. of Environmental Protection (MassDEP)** -- Water Management Act program.

### Water Management Act Permits
- **Program:** Permits required for withdrawals >100,000 GPD annual average (or >9M gallons in any 3-month period). Registrations for pre-1988 large users (>100,000 GPD based on 1981-1985 use).
- **Application portal:** EEA ePlace Portal (online filing).
- **Info URL:** https://www.mass.gov/lists/water-management-act-wma-permitting
- **Access method:** Online application via ePlace; permit/registration lists on Mass.gov.
- **Format:** Web portal, PDF documents.
- **Bulk download:** Permit lists available as documents; no consolidated GIS layer of all permits identified.

### Drinking Water Program
- **Portal:** MassDEP Drinking Water Reporting System (DWRS) -- public access to sample history, inventory, violation history.
- **Water Quality Data Viewer:** https://arcgisserver.digital.mass.gov/massdepwaterquality/Home/Index
- **MassGIS public water supply data:** https://www.mass.gov/info-details/massgis-data-massdep-estimated-public-drinking-water-system-service-area-boundaries
- **Access method:** Interactive map viewer, MassGIS download.
- **Format:** Shapefile, feature service.

### Wastewater / NPDES
- **Program:** Massachusetts is a delegated NPDES state.
- **Access method:** MassDEP administers permits; data also in EPA ECHO.

### Groundwater Well Registry
- **MassDEP Well Database:** https://www.mass.gov/info-details/well-database
  - Searchable by city/town, well ID, well type, date range, work type.
  - ~200,000 Well Completion Reports (WCRs) on file.
- **MassGIS Well Location Viewer:** Depicts locations of vetted WCRs.
  - Data on EEA Data Portal.
- **Access method:** Searchable web database + GIS viewer.
- **Format:** MassGIS provides shapefile/feature layers.
- **Bulk download:** Yes -- MassGIS provides downloadable datasets.

### GIS / Bulk Data
- **MassGIS:** https://www.mass.gov/orgs/massgis-bureau-of-geographic-information -- comprehensive state GIS data hub.
- **Format:** Shapefile, GDB, feature services.

### Commercial Use
MassGIS data is published for public use under standard government terms. Federal source data is public domain.

---

## New Hampshire (NH)

### Agency
**NH Dept. of Environmental Services (NHDES)** -- Water Division.
Geological survey under NHDES (NH Geological Survey).

### Water Withdrawal Permits
- **Program:** Large Groundwater Withdrawal Permit required for >57,600 GPD (40 GPM average). Applies to wells installed after August 1998.
- **Info URL:** https://www.des.nh.gov/water/groundwater/water-use-and-withdrawal/large-groundwater-withdrawal
- **Issued permits:** PDF summary table at https://www.des.nh.gov/sites/g/files/ehbemt341/files/documents/lgwp-summary-table.pdf
- **Access method:** PDF list of issued permits; applications through NHDES.
- **Format:** PDF.
- **Bulk download:** No consolidated database; PDF summary only.

### Drinking Water Program
- **Portal:** NHDES OneStop Web GIS (requires registration).
- **Geodata Portal:** https://nh-department-of-environmental-services-open-data-nhdes.hub.arcgis.com/
  - Public Water Supply Wells layer available.
- **Access method:** ArcGIS Hub feature layers; OneStop registration for full GIS access.
- **Format:** ArcGIS feature layers (shapefile/GeoJSON export).

### Wastewater / NPDES
- **Important:** New Hampshire is one of three states **not delegated** for NPDES. EPA Region 1 administers NPDES permits directly.
- **NHDES role:** NHDES must certify that NPDES permit conditions meet state standards.
- **GIS layer:** NPDES facilities available on NHDES Geodata Portal ArcGIS Hub.
- **Portal:** https://www.des.nh.gov/waste/wastewater/npdes-permits-and-compliance

### Groundwater Well Registry
- **Water Well Inventory Database:** 135,000+ records (since 1984, RSA 482-B).
- **NHDES Geodata Portal (ArcGIS Hub):**
  - https://nh-department-of-environmental-services-open-data-nhdes.hub.arcgis.com/datasets/water-well-inventory-1
- **Data includes:** Well construction details, depth, yield, overburden thickness, use, type, geologic materials.
- **Access method:** ArcGIS Hub feature layer -- online query, map view, download.
- **Format:** Feature layer with shapefile/CSV/GeoJSON export.
- **Bulk download:** Yes -- full dataset downloadable from ArcGIS Hub.

### GIS / Bulk Data
- **NHDES Geodata Portal:** https://nh-department-of-environmental-services-open-data-nhdes.hub.arcgis.com/
- **NHDES Data and Mapping:** https://www.des.nh.gov/resource-center/data-and-mapping
- **Format:** ArcGIS feature layers, downloadable.

### Commercial Use
NHDES Geodata Portal data is published for public access. Standard government data terms. Federal source data is public domain.

---

## New Jersey (NJ)

### Agency
**NJ Dept. of Environmental Protection (NJDEP)** -- Division of Water Supply and Geoscience; Bureau of Water Allocation (BWA).

### Water Allocation Permits
- **Program:** Permits for diversions >100,000 GPD.
- **Portal:** https://dep.nj.gov/watersupply/water-allocation/water-allocation-permits-registrations-utilization/
- **DataMiner:** https://www13.state.nj.us/DataMiner/Search/SearchByCategory?isExternal=y&getCategory=y&catName=Water+Supply+and+Geoscience
  - BWA Diversion Source Radial Search reports; monthly diversion data for permitted points.
- **Access method:** NJDEP DataMiner web queries; NJDEP Online for utilization submissions.
- **Format:** Web query results, downloadable reports.
- **Bulk download:** Yes -- DataMiner provides query-based exports; historical dBASE files available for GIS polygon coverages.

### Drinking Water Program
- **Drinking Water Watch:** https://www-dep.nj.gov/DEP_WaterWatch_public/
  - Searchable by water system ID, name, county, municipality.
- **Find My Water System:** https://dep.nj.gov/watersupply/drinking-water-consumers/your-utility-its-water/
- **Access method:** Interactive web viewer.

### Wastewater / NJPDES
- **Program:** NJ is a delegated NPDES state (NJPDES).
- **Portal:** https://dep.nj.gov/dwq/permitting_information/data_access_and_reports/
- **DataMiner:** NJPDES permit data available through DataMiner application.
- **Access method:** Web query, downloadable reports.
- **Bulk download:** Yes -- via DataMiner and OPRA requests.

### Groundwater Well Registry
- **NJDEP DataMiner Well Search:** Permits, records, decommissioning reports (electronically submitted via ePermitting).
  - https://njems.nj.gov/dataminer/
- **Well Permitting:** https://dep.nj.gov/watersupply/wells/well-permits-program-information/
- **NJ Geological and Water Survey:** https://dep.nj.gov/njgws/ -- interactive geological mapping, aquifer locations, wellhead protection areas.
- **Access method:** DataMiner queries; NJ-GeoWeb interactive map.
- **Format:** Query results, GIS layers.
- **Bulk download:** Yes -- through DataMiner and NJ-GeoWeb.

### GIS / Bulk Data
- **NJDEP Open Data:** https://gisdata-njdep.opendata.arcgis.com/
- **NJ-GeoWeb:** Interactive GIS application with downloadable layers.
- **Format:** Shapefile, feature service, CSV via ArcGIS Hub.

### Commercial Use
NJDEP Open Data is published for public access. Federal source data is public domain. Check specific dataset terms.

---

## New York (NY)

### Agency
**NY State Dept. of Environmental Conservation (NYSDEC)** -- Division of Water, Bureau of Water Resource Management.

### Water Withdrawal Permits
- **Program:** Permits and reporting for withdrawals >100,000 GPD.
- **Portal:** https://dec.ny.gov/environmental-protection/water/water-quantity/water-withdrawal-permits-reporting
- **DECinfo Locator:** Interactive map with water withdrawal annual reports in "Permits and Registrations" layer.
- **Access method:** DECinfo Locator map viewer; annual reports viewable online.
- **Format:** Web viewer, PDF reports.
- **Bulk download:** Partial -- data accessible through DECinfo Locator and GIS Clearinghouse.

### Drinking Water Program
- **Portal:** https://water.ny.gov/ -- NYS Water Quality portal.
- **DOH:** NY Dept. of Health administers drinking water program (public water system compliance).
- **Access method:** Web portal for water quality information.

### Wastewater / SPDES
- **Program:** New York uses SPDES (State Pollutant Discharge Elimination System) -- delegated from federal NPDES.
- **Portal:** https://dec.ny.gov/environmental-protection/water/water-quality/spdes-compliance-enforcement
- **Data:** ~1,750 SPDES wastewater treatment facilities + 1,600 industrial stormwater facilities submit DMRs.
- **Access method:** DMR data entered into EPA ECHO; CSO outfall maps on DEC site.

### Groundwater Well Registry
- **NYS GIS Clearinghouse -- Water Wells:**
  - https://data.gis.ny.gov/datasets/nysdec::water-wells
  - Data collected since April 2000 (ECL 15-1525); completion reports added as available.
- **Long Island wells:** Many records posted on DECinfo Locator with PDF completion reports.
- **Access method:** GIS Clearinghouse download; DECinfo Locator viewer.
- **Format:** Shapefile, feature layer via GIS Clearinghouse.
- **Bulk download:** Yes -- downloadable from NYS GIS Clearinghouse.

### GIS / Bulk Data
- **NYS GIS Clearinghouse:** https://data.gis.ny.gov/
- **DECinfo Locator:** Interactive map with multiple environmental data layers.
- **Format:** Shapefile, GDB, feature services.

### Commercial Use
NYS GIS Clearinghouse data is published for public use. Federal source data is public domain.

---

## Pennsylvania (PA)

### Agency
**PA Dept. of Environmental Protection (DEP)** -- Water Use Planning Program.
Well data under **PA Dept. of Conservation and Natural Resources (DCNR)** -- Bureau of Geological Survey.
Also regulated by **Delaware River Basin Commission (DRBC)** and **Susquehanna River Basin Commission (SRBC)** for major basin withdrawals.

### Water Allocation Permits
- **Program:** DEP Water Resource facility type; also DRBC/SRBC docket approvals for basin withdrawals.
- **Portal:** DEP eFACTS system.
- **Info URL:** https://extension.psu.edu/access-and-allocation-of-water-in-pennsylvania
- **Access method:** eFACTS web query; basin commission dockets available separately.
- **Format:** Web query results, PDF permits.
- **Note:** PA water law is complex -- no unified prior-appropriation system; regulated through multiple overlapping authorities (DEP, DRBC, SRBC, Act 220 plans).

### Drinking Water Program
- **PA DWRS:** Drinking Water Reporting System -- public access to sample history, inventory, violation history.
- **PADWIS:** Pennsylvania Drinking Water Information System (internal DEP system, data feeds to federal SDWIS).
- **Portal:** https://www.pa.gov/agencies/dep/data-and-tools/reports/water-reports/
- **Access method:** Web viewer for public queries.

### Wastewater / NPDES
- **Program:** PA is a delegated NPDES state.
- **Portal:** https://www.pa.gov/agencies/dep/programs-and-services/water/clean-water/wastewater-reports/
- **eFACTS:** Reports listing NPDES and WQM permitted facilities, updated daily.
- **eDMR:** Electronic discharge monitoring reports accessible through wastewater reports page.
- **Access method:** Web query, downloadable reports.
- **Bulk download:** Yes -- eFACTS facility reports downloadable.

### Groundwater Well Registry
- **PA Groundwater Information System (PaGWIS):**
  - Hundreds of thousands of water well records + 2,000+ spring records.
  - **PaGEODE viewer:** https://www.pa.gov/agencies/dcnr/conservation/water/groundwater/pa-groundwater-information-system/
  - **ArcGIS Hub:** https://hub.arcgis.com/datasets/DCNR::pagwis-water-wells/about
  - **PASDA:** https://www.pasda.psu.edu/uci/DataSummary.aspx?dataset=289
- **Well Driller Reporting:** Online via PaGWIS Driller web application.
- **Access method:** PaGEODE web query; ArcGIS Hub download; PASDA download.
- **Format:** Shapefile, feature layer, CSV.
- **Bulk download:** Yes -- downloadable from PASDA and ArcGIS Hub.

### GIS / Bulk Data
- **PASDA (PA Spatial Data Access):** https://www.pasda.psu.edu/ -- comprehensive state GIS clearinghouse.
- **Format:** Shapefile, GDB, feature services.

### Commercial Use
PASDA data is published for public use. Federal source data is public domain. Individual dataset metadata may carry specific terms.

---

## Rhode Island (RI)

### Agency
**RI Dept. of Environmental Management (DEM)** -- Office of Water Resources (OWR).
Geological/well data also through **RI Geological Survey (RIGS)** at URI.

### Water Withdrawal Permits
- **Program:** Groundwater Withdrawal Registration Program for large-scale facilities.
- **Portal:** https://dem.ri.gov/owr-portal (OWR Permit Application Portal).
- **Info URL:** https://dem.ri.gov/environmental-protection-bureau/water-resources/permitting/water-quality-certification/water-withdrawals
- **Access method:** Online permit portal (no login for searches); permit applications electronic.
- **Format:** Web portal.

### Drinking Water Program
- **Agency:** RI Dept. of Health (DOH) administers drinking water program; DEM handles source protection.
- **Access method:** DOH maintains public water system compliance data.

### Wastewater / RIPDES
- **Program:** RI Pollutant Discharge Elimination System (RIPDES) -- delegated from federal NPDES.
- **Portal:** https://dem.ri.gov/environmental-protection-bureau/water-resources/permitting/ripdes
- **Access method:** Permit documents on DEM site; DMR data also in EPA ECHO.

### Groundwater Well Registry
- **RI WUNDR (Water Use, Needs and Data Resource):** https://rigs.uri.edu/water/home.html
  - First publicly available, web-accessible water withdrawal and use database for RI.
  - Maintained by RI Geological Survey at URI.
  - Visualize and download statewide water withdrawal and use data.
- **DEM Groundwater Programs:** http://www.dem.ri.gov/programs/water/quality/groundwater/
- **Access method:** WUNDR web viewer with download capability.
- **Format:** Downloadable data from WUNDR interface.
- **Bulk download:** Partial -- WUNDR provides download of withdrawal/use data.

### GIS / Bulk Data
- **OWR Permit Searches:** https://dem.ri.gov/environmental-protection-bureau/water-resources/permitting/permit-searches
- **RIGIS (RI GIS):** https://www.rigis.org/ -- state GIS clearinghouse (separate from DEM).
- **Format:** Shapefile, feature services.

### Commercial Use
RIGIS and WUNDR data published for public use. Federal source data is public domain.

---

## Vermont (VT)

### Agency
**VT Dept. of Environmental Conservation (DEC)** within the Agency of Natural Resources (ANR).

### Water Withdrawal Permits
- **Groundwater:** Permit required for withdrawals >57,600 GPD (non-potable sources -- industrial/commercial).
  - https://dec.vermont.gov/water/groundwater/groundwater-withdrawal-reporting-and-permitting
- **Surface Water:** Act 135 -- Surface Water Withdrawal Registration and Reporting.
  - https://dec.vermont.gov/watershed/rivers/streamflow-protection/act-135-surface-water-withdrawal-registration-and-reporting
- **Application:** Most applications submitted electronically on ANR Online.
- **Access method:** ANR Online portal; permit location info on ANR Atlas.
- **Format:** Web portal, PDF.
- **Bulk download:** No consolidated download identified.

### Drinking Water Program
- **Drinking Water Watch:** Searchable database for general water system information.
  - Access via: https://dec.vermont.gov/drinking-water-and-groundwater-protection/searchable-databases
- **Additional databases:** Water System Operator Information, Public Water System Sample and Sampling Schedule Database.
- **Access method:** Interactive web search tools.

### Wastewater / NPDES
- **Program:** Vermont is a delegated NPDES state.
- **Discharge Permits:** https://dec.vermont.gov/watershed/wastewater/discharge-permits
- **Active NPDES Permits Report:** https://anrweb.vt.gov/DEC/IWIS/ReportViewer2.aspx?Report=WWActiveNPDESPermits&ViewParms=False
- **WWRO Permit Search:** https://anrweb.vt.gov/DEC/WWDocs/Default.aspx
- **Access method:** Web viewer for permit documents and active permit lists.

### Groundwater Well Registry
- **Well Driller Reports Database:** https://anrweb.vt.gov/DEC/WellDrillerReports/Default.aspx
  - Searchable database of well completion reports (private and public wells).
- **ANR Natural Resources Atlas:** https://anrmaps.vermont.gov/websites/anra5/
  - Address-based search for well locations and other environmental data.
- **Interactive Water Use Dashboards:** https://dec.vermont.gov/geological-survey/groundwater/wudr
- **Access method:** Web search tools; ANR Atlas map viewer.
- **Format:** Web query results; dashboard visualizations.
- **Bulk download:** Partial -- dashboards provide data views; well reports searchable but bulk export not clearly available.

### GIS / Bulk Data
- **ANR Atlas:** Interactive GIS -- https://anrmaps.vermont.gov/websites/anra5/
- **Vermont Open Geodata Portal:** https://geodata.vermont.gov/ (VT Center for Geographic Information).
- **Format:** Various GIS formats.

### Commercial Use
Vermont open geodata published for public use. Federal source data is public domain.

---

## Cross-Cutting Notes

### Federal Fallback Portals (all states)
These federal systems aggregate data from all 11 states and serve as a baseline when state portals lack query/download capability:

| System | URL | Coverage |
|--------|-----|----------|
| EPA SDWIS/FED | https://www.epa.gov/ground-water-and-drinking-water/safe-drinking-water-information-system-sdwis-federal-reporting | All public water systems |
| EPA ECHO (ICIS-NPDES) | https://echo.epa.gov/ | All NPDES/SPDES/RIPDES/MEPDES permits |
| USGS NWIS | https://waterdata.usgs.gov/nwis | Groundwater levels, water quality, streamflow |
| USGS National Groundwater Monitoring Network | https://cida.usgs.gov/ngwmn/ | Federated well data from participating states |

### NPDES Delegation Status
- **Delegated states (issue own permits):** CT, DE, ME (MEPDES), MD, MA, NJ (NJPDES), NY (SPDES), PA, RI (RIPDES), VT
- **Not delegated (EPA Region 1 issues permits):** NH

### Best Bulk-Download States (for facility intelligence)
Ranked by ease of obtaining complete, machine-readable facility/permit/well datasets:

1. **NJ** -- DataMiner + NJDEP Open Data ArcGIS Hub; most query-flexible
2. **PA** -- PaGWIS + PASDA; hundreds of thousands of well records downloadable
3. **NH** -- NHDES Geodata Portal ArcGIS Hub; 135k+ wells as feature layers
4. **ME** -- MGS ArcGIS Hub; 50k+ wells downloadable
5. **NY** -- GIS Clearinghouse; water wells + withdrawal data as shapefiles
6. **MA** -- MassGIS; 200k+ well completion reports, public water supply boundaries
7. **CT** -- data.ct.gov open data; well records + CT ECO environmental layers
8. **DE** -- FirstMap ArcGIS Hub; well viewer + DNREC geospatial layers
9. **MD** -- iMap GIS Catalog; partial coverage
10. **VT** -- ANR Atlas + dashboards; searchable but limited bulk export
11. **RI** -- WUNDR + RIGIS; smallest state, partial download

### Commercial Redistribution
No state explicitly prohibits redistribution of its open/public data portals in these searches, but:
- Always check the specific dataset's terms of use / license metadata.
- Federal source data (USGS, EPA) is **public domain** -- no restrictions.
- State-generated data is typically usable with attribution but may carry state-specific open data licenses.
- Well completion reports may contain PII (property owner names/addresses) -- scrub before redistribution.
- Individual water use reports in some states (e.g., ME) are **confidential** by statute.
