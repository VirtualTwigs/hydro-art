# Midwest Water Data Portals

Water rights, withdrawal permits, drinking water, wastewater, and groundwater well
data portals for 12 Midwestern US states.  Researched September 2026.

> **Commercial use note.**  USGS/NHD/WBD data is federal public domain.
> State water-rights and well databases are generally public record, but
> redistribution terms vary by state.  Check each portal's terms of use
> before packaging data in a commercial product.

---

## Illinois (IL)

| Category | Details |
|---|---|
| **Water rights agency** | Illinois State Water Survey (ISWS), Prairie Research Institute; Illinois DNR Water Supply |
| **Water withdrawal database** | **Illinois Water Inventory Program (IWIP)** -- tracks all high-capacity wells/intakes (>=70 gpm). Public water supply data available at facility/source level; industrial/irrigation data aggregated to county/watershed level (privacy). Data 1978--2023+. Contact: cwessm3@illinois.edu |
| **Access method** | Request-based for facility-level industrial/irrigation; public supply data via ISWS Water Supply Planning site |
| **URL** | https://water-supply.isws.illinois.edu/resources/water-use-reporting/water-use-data/ |
| **Drinking water portal** | **Drinking Water Watch** -- county map browse or name search; compliance monitoring, violations, PWS contacts. URL: https://water.epa.state.il.us/dww/index.jsp |
| **Wastewater / NPDES** | Illinois EPA NPDES program. **IEPA Document Explorer** for permit docs: https://webapps.illinois.gov/EPA/DocumentExplorer/ ; **DMR Data Search**: http://dataservices.epa.illinois.gov/dmrdata/dmrsearch.aspx |
| **Groundwater well registry** | **ISWS Wells Database** -- 370,000+ records (domestic + high-capacity). **ILWATER** interactive map (ISGS): transcribed well logs, aquifer data. URL: https://isws.illinois.edu/resources/data-maps/well-groundwater-resources/ |
| **Bulk download** | ILWATER map service; ISWS provides data on request; IWIP county/watershed aggregates downloadable |
| **Commercial use** | Public records; industrial/irrigation data privacy-restricted at facility level |

---

## Indiana (IN)

| Category | Details |
|---|---|
| **Water rights agency** | Indiana DNR, Division of Water, Water Rights & Use Section |
| **Water withdrawal database** | **Significant Water Withdrawal Facility (SWWF) Registration** -- facilities capable of >=100,000 gpd must register. ~4,315 active SWWFs, ~7,615 groundwater wells, ~1,261 surface intakes. Interactive map with county selection. |
| **Access method** | Web map viewer with click-to-query; no bulk API documented |
| **URL** | https://www.in.gov/dnr/water/water-availability-use-rights/significant-water-withdrawal-facility-data/ |
| **Drinking water portal** | **Indiana Drinking Water Viewer** (replaced Drinking Water Watch) -- sample results, contacts, schedules. Searchable by PWS name or ID. URL: https://indwv.gecsws.com/ |
| **Wastewater / NPDES** | IDEM Permits Branch issues NPDES permits. NPDES Facilities map from ICIS data. URL: https://www.in.gov/idem/cleanwater/wastewater-permitting/national-pollutant-discharge-elimination-system-npdes/ |
| **Groundwater well registry** | **IDNR Water Well Record Database** -- 400,000+ well records. Free search by township/range/section or via web viewer. Bulk digital download via accessIndiana (fee). URL: https://secure.in.gov/dnr/water/ground-water-wells/water-well-record-database/ |
| **Bulk download** | Well locations available as GIS layer on IndianaMap (ArcGIS). Well records bulk download requires paid accessIndiana subscription. |
| **Commercial use** | Public records; bulk digital download incurs a fee |

---

## Iowa (IA)

