# Western US Water Rights, Permits, and Facility Data Portals

Research compiled September 2026. Covers 13 Western US states operating under
prior-appropriation (or hybrid) water rights doctrines. All URLs verified via
web search; availability and formats may change.

## Cross-State Resource: WaDE / WestDAAT

The **Water Data Exchange (WaDE)** program, run by the Western States Water
Council (WSWC), aggregates water rights data from all 18 member states into a
single cloud-based platform.

| Item | Detail |
|------|--------|
| Portal | [WestDAAT](https://westernstateswater.org/wade/westdaat-analytics/) |
| Coverage | 2.5M+ active water rights across 18 western states |
| API | OGC API (key required -- contact WaDE staff) |
| Bulk download | Up to 100,000 water rights per export via WestDAAT UI |
| Code | [github.com/WSWCWaterDataExchange](https://github.com/WSWCWaterDataExchange) |
| Data format | CSV, GeoJSON via API |
| Commercial use | Public data; check individual state source restrictions |

---

## Alaska (AK)

### Water Rights / Allocation

| Item | Detail |
|------|--------|
| Agency | AK Dept. of Natural Resources, Division of Mining, Land & Water |
| Database | [Water Rights Search](https://dnr.alaska.gov/mlw/water/data/) (~24,000 records) |
| Portal | [Alaska Water Use Data System (AKWUDS)](https://dnr.alaska.gov/mlw/water/data/) -- monthly water use reporting + public download |
| Map | [Water Rights Map](https://dnr.alaska.gov/mlw/water/data/) -- active water rights & temporary use authorizations |
| ArcGIS | [Surface Water Rights FeatureServer](https://arcgis.dnr.alaska.gov/arcgis/rest/services/OpenData/Water_SurfaceWaterRight/FeatureServer) |
| Access | Web search, interactive map, ArcGIS REST, bulk download via AKWUDS |
| Format | Shapefile, GeoJSON (ArcGIS), Excel/CSV (AKWUDS) |

### Drinking Water

| Item | Detail |
|------|--------|
| Agency | AK Dept. of Environmental Conservation (DEC) |
| Portal | [Drinking Water Watch](https://dec.alaska.gov/dww/) -- search by PWSID or system name |
| GIS | [SDWIS Drinking Water Facilities](https://gis.data.alaska.gov/maps/ADEC::alaska-dec-sdwis-drinking-water-facilities) |

### Wastewater / NPDES

| Item | Detail |
|------|--------|
| Agency | AK DEC, Division of Water |
| Program | Alaska Pollutant Discharge Elimination System (APDES) -- state-administered, replaces federal NPDES |
| Portal | [APDES Permit Entry](https://dec.alaska.gov/water/wastewater/permit-entry/) |

### Groundwater Wells

| Item | Detail |
|------|--------|
| Agency | AK DNR |
| Access | Well logs available via [Alaska Mapper](https://dnr.alaska.gov/mlw/water/data/) and DNR Open Data ArcGIS portal |
| Format | ArcGIS REST, individual PDFs |
| Bulk download | Limited; ArcGIS feature service supports query/export |

### Commercial Use Rights

Federal public-domain data (USGS NHD/NHDPlus/WBD). State water rights records are public records under Alaska law.

---

## Arizona (AZ)

### Water Rights / Allocation

| Item | Detail |
|------|--------|
| Agency | Arizona Dept. of Water Resources (ADWR) |
| Database | [Constituent Portal](https://www.azwater.gov/adwr-customer-portals) -- apply, review, track permits |
| Well Registry | [Well Registry Search](https://app.azwater.gov/WellRegistry/SearchWellReg.aspx) / [Map](https://azwatermaps.azwater.gov/wellreg/) |
| Open Data | [ADWR Open Data Hub](https://gisdata-azwater.opendata.arcgis.com/) |
| Access | Web search, ArcGIS Hub, bulk download |
| Format | Shapefile, KML, CSV (spreadsheet), GeoJSON |

### Drinking Water

| Item | Detail |
|------|--------|
| Agency | Arizona Dept. of Environmental Quality (ADEQ) |
| Portal | [ADEQ Database Search](https://azdeq.gov/databases) |

### Wastewater / NPDES

| Item | Detail |
|------|--------|
| Agency | ADEQ, Water Quality Division |
| Program | Arizona Pollutant Discharge Elimination System (AZPDES) -- state-authorized since 2002 |
| Portal | [AZPDES Permitting](https://azdeq.gov/SWPPermitting) |

### Groundwater Wells

| Item | Detail |
|------|--------|
| Agency | ADWR |
| Database | [Wells55 Database](https://www.azwater.gov/permitting-wells/wells-data) + [Well Record Search](https://www.azwater.gov/permitting-wells/well-record-search) |
| Bulk download | Yes -- via [ADWR Open Data Hub](https://gisdata-azwater.opendata.arcgis.com/) (Shapefile, KML, CSV) |

### Commercial Use Rights

Public records. ADWR GIS data freely downloadable.

---

## California (CA)

### Water Rights / Allocation

| Item | Detail |
|------|--------|
| Agency | State Water Resources Control Board (SWRCB), Division of Water Rights |
| Database | [CalWATRS](https://www.waterboards.ca.gov/waterrights/water_issues/programs/ewrims/) (replaced legacy eWRIMS) |
| Open Data | [CA Natural Resources Agency Open Data](https://data.cnra.ca.gov/dataset/california-water-rights-list-detail-summary-list) -- Water Rights LIST (Detail Summary) |
| Alt download | [CA Open Data Portal](https://data.ca.gov/dataset/water-rights/) |
| Access | Web search (CalWATRS), CSV bulk download via open data portals |
| Format | CSV, Excel, JSON via CKAN API |

### Drinking Water

| Item | Detail |
|------|--------|
| Agency | SWRCB, Division of Drinking Water (DDW) |
| Portal | [SDWIS Public Water System Search](https://sdwis.waterboards.ca.gov/PDWW/JSP/SysSearch.jsp) |
| Data download | [EDT Library](https://waterboards.ca.gov/drinking_water/certlic/drinkingwater/EDTlibrary.html) -- SDWIS data files (tab-delimited) |
| Open Data | [CNRA Drinking Water dataset](https://data.cnra.ca.gov/dataset/drinking-water-public-water-system-information) |

### Wastewater / NPDES

| Item | Detail |
|------|--------|
| Agency | SWRCB + Regional Water Quality Control Boards |
| Database | [CIWQS](https://www.waterboards.ca.gov/ciwqs/chc_npdes.html) -- California Integrated Water Quality System |
| Access | Web search; regulatory, compliance, enforcement data; permits, inspections, violations |

### Groundwater Wells

| Item | Detail |
|------|--------|
| Agency | Dept. of Water Resources (DWR) |
| Access | Well completion reports via DWR; CASGEM (groundwater elevation monitoring) |
| Bulk download | Via CNRA open data and CIWQS exports |

### Commercial Use Rights

Public data. CNRA open data is CC-compatible. CalWATRS/eWRIMS data is public record.

---

## Colorado (CO)

### Water Rights / Allocation

| Item | Detail |
|------|--------|
| Agency | CO Division of Water Resources (DWR) |
| Database | [HydroBase](https://opencdss.state.co.us/opencdss/hydrobase/) via Colorado Decision Support Systems (CDSS) |
| REST API | [HydroBase REST Web Services](https://dwr.state.co.us/Rest/GET/api/v2/) -- API key available (increases query limits) |
| Bulk export | [HydroBase Bulk Exporter](http://www.dwr.state.co.us/HBGuestExport/HBGuestExport.aspx) -- structures, stations, well permits, water rights by division |
| CDSS tools | [TSTool](https://opencdss.state.co.us/tstool/), [StateDMI](https://opencdss.state.co.us/statedmi/) for programmatic access |
| FTP | Periodic HydroBase images on DWR FTP site |
| GIS | [DWR GIS & Maps](https://dwr.colorado.gov/services/data-information/gis) |
| Format | CSV, JSON (REST), Access DB (HydroBase images), Shapefile (GIS) |

### Drinking Water

| Item | Detail |
|------|--------|
| Agency | CO Dept. of Public Health & Environment (CDPHE) |
| Portal | [Drinking Water Consumer Info](https://cdphe.colorado.gov/dwinfo) |
| Records | CDPHERM WTR search for clean water + drinking water records |

### Wastewater / NPDES

| Item | Detail |
|------|--------|
| Agency | CDPHE, Water Quality Control Division |
| Program | Colorado Discharge Permit System (CDPS) |
| Portal | [Active Permits (Excel download)](https://cdphe.colorado.gov/clean-water-active-permits) |
| Records | [Water Quality Records Center](https://cdphe.colorado.gov/water-quality-records-center-and-requests) |

### Groundwater Wells

| Item | Detail |
|------|--------|
| Agency | CO DWR |
| Database | Well permits in HydroBase |
| Bulk download | Yes -- via HydroBase Bulk Exporter and REST API |

### Commercial Use Rights

Public data. HydroBase and CDSS tools are open-source (OpenCDSS). REST API is free with optional key.

**Colorado is the gold standard** for western water data access: open-source tools, documented REST API, bulk export, and periodic database snapshots.

---

## Hawaii (HI)

### Water Rights / Allocation

| Item | Detail |
|------|--------|
| Agency | Commission on Water Resource Management (CWRM), under DLNR |
| System | Public trust doctrine (not prior appropriation); Water Use Permits required in designated areas |
| Portal | [CWRM](https://dlnr.hawaii.gov/cwrm/) |
| Access | Permit applications (PDF forms); no centralized downloadable database found |

### Drinking Water

| Item | Detail |
|------|--------|
| Agency | Dept. of Health (DOH), Safe Drinking Water Branch |
| Portal | [Safe Drinking Water Branch](https://health.hawaii.gov/sdwb/) |
| E-Permitting | [DOH e-Permitting -- SDWB](https://eha-cloud.doh.hawaii.gov/epermit/Home/993d1338-2ff4-415a-a995-1ede7fa6bf74) |

### Wastewater / NPDES

| Item | Detail |
|------|--------|
| Agency | DOH, Clean Water Branch |
| Portal | [Clean Water Branch](https://health.hawaii.gov/cwb/) |
| NPDES | [General Permits](https://health.hawaii.gov/cwb/general-permits/) |
| E-Permitting | [DOH e-Permitting -- Wastewater](https://eha-cloud.doh.hawaii.gov/epermit/Home/d0ca3c8e-435a-433e-8c71-5734c2bc643b) |

### Groundwater Wells

| Item | Detail |
|------|--------|
| Agency | CWRM + University of Hawaii HIGP |
| Database | [Hawaii State Water Wells](https://www.higp.hawaii.edu/hggrc/projects/hawaii-state-waterwells/) (UH Groundwater & Geothermal Resources Center) |
| Access | Interactive map + downloadable individual well files; tabular list with links |
| Bulk download | Limited; individual well file downloads |

### Commercial Use Rights

Public data where available. Well data hosted by UH. CWRM permit records are public.

**Note:** Hawaii uses a public trust / regulated riparian system, not prior appropriation. Data portals are less mature than mainland western states.

---

## Idaho (ID)

### Water Rights / Allocation

| Item | Detail |
|------|--------|
| Agency | Idaho Dept. of Water Resources (IDWR) |
| Database | [Water Right Adjudication Search](https://research.idwr.idaho.gov/apps/waterrights/wrajsearch/wradjsearch.aspx) |
| Research Portal | [IDWR Research Portal](https://research.idwr.idaho.gov/) -- water rights, applications, points of diversion, streamflow |
| Open Data | [IDWR Open Data Hub](https://data-idwr.hub.arcgis.com/) (ArcGIS Hub) |
| GIS | [Wells MapServer](https://gis.idwr.idaho.gov/hosting/rest/services/Groundwater/Wells/MapServer) (JSON, GeoJSON) |
| Format | Shapefile, GeoJSON, CSV via ArcGIS Hub; JSON via REST services |

### Drinking Water

| Item | Detail |
|------|--------|
| Agency | Idaho Dept. of Environmental Quality (DEQ) |
| Access | DEQ drinking water program; specific SDWIS portal not found in search |

### Wastewater / NPDES

| Item | Detail |
|------|--------|
| Agency | Idaho DEQ |
| Program | Idaho Pollutant Discharge Elimination System (IPDES) |
| Portal | [IPDES E-Permitting](https://apps-deq.idaho.gov/water/IPDES) |

### Groundwater Wells

| Item | Detail |
|------|--------|
| Agency | IDWR |
| Database | [Wells Overview](https://idwr.idaho.gov/wells/) -- well logs with size, depth, geology, water levels |
| GIS | [Wells MapServer](https://gis.idwr.idaho.gov/hosting/rest/services/Groundwater/Wells/MapServer) |
| Bulk download | Yes -- via ArcGIS Hub and REST services |

### Commercial Use Rights

Public data. IDWR Open Data Hub is freely accessible.

---

## Montana (MT)

### Water Rights / Allocation

| Item | Detail |
|------|--------|
| Agency | MT Dept. of Natural Resources & Conservation (DNRC) |
| Database | [DNRC Water Rights Query System (WRQS)](https://gis.dnrc.mt.gov/apps/WRQS/) |
| Access | Web search by water right number; scanned document images |
| Format | Web viewer; scanned PDFs |

### Drinking Water

| Item | Detail |
|------|--------|
| Agency | MT Dept. of Environmental Quality (DEQ) |
| Portal | [MT DEQ Water](https://deq.mt.gov/water/) |

### Wastewater / NPDES

| Item | Detail |
|------|--------|
| Agency | MT DEQ |
| Program | Montana Pollutant Discharge Elimination System (MPDES) |
| Portal | [MPDES Permits](https://deq.mt.gov/water/Programs/mpdes) -- apply/renew via FACTS online system |
| Groundwater | [MGWPCS](https://deq.mt.gov/water/Programs/groundwater) -- Montana Ground Water Pollution Control System |

### Groundwater Wells

| Item | Detail |
|------|--------|
| Agency | Montana Bureau of Mines & Geology (MBMG) |
| Database | [Ground Water Information Center (GWIC)](https://mbmggwic.mtech.edu/) |
| Content | Well completion reports, water levels (60+ years), water quality, hydrographs |
| GIS | [MBMG GIS Data Hub](https://gis-data-hub-mbmg.hub.arcgis.com/pages/water-resources) |
| Bulk download | Yes -- GWIC wells GIS layer via [Montana State Library](https://msl.mt.gov/geoinfo/water_information_system/groundwater/) |
| Format | Shapefile (GIS layer), web query for individual records |

### Commercial Use Rights

Public data. GWIC and WRQS data are publicly accessible. GIS layers downloadable.

---

## Nevada (NV)

### Water Rights / Allocation

| Item | Detail |
|------|--------|
| Agency | Nevada Division of Water Resources (NDWR) |
| Portal | [NDWR Data Page](https://water.nv.gov/index.php/data) |
| ArcGIS | [Points of Diversion MapServer](https://arcgis.water.nv.gov/arcgis/rest/services/NDWR/LWRFS_Points_of_Diversion/MapServer) -- updated daily from permit DB |
| Open Data | NDWR Open Data page for bulk downloads |
| Format | ArcGIS REST (JSON/GeoJSON), downloadable datasets |

### Drinking Water

| Item | Detail |
|------|--------|
| Agency | Nevada Dept. of Environmental Protection (NDEP) |
| Portal | [NDEP Drinking Water search](https://ndep.nv.gov/resources/search/drinking-water/) |

### Wastewater / NPDES

| Item | Detail |
|------|--------|
| Agency | NDEP, Bureau of Water Pollution Control (BWPC) |
| Portal | [NDEP Permitting](https://ndep.nv.gov/water/water-pollution-control/permitting) |
| E-Permitting | Water Pollution Control E-Permitting System for online applications |

### Groundwater Wells

| Item | Detail |
|------|--------|
| Agency | NDWR |
| Database | [Well Driller's Reports](https://water.nv.gov/index.php/data) |
| Bulk download | Yes -- bulk well records available from NDWR Open Data page |

### Commercial Use Rights

Public data. NDWR datasets and ArcGIS services are publicly accessible.

---

## New Mexico (NM)

### Water Rights / Allocation

| Item | Detail |
|------|--------|
| Agency | NM Office of the State Engineer (OSE) |
| Database | [NMWRRS](https://nmwrrs.ose.nm.gov/nmwrrs/index) -- NM Water Rights Reporting System (accesses WATERS database) |
| Search | [Water Rights Lookup](https://www.ose.nm.gov/WRAB/) -- search by owner name, file number, POD location |
| Open Data | [NM Water Data Catalog](https://catalog.newmexicowaterdata.org/dataset/ose-nmwrrs) |
| Access | Web search, document images, downloadable reports |
| Format | Well reports, POD reports, driller license reports (PDF/web); open data downloads |

### Drinking Water

| Item | Detail |
|------|--------|
| Agency | NM Environment Dept. (NMED), Drinking Water Bureau |
| Portal | Drinking Water Watch -- sampling history and test results for all regulated contaminants |

### Wastewater / NPDES

| Item | Detail |
|------|--------|
| Agency | EPA (NM is one of ~4 states without NPDES primacy) |
| State role | NMED assists EPA in reviewing federal NPDES permits |
| Note | NM does **not** issue its own NPDES permits; use [federal ICIS/ECHO](https://echo.epa.gov/) |

### Groundwater Wells

| Item | Detail |
|------|--------|
| Agency | OSE |
| Database | Well reports via NMWRRS |
| Access | Searchable online; downloadable individual well reports |
| Note | Database population is ongoing; coverage varies by region (see Abstracted Areas Map) |

### Commercial Use Rights

Public data. OSE data is public record. NM Water Data Catalog provides open data downloads.

**Note:** NM is unusual among western states in lacking state NPDES authority -- all point-source discharge permits come from EPA Region 6.

---

## Oregon (OR)

### Water Rights / Allocation

| Item | Detail |
|------|--------|
| Agency | Oregon Water Resources Dept. (OWRD) |
| Database | [Water Rights Information System (WRIS)](https://www.oregon.gov/owrd/programs/waterrights/wris/pages/default.aspx) |
| Map | [OWRD Water Rights Mapping Tool](https://hub.oregonexplorer.info/content/owrd-water-rights-mapping-tool) |
| Data Portal | [OWRD Data Access](https://www.oregon.gov/owrd/access_data/pages/data.aspx) |
| Oregon Water Data | [oregonwaterdata.org](https://www.oregonwaterdata.org/) -- water rights by type (surface, ground, storage) |
| Format | Web viewer; GIS layers via Oregon Explorer; specific bulk download options via OWRD data portal |

### Drinking Water

| Item | Detail |
|------|--------|
| Agency | Oregon Health Authority (OHA), Drinking Water Services |
| Portal | [Your Water Oregon](https://yourwater.oregon.gov/) -- includes SDWIS IDs |

### Wastewater / NPDES

| Item | Detail |
|------|--------|
| Agency | Oregon Dept. of Environmental Quality (DEQ) |
| Database | [Wastewater Permits Database](https://www.oregon.gov/deq/wq/wqpermits/pages/wastewater-permits-database.aspx) |
| Tools | [WQ Permitting Resources](https://www.oregon.gov/deq/wq/wqpermits/Pages/Tools-and-Data.aspx) |

### Groundwater Wells

| Item | Detail |
|------|--------|
| Agency | OWRD |
| Database | [Well Log Query](https://apps.wrd.state.or.us/apps/gw/well_log/) -- search by TRS, date, owner |
| Map | [Well Report Mapping Tool](https://apps.wrd.state.or.us/apps/gw/wl_well_report_map/Default.aspx) |
| Bulk download | Contact OWRD for bulk export; individual well reports available online (since 1955) |

### Commercial Use Rights

Public data. OWRD and DEQ data are public records under Oregon law.

---

## Utah (UT)

### Water Rights / Allocation

| Item | Detail |
|------|--------|
| Agency | Utah Division of Water Rights (DWRi) |
| Portal | [waterrights.utah.gov](https://waterrights.utah.gov/) |
| Search | [Water Right Search](https://waterrights.utah.gov/search/) |
| Records | [Water Right Records](https://waterrights.utah.gov/wrinfo/query.asp) |
| Open Data | [Utah Open Water Data](https://dwre-utahdnr.opendata.arcgis.com/) |
| ArcGIS Hub | [Water Right Distribution Network](https://utahdnr.hub.arcgis.com/maps/742b709208934b4a970ec8af34046104) |
| GIS | [DWRi GIS Data](https://waterrights.utah.gov/gisinfo/default.asp) |
| Format | CSV, KML, GeoJSON, Shapefile, GeoTIFF, PNG; API via GeoServices, WMS, WFS |

### Drinking Water

| Item | Detail |
|------|--------|
| Agency | Utah DEQ, Division of Drinking Water (DDW) |
| Portal | [Division of Drinking Water](https://deq.utah.gov/division-drinking-water) -- searchable database |

### Wastewater / NPDES

| Item | Detail |
|------|--------|
| Agency | Utah DEQ, Division of Water Quality |
| Program | Utah Pollutant Discharge Elimination System (UPDES) |
| Portal | [UPDES Current Permits](https://deq.utah.gov/water-quality/current-permits-and-forms-updes-permitting-program) |
| Databases | [Water Quality Databases](https://deq.utah.gov/dwq/wq-databases) |

### Groundwater Wells

| Item | Detail |
|------|--------|
| Agency | DWRi |
| Database | [Well Information](https://waterrights.utah.gov/wellInfo/wellInfo.asp) -- search by location or map |
| Bulk download | Yes -- via Utah Open Water Data (ArcGIS Hub) in multiple formats |

### Commercial Use Rights

Public data. Utah Open Water Data provides free downloads in multiple GIS formats with API access.

---

## Washington (WA)

### Water Rights / Allocation

| Item | Detail |
|------|--------|
| Agency | WA Dept. of Ecology |
| Database | Water Right Tracking System (WRTS) + Geographic Water-right Information System (GWIS) |
| Search | [Water Right Record Search](https://appswr.ecology.wa.gov/waterrighttrackingsystem/WaterRights/WaterRightSearch.aspx) |
| Map | [Water Resources Explorer](https://appswr.ecology.wa.gov/waterrighttrackingsystem/WaterRights/Map/WaterResourcesExplorer.aspx) |
| Access | Web search by location, document number, name |

### Drinking Water

| Item | Detail |
|------|--------|
| Agency | WA Dept. of Health (DOH) |
| Portal | [Water System Data for Download](https://doh.wa.gov/data-statistical-reports/environmental-health/drinking-water-system-data/data-download) |
| Bulk download | Yes -- downloadable files for Group A and Group B public water systems |

### Wastewater / NPDES

| Item | Detail |
|------|--------|
| Agency | WA Dept. of Ecology |
| Database | [PARIS](https://ecology.wa.gov/regulations-permits/guidance-technical-assistance/water-quality-permits-database) -- Permitting and Reporting Information System |
| Content | NPDES + state waste discharge permits, inspections, enforcement, DMRs |
| Access | [Online Tools & Databases](https://ecology.wa.gov/footer-pages/online-tools-publications/online-tools-databases) |

### Groundwater Wells

| Item | Detail |
|------|--------|
| Agency | WA Dept. of Ecology |
| Database | [Wells](https://ecology.wa.gov/water-shorelines/water-supply/wells) -- State Well Report Viewer |
| Access | Search by location, owner, driller; view construction details and production |

### Commercial Use Rights

Public data. DOH provides bulk downloads. Ecology databases are publicly searchable.

---

## Wyoming (WY)

### Water Rights / Allocation

| Item | Detail |
|------|--------|
| Agency | Wyoming State Engineer's Office (SEO) |
| Database | [e-Permit (Water Right Database)](https://seo.wyo.gov/home/e-permit-and-instructions) |
| Content | ~28,000 stream diversions, ~42,000 reservoirs, ~210,000 well records |
| Search | [Find Water Right Results](https://seoweb.wyo.gov/e-Permit/Help/e-Permit/Search/FWRR.htm) |
| GIS | [Geospatial Hub](https://water.geospatialhub.org/) -- SEO well datasets by basin |
| Bulk download | Limited -- e-Permit caps exports at 10,000 records per batch |
| Format | Web viewer; GIS shapefiles via Water Plan / Geospatial Hub |

### Drinking Water

| Item | Detail |
|------|--------|
| Agency | Wyoming DEQ, Water Quality Division |
| Portal | [Water & Wastewater](https://deq.wyoming.gov/water-quality/water-wastewater/) |

### Wastewater / NPDES

| Item | Detail |
|------|--------|
| Agency | Wyoming DEQ |
| Program | Wyoming Pollutant Discharge Elimination System (WYPDES) |
| Portal | [WYPDES Permits](https://deq.wyoming.gov/water-quality/wypdes/) -- searchable, last 5 years downloadable |
| DMRs | [Discharge Monitoring Reports](https://deq.wyoming.gov/water-quality/wypdes/discharge-monitoring-reports/) |

### Groundwater Wells

| Item | Detail |
|------|--------|
| Agency | SEO |
| Database | ~210,000 well permit records in e-Permit |
| GIS | Basin-level well shapefiles via [WY Water Plan](https://waterplan.state.wy.us/) |
| Bulk download | Partial -- 10,000-record cap per export; basin-level GIS downloads available |

### Commercial Use Rights

Public data. SEO and DEQ data are public records. GIS shapefiles freely downloadable from Water Plan.

---

## Summary: Data Access Maturity by State

| State | Water Rights DB | REST API | Bulk Download | Well Registry | State NPDES |
|-------|----------------|----------|---------------|---------------|-------------|
| AK | AKWUDS | ArcGIS REST | Yes (AKWUDS) | ArcGIS | APDES |
| AZ | Constituent Portal | ArcGIS Hub | Yes (Open Data) | Wells55 | AZPDES |
| CA | CalWATRS | CKAN API | Yes (Open Data) | DWR | CIWQS |
| **CO** | **HydroBase** | **REST API (key)** | **Yes (Bulk Exporter)** | **HydroBase** | **CDPS** |
| HI | CWRM (limited) | No | No | HIGP (UH) | DOH CWB |
| ID | WRIS | ArcGIS REST | Yes (Open Data) | IDWR Wells | IPDES |
| MT | WRQS | No | Partial (GIS) | GWIC | MPDES |
| NV | NDWR | ArcGIS REST | Yes (Open Data) | NDWR | NDEP BWPC |
| NM | NMWRRS/WATERS | No | Partial (Open Data) | OSE | **No (EPA)** |
| OR | WRIS | No | Contact OWRD | Well Log Query | DEQ |
| UT | DWRi | GeoServices/WMS/WFS | Yes (Open Data) | DWRi Wells | UPDES |
| WA | WRTS/GWIS | No | Yes (DOH DW) | Well Report Viewer | PARIS |
| WY | e-Permit | No | Partial (10k cap) | SEO e-Permit | WYPDES |

**Top-tier data access (API + bulk + open data):** CO, CA, UT, AZ, ID
**Mid-tier (bulk download, no API):** AK, NV, WA, MT
**Limited (web viewer, partial download):** OR, NM, WY, HI

---

## Federal Baselines (for comparison)

These federal portals cover all states; the state portals above provide richer, more current data:

| System | URL | Content |
|--------|-----|---------|
| EPA SDWIS | [epa.gov/enviro/sdwis-search](https://www.epa.gov/enviro/sdwis-search) | Public water systems nationwide |
| EPA ECHO/ICIS | [echo.epa.gov](https://echo.epa.gov/) | NPDES permits, compliance, enforcement |
| USGS NWIS | [waterdata.usgs.gov](https://waterdata.usgs.gov/) | Streamflow, groundwater levels, water quality |
| EPA Safe Drinking Water | [epa.gov/ground-water-and-drinking-water](https://www.epa.gov/ground-water-and-drinking-water) | Regulations, MCLs, consumer info |