| Category | Details |
|---|---|
| **Water rights agency** | Iowa DNR, Water Allocation & Use Program |
| **Water withdrawal database** | **Water Allocation Compliance and Online Permitting (WACOP)** -- permits required for >=25,000 gpd withdrawals; permits valid 10 years. Online permit management. URL: https://programs.iowadnr.gov/wacop/ |
| **Access method** | Web application with login; draft permits published for public comment |
| **URL** | https://www.iowadnr.gov/environmental-protection/water-quality/water-supply-engineering/water-allocation-use |
| **Drinking water portal** | **Iowa Drinking Water Data Portal** -- water quality data for public water supply systems. Via Iowa DNR. URL: https://www.iowadnr.gov/environmental-protection/water-quality/drinking-water |
| **Wastewater / NPDES** | **Wastewater Permit Information Exchange (WWPIE)** -- search NPDES and state operation permits (final, draft, draft-amendment). Email notifications available. URL: https://programs.iowadnr.gov/wwpie/ |
| **Groundwater well registry** | **Private Well Tracking System (PWTS)** -- permits, test registration, abandoned wells, renovation. Map and filter search. URL: https://programs.iowadnr.gov/pwts/ |
| **Bulk download** | PWTS well locations available as GIS layer on Iowa Geospatial Data Clearinghouse (geodata.iowa.gov). NPDES databases downloadable. |
| **Commercial use** | Public records; well data freely available via geospatial clearinghouse |

---

## Kansas (KS)

| Category | Details |
|---|---|
| **Water rights agency** | Kansas Department of Agriculture, Division of Water Resources (KDA-DWR) |
| **Water withdrawal database** | **Water Rights Information System (WRIS)** -- Oracle RDBMS with 70+ tables: points of diversion, place of use, authorized quantities, historic reported usage. Public access via **Water Information Management and Analysis System (WIMAS)** (joint KDA-DWR / Kansas Geological Survey). Dataset refreshed weekly. |
| **Access method** | WIMAS web query, analysis, and mapping tool |
| **URL** | https://geohydro.kgs.ku.edu/geohydro/wimas/ |
| **Drinking water portal** | **Drinking Water Watch (DWW)** -- KDHE Bureau of Water, Public Water Supply Section. 1,000+ PWS systems. URL: https://dww.kdhe.ks.gov/DWW/KSindex.jsp |
| **Wastewater / NPDES** | KDHE Bureau of Water administers NPDES. URL: https://www.kdhe.ks.gov/754/Pollution-Control-Wastewater-Programs |
| **Groundwater well registry** | **Water Well Completion Records (WWC5)** -- KGS database; ~298,000 scanned well reports. Search by county, legal description, or interactive mapper. URL: https://www.kgs.ku.edu/Magellan/WaterWell/index.html |
| **Bulk download** | WIMAS data queryable in bulk; WWC5 records searchable but bulk export not prominently offered; KS Water Hub aggregates data sources: https://www.waterhub.ks.gov/education/water-data-sources |
| **Commercial use** | Public records; WIMAS and WWC5 freely queryable |

---

## Michigan (MI)

| Category | Details |
|---|---|
| **Water rights agency** | Michigan EGLE (Environment, Great Lakes, and Energy), Water Use Program |
| **Water withdrawal database** | **Part 327 Water Withdrawal Permits** -- large quantity withdrawals (>=100,000 gpd) must register. Permit applications via **MiEnviro** portal ($2,000 fee). Annual water use reporting required. |
| **Access method** | MiEnviro web portal (login required for filing); Water Use Reporting System |
| **URL** | https://www.michigan.gov/egle/about/organization/geologic-resources-management/water-use |
| **Drinking water portal** | **MiEHDWIS** (Michigan Environmental Health and Drinking Water Information System). PWS data via EGLE. |
| **Wastewater / NPDES** | **MiEnviro** portal handles NPDES permitting and compliance (formerly MiWaters). URL: https://www.michigan.gov/egle/about/organization/water-resources/npdes |
| **Groundwater well registry** | **Wellogic** -- 1,000,000+ well records; public search (no account needed). ~12,000--14,000 new records/year. **Water Well Viewer** interactive map. URL: https://www.michigan.gov/egle/maps-data/wellogic |
| **Bulk download** | Wellogic data downloadable by region from Michigan GIS Open Data Portal (ArcGIS). URL: https://gis-michigan.opendata.arcgis.com/datasets/egle::michigan-wellogic-wells/ |
| **Commercial use** | Public records; Wellogic data freely downloadable as open data |

---

## Minnesota (MN)

| Category | Details |
|---|---|
| **Water rights agency** | Minnesota DNR, Water Appropriation Permit Program |
| **Water withdrawal database** | **MPARS** (Minnesota Permitting and Reporting System) -- online permit applications, change requests, water use reporting. Permit required for >=10,000 gpd or >=1M gal/year. URL: https://www.dnr.state.mn.us/mpars/index.html |
| **Access method** | Web application with login; permit index report publicly accessible |
| **URL** | https://www.dnr.state.mn.us/waters/watermgmt_section/appropriations/wateruse.html |
| **Drinking water portal** | **Minnesota Dept. of Health (MDH)** -- regulates ~10,000 PWS. Drinking Water Quality data via MN Public Health Data Access. URL: https://data.web.health.state.mn.us/web/mndata/drinkingwater |
| **Wastewater / NPDES** | **Minnesota Pollution Control Agency (MPCA)** issues NPDES/SDS permits. URL: https://www.pca.state.mn.us/business-with-us/wastewater-permits |
| **Groundwater well registry** | **County Well Index (CWI)** -- 599,000+ wells (as of 06/2025). Joint MGS/MDH database. Online search: https://mnwellindex.web.health.state.mn.us/mwi/ . Offline: shapefiles, Access DB, cwi4VIEW app (updated quarterly). |
| **Bulk download** | CWI shapefiles and Access DB free from MGS FTP. Note: open-access versions exclude public water supply wells; full dataset via MDH request. GIS data: https://gisdata.mn.gov/dataset/water-well-information-non-pws |
| **Commercial use** | Public records; CWI shapefiles freely downloadable; PWS well data requires MDH contact |

---

## Missouri (MO)

| Category | Details |
|---|---|
| **Water rights agency** | Missouri DNR, Missouri Geological Survey, Water Resources Center. **Note:** Missouri uses riparian rights; no water appropriation permit system. |
| **Water withdrawal database** | **Major Water Users** program -- registration (not permitting) required for capacity >=70 gpm. No fees, no fines, no metering -- only annual volume reporting. Each user gets an 8-digit ID. URL: https://dnr.mo.gov/water/business-industry-other-entities/reporting/major-water-users |
| **Access method** | Annual reporting via Major Water Use Information System |
| **URL** | https://dnr.mo.gov/water/data-e-services |
| **Drinking water portal** | **Drinking Water Viewer** -- 2,700+ PWS; contaminant monitoring, permits, operator certification. URL: https://dnr.mo.gov/water/data-e-services/drinking-water-viewer |
| **Wastewater / NPDES** | Missouri DNR issues NPDES operating permits. **Permit Search** for general and site-specific water pollution permits. URL: https://dnr.mo.gov/water/business-industry-other-entities/permits-certifications/issued/site-specific-wastewater |
| **Groundwater well registry** | **WIMS 2.0** (Well Information Management System) -- well construction, geology, water level data (1987--present). URL: https://dnr.mo.gov/water/business-industry-other-entities/reporting/well-information-management-system-wims . Well cuttings GIS layer: https://gis-modnr.opendata.arcgis.com/datasets/modnr::well-cuttings/ |
| **Bulk download** | Well data available on data.mo.gov (State of Missouri Data Portal) and MoDNR ArcGIS Open Data. WIMS search at www.dnr.mo.gov/mowells/ |
| **Commercial use** | Public records; well data on open data portals; no permit fees or restrictions on water use data |

---

## Nebraska (NE)

| Category | Details |
|---|---|
| **Water rights agency** | Nebraska Dept. of Water, Energy, and Environment (DWEE, formerly DNR + NDEE) |
| **Water withdrawal database** | **Surface Water Permits** -- appropriation permits for irrigation, hydropower, municipal, industrial, storage. Searchable by owner, legal description, source, or map. **Natural Resources Districts (NRDs)** manage groundwater allocations locally. |
| **Access method** | Web search and map viewer |
| **URL** | https://dwee.nebraska.gov/surface-water |
| **Drinking water portal** | **Drinking Water Watch** -- 1,300+ PWS; sample schedules/results, violations, enforcement, treatment, population served. Searchable by name or county. URL: https://dwee.nebraska.gov/news-events/press-releases/all-about-dwee-drinking-water-watch |
| **Wastewater / NPDES** | DWEE NPDES Program. Permits tracked in ECM/IIS systems. URL: https://dwee.nebraska.gov/surface-water/water-quality-permitting/national-pollutant-discharge-elimination-systems-npdes-program |
| **Groundwater well registry** | **DWEE Groundwater Well Registration** -- well purpose, status, location, depth, water level, geology, construction. All wells registered after 1969 (except PWS). URL: https://nednr.nebraska.gov/dynamic/Wells/Wells |
| **Bulk download** | Well data searchable and downloadable via web interface. Surface water permit data searchable with map. |
| **Commercial use** | Public records; well registration data freely accessible |

---

## North Dakota (ND)

| Category | Details |
|---|---|
| **Water rights agency** | North Dakota Dept. of Water Resources (DWR, formerly State Water Commission), Water Appropriation Division |
| **Water withdrawal database** | **Water Permits** -- conditional and perfected permits. Non-domestic use >12.5 acre-ft/year requires a permit. Temporary permits (<12 months) available. Searchable online. URL: https://www.swc.nd.gov/reg_approp/waterpermits/ |
| **Access method** | Web search; GIS MapServices |
| **URL** | https://www.swc.nd.gov/info_edu/map_data_resources/ |
| **Drinking water portal** | **ND DEQ Drinking Water Program** -- PWS monitoring, operator certification, inspections, technical assistance. URL: https://deq.nd.gov/mf/DWP/ |
| **Wastewater / NPDES** | **NDPDES Permits Program** (ND DEQ) -- municipal/industrial, stormwater, pretreatment, CAFO, septic. URL: https://deq.nd.gov/WQ/2_NDPDES_Permits/ |
| **Groundwater well registry** | **DWR MapServices** -- well drillers logs, water wells, water chemistry, water levels. Drillers' reports required within 30 days of completion/abandonment. URL: https://www.swc.nd.gov/info_edu/map_data_resources/mapservices.html |
| **Bulk download** | GIS data via ND GIS Hub Data Portal (State Water Commission group). URL: https://gishubdata.nd.gov/group/state-water-commission |
| **Commercial use** | Public records; GIS data available on state open data portal |

---

## Ohio (OH)

| Category | Details |
|---|---|
| **Water rights agency** | Ohio DNR, Division of Water Resources (water withdrawal registration); Ohio EPA (drinking/ground waters) |
| **Water withdrawal database** | **Water Withdrawal Facilities Registration** -- facilities with capacity >=100,000 gpd must register (not a permit). Annual withdrawal reporting required. **Water Withdrawal Atlas** available. URL: https://ohiodnr.gov/discover-and-learn/safety-conservation/about-odnr/water-resources/water-inventory-planning/water-withdrawal-information |
| **Access method** | Online registration and reporting system |
| **URL** | https://ohiodnr.gov/discover-and-learn/safety-conservation/about-odnr/water-resources/water-inventory-planning/withdrawal-reporting-facility-registration/withdrawal-reporting-facility-registration |
| **Drinking water portal** | **Drinking Water Viewer** (replaced Drinking Water Watch) -- PWS info, sample results, violations, enforcement, site visits. URL: https://ohdwv.gecsws.com/ |
| **Wastewater / NPDES** | Ohio EPA, Division of Surface Water. **STREAMS** system (Surface Water Tracking, Reporting, and Electronic Application Management System) for NPDES permits. **eDMR** for electronic discharge monitoring. All via **eBusiness Center**. URL: https://ebiz.epa.ohio.gov/ |
| **Groundwater well registry** | **Ohio Water Well Database** -- well logs and well sealing records. URL: https://waterwells.ohiodnr.gov/search |
| **Bulk download** | eBusiness Center for permit data; well database searchable online; ODNR provides GIS data |
| **Commercial use** | Public records; registration data (not permits) with no restrictions on water use |

---

## South Dakota (SD)

| Category | Details |
|---|---|
| **Water rights agency** | South Dakota DANR (Dept. of Agriculture & Natural Resources), Office of Water, Water Rights Program |
| **Water withdrawal database** | **Water Rights Database** -- prior appropriation system. Permit required for all non-domestic use (domestic exemption up to 25,920 gpd or 25 gpm). Issued by Water Management Board. Searchable by multiple criteria. URL: https://danr.sd.gov/OfficeOfWater/WaterRights/Databases/WaterRights.aspx |
| **Access method** | Web search form |
| **URL** | https://danr.sd.gov/OfficeOfWater/WaterRights/default.aspx |
| **Drinking water portal** | **SD Drinking Water Program** -- ~645 PWS. Searchable map with links to drinking water reports per system. URL: https://danr.sd.gov/OfficeOfWater/DrinkingWater/default.aspx |
| **Wastewater / NPDES** | **Surface Water Discharge Permits (NPDES)** -- facility map with permit search. Full permit docs via EPA ECHO. URL: https://danr.sd.gov/OfficeOfWater/SurfaceWaterQuality/swdpermitting/wwDBSearch.aspx |
| **Groundwater well registry** | **Water Well Completion Reports** -- well logs since 1975 (some older). Search by city, county, category, address, operator, legal description. URL: https://danr.sd.gov/OfficeOfWater/WaterRights/Databases/WellCompletionReports.aspx . Legacy app: https://apps.sd.gov/nr68welllogs/ |
| **Bulk download** | DANR Data & Mapping page aggregates datasets. URL: https://danr.sd.gov/Press/DataAndMapping.aspx |
| **Commercial use** | Public records; water rights and well completion data freely searchable |

---

## Wisconsin (WI)

| Category | Details |
|---|---|
| **Water rights agency** | Wisconsin DNR, Water Use Program |
| **Water withdrawal database** | **High Capacity Well Approval** -- wells/systems >=100,000 gpd (70 gpm) require approval ($500 fee). Interactive map of approved wells, pending applications, and withdrawal volumes. Annual reporting required. URL: https://dnr.wisconsin.gov/topic/WaterUse |
| **Access method** | Interactive map viewer; searchable applications; advanced GIS requests via email to Water Use Program |
| **URL** | https://dnr.wisconsin.gov/topic/WaterUse/data.html |
| **Drinking water portal** | **Drinking Water System (DWS) Portal** -- query and download PWS data: monitoring requirements, sample results, violations, inspections. Updated nightly. URL: https://apps.dnr.wi.gov/dwsportalpub |
| **Wastewater / NPDES** | **WPDES** (Wisconsin Pollutant Discharge Elimination System) -- state equivalent of NPDES. Individual and general permits (5-year term). Permit holder lists and public notices online. URL: https://dnr.wisconsin.gov/topic/Wastewater/PermitLists.html |
| **Groundwater well registry** | **Well Construction Information System** -- all WCRs (well construction reports): geology, construction, depth, water level, yield. Free search by WUWN, township/range/section, or other criteria. URL: https://apps.dnr.wi.gov/wellconstructionpub/#!/PublicSearch/Index |
| **Bulk download** | **Wisconsin Well Inventory** on DNR Open Data Portal (ArcGIS): https://data-wi-dnr.opendata.arcgis.com/datasets/wi-dnr::wisconsin-well-inventory/ . High capacity well data available on request. |
| **Commercial use** | Public records; well inventory and DWS data freely downloadable via open data portal |

---

## Cross-State Summary

### Water Rights Doctrine

| Doctrine | States |
|---|---|
| **Prior appropriation** | KS, NE, ND, SD |
| **Regulated riparian / hybrid** | IA, IN, MI, MN, WI |
| **Riparian (registration only)** | IL, MO, OH |

### Best Bulk-Download Portals

| State | Portal | Format |
|---|---|---|
| IA | Iowa Geospatial Data Clearinghouse | Shapefile, GeoJSON |
| KS | WIMAS + KGS WWC5 | Web query, scanned logs |
| MI | Michigan GIS Open Data (Wellogic) | Shapefile, GeoJSON, ArcGIS REST |
| MN | MGS FTP (CWI) + MnGeo | Shapefile, Access DB |
| MO | data.mo.gov + MoDNR ArcGIS | CSV, Shapefile |
| ND | ND GIS Hub Data Portal | Shapefile, ArcGIS REST |
| OH | ODNR + Ohio EPA eBusiness | Web query, eDWR/eDMR |
| WI | WI DNR Open Data Portal | Shapefile, GeoJSON, ArcGIS REST |
| IL | ILWATER (ISGS) | Map service, request-based |
| IN | IndianaMap (ArcGIS) | Shapefile (fee for bulk well records) |
| NE | DWEE well search | Web query, downloadable |
| SD | DANR Data & Mapping | Web query |

### Threshold for Registration/Permit

| State | Threshold | Type |
|---|---|---|
| IL | 70 gpm | Reporting |
| IN | 100,000 gpd | Registration |
| IA | 25,000 gpd | Permit |
| KS | Any beneficial use | Appropriation permit |
| MI | 100,000 gpd | Registration + permit |
| MN | 10,000 gpd or 1M gal/yr | Appropriation permit |
| MO | 70 gpm (capacity) | Reporting only |
| NE | Any surface diversion; groundwater via NRDs | Appropriation permit |
| ND | >12.5 acre-ft/yr (non-domestic) | Appropriation permit |
| OH | 100,000 gpd | Registration (not a permit) |
| SD | All non-domestic (>25,920 gpd domestic) | Appropriation permit |
| WI | 100,000 gpd | Approval |
