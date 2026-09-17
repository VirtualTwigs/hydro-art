# Water-Facility and Data-Center Intelligence

## Executive assessment

The planned database is feasible and can become a strong, differentiated input to
Hydro-Art images and reports. Its value will come less from accumulating the
largest possible list of points and more from being able to state, for every
displayed facility, **what the place is, what its relationship to water is, and
what evidence supports that statement**.

The core recommendation is to replace a single facility-centric model with three
linked graphs:

```text
Place graph                 Water-relationship graph        Evidence graph
facility / campus ────────< permit / measurement >──────── source record
building / outfall          served_by / discharges_to        source snapshot
service area                withdrawal / delivered / reuse  document/page/row
```

This structure prevents the most material error in this domain: turning a nearby
utility, a discharge permit, a service-area overlap, or a data-center candidate
into a claim of site-level water consumption. It also creates a useful product
ladder: a customer can request neutral infrastructure context on an image, while
a report can show only the smaller set of evidence-backed water facts.

The national federal sources are sufficient for a broad public infrastructure
layer and regulatory identity. They are not sufficient for a nationwide,
facility-level database of withdrawals or data-center consumption. That gap is
structural: allocation and withdrawal records are administered by states, while
large data centers often receive water from a public utility rather than directly
withdrawing it. The rollout should therefore prioritize source rights, record
provenance, and a small number of high-quality state adapters over national
coverage claims.

## What the public data can establish

| Question | Best available evidence | What it can establish | What it cannot establish |
| --- | --- | --- | --- |
| Where is a regulated facility? | EPA FRS | Identity, program IDs, address/coordinate, NAICS/SIC and linked program records | Current operations, water quantity, or a precise site boundary in every case |
| Who supplies public drinking water? | SDWIS plus EPA service areas | A public water system and the documented/modeled area it serves | That a mapped building is a customer or its volume of use |
| Where is wastewater discharged? | ICIS-NPDES, outfalls, DMR | Permit/outfall location, discharge monitoring and permit limits | Facility intake, withdrawal, or net consumption |
| What treatment capacity exists? | CWNS and sewersheds | POTW flow/treatment/reuse attributes and service geography | A real-time treatment load or a named industrial customer |
| Where are dams/reservoirs? | USACE NID | Qualifying dam identity, location, purpose, owner and structural attributes | A complete inventory of every small structure or operational releases |
| What is regional water use/availability? | USGS water-use and NWAA Data Companion | County/HUC/state context and modeled water-availability data | Individual facility use or a legal allocation decision |
| Does a data center use water? | Site-specific utility, withdrawal, permit, or owner evidence | Only the fact and quantity directly supported by that record | A general conclusion from sector, name, size, or location |

EPA’s FRS state files are a sensible identity spine because they include facility
name/address, coordinates, program associations, and SIC/NAICS fields.^1 But FRS
and ECHO are integration systems: names, mailing/physical addresses, and program
records can differ across sources. EPA also explicitly publishes state-specific
data-quality alerts, and notes that mapped points can be approximate when a source
does not supply a location.^2 A provenance-first system should surface these
conditions, rather than hiding them behind a single canonical pin.

The strongest federal infrastructure additions are underused in the first plan.
EPA’s national community-water-system service areas combine published state
boundaries with modeled coverage where state data is missing or unverifiable.^3
EPA’s sewershed dataset similarly covers nearly 17,000 publicly owned treatment
works, but includes modeled boundaries.^4 Both are valuable geographic context;
neither proves a particular facility is served by that utility. USACE’s National
Inventory of Dams offers a public API and GIS service for a nationally consistent
dam layer.^5

For wastewater, add the DMR layer as a distinct *discharge evidence* product.
ICIS-NPDES DMR data reports permit conditions, monitored pollutant values, and
whether reported amounts exceeded limits; it is available by fiscal year from
2009.^6 EPA’s Loading Tool also derives annual/monthly pollutant loads from DMR
data and permit limits.^7 This enables a report to say “documented discharge” with
period, parameter, outfall, and provenance. It must not be used as a proxy for
water consumed at the facility.

## Data-center conclusion: discovery is easy; proof is not

NAICS 518210 is a useful discovery seed, not a data-center registry. A site can be
omitted, coded to another business activity, represented at a parent address, or
be present in FRS because of an unrelated environmental program. Owner directories,
local planning records, and public permits are complementary candidate sources,
but any of them may describe a planned rather than operational facility.

The database should store a data-center lifecycle separately from water evidence:

```text
candidate → announced → permitted → under_construction → operating → closed
                         │
                         └── water relevance is independently: unknown /
                             permitted_or_committed / confirmed
```

This avoids two common errors: treating a construction/wetland permit as an
operating water-use record, and treating an operating data center as confirmed to
use a particular water source. Virginia’s public material on Google’s proposed
Project Raspberry illustrates the distinction: it documents a data-center campus
and a Virginia Water Protection application for impacts to streams/wetlands, but
does not by itself demonstrate facility water consumption.^8

Water Usage Effectiveness (WUE) should be stored only as a performance metric with
its reporting boundary. DOE defines WUE as annual site water divided by IT energy
and explains that cooling-tower consumption is driven by heat load and cooling
system efficiency.^9 WUE without site energy does not yield an annual water volume;
even a site-level annual number can obscure seasonal peaks, source quality, and
whether water is potable, reclaimed, or self-supplied.

## Recommended facility taxonomy

Use two axes rather than one long list of types.

### 1. Physical role

```text
water_supply:       intake, well, treatment plant, storage, distribution asset
wastewater:         collection, pump station, treatment plant, outfall, reuse plant
water_control:      dam, reservoir, diversion, flood-control structure
regulated_user:     industrial facility, thermoelectric plant, mine, campus
digital_load:       data-center campus, data-center building, planned data center
monitoring_context: streamgage, groundwater monitor, quality-monitoring station
```

### 2. Water relationship

```text
withdraws | receives_delivered_water | uses_reclaimed_water | discharges |
operates_supply | operates_treatment | lies_within_service_area | unknown
```

The taxonomy improves both collection and customer choice. A customer interested
in a watershed image might request `water_control + wastewater` context; a customer
investigating digital infrastructure might request `digital_load` sites with the
separate water-relevance status visible. It also prevents a utility provider from
being displayed as if it were a water consumer.

## Source strategy and pilot recommendation

### Source scorecard

Score every source before it enters production. A source must pass all hard gates:
public-display rights are clear; a stable record key exists; scope and refresh are
known; the source can be archived or re-fetched; and location precision is known.

| Dimension | Weight | Pass condition |
| --- | ---: | --- |
| Legal/display rights | hard gate | License or terms permit the intended storage and customer display |
| Water-fact specificity | 25% | Contains a permit, source, quantity, or verifiable relationship—not only a point |
| Stable identifier and provenance | 20% | Record/document key, date, publisher, and retrievable locator |
| Geographic precision | 15% | Precision and method disclosed; location is appropriate to intended display scale |
| Refresh/reproducibility | 15% | Bulk/API/export or a repeatable documented manual process |
| Coverage and completeness | 15% | Known jurisdiction/program coverage and explicit exclusions |
| Matchability | 10% | Owner/address/permit/Federal IDs enable reviewable linkage |

Do not award a “high confidence” facility label based solely on an authoritative
publisher. Confidence is claim-specific: a source can establish a precise outfall
but have no evidence of intake water, or establish a permit authorization but not
an observed use.

### Pilot-state decision

**Texas is the strongest first pilot.** TCEQ publishes active and inactive surface
water-rights files containing holder, basin, and authorized amount, along with GIS
diversion points. It also publishes self-reported water-use data for right holders
in non-watermaster areas.^10 The Water Rights Viewer exposes permit documents,
ownership, and recent use data.^11 This supports a transparent distinction among
authorized, reported, and missing volumes. Its limitations are material: it is
surface-water rights centered, reporting coverage is not statewide-equivalent, and
the right holder may not be the consuming facility.

**Virginia is the strongest second pilot.** DEQ publishes queryable water-protection
and outfall GIS layers, some refreshed daily, and its withdrawal program provides
clear thresholds and program framing.^12 Virginia is also valuable for the
data-center lifecycle because public project/permitting pages can evidence a
proposed campus without prematurely claiming water use. Treat VWP impact records,
outfalls, and withdrawals as separate permit classes.

**Arizona is valuable but should be a controlled third pilot, not an automatic
public-display launch.** ADWR offers well, water-right, groundwater-site, and
assured-water-supply resources; its well registry can expose owner, associated
right, and pumping data.^13 However, ADWR says registry data is supplied by owners
and drillers and is not independently verified; its public data disclaimer also
requests that recipients not make the data available for re-use.^14 That makes
Arizona excellent for a source-rights and review workflow, but the project should
obtain a documented use decision before redistributing point-level results to
customers.

Do not select a third pilot only by data-center market size. Select it after a
short source-rights audit. A state with a smaller data-center concentration and a
clean bulk permit export can produce a safer, faster end-to-end validation than a
high-profile state whose data is view-only or restricted.

## Architecture improvements

### Preserve time twice

Every mutable fact needs both `valid_time` (when it describes) and `system_time`
(when the database obtained/changed it). For a permit, retain application, issue,
effective, expiry, and retrieval dates. For a measurement, retain measurement
period and publication/retrieval date. This permits an image/report to be
reproduced from the exact snapshot the customer approved.

### Add a claim table, not only evidence links

`facility_evidence` describes a document. Add `water_claim` as the reviewed
assertion extracted from it:

```text
water_claim(
  subject_facility_id, predicate, value, unit, measure_type, quantity_status,
  valid_from, valid_to, confidence, display_eligibility, evidence_id,
  reviewer_decision, reviewed_at
)
```

One document can support several claims, and one claim can cite several documents.
This improves auditability and prevents a UI from presenting an entire permit as
support for a claim the permit does not actually make.

### Use display eligibility as a first-class control

Separate analytic availability from customer-display eligibility:

```text
internal_only | review_required | publishable_precise | publishable_generalized | excluded
```

The public renderer should query only a pre-approved view. For generalized points,
display an area, watershed label, or grid cell rather than an exact point. This
protects restricted data, reduces false precision, and gives the reviewer a
practical control beyond an all-or-nothing visibility flag.

### Formalize facility resolution as an event

Persist every candidate match with input record IDs, component scores, versioned
algorithm, reviewer, and outcome. Never overwrite a prior decision. EPA itself
notes that facility names and addresses can differ across its data systems; manual
review must therefore be a durable operation, not a spreadsheet side effect.^15

### Make source quality queryable

Ingest EPA ECHO’s known data problems and source-specific caveats as a small
`data_alert` table keyed by state, program, time, and impact. EPA publishes such
alerts because state-to-federal data transfer can affect completeness, timeliness,
and accuracy.^16 A report can then show “Federal record; state verification
recommended” instead of incorrectly presenting a compliance status as settled.

### Separate live context from deliverable evidence

USGS data APIs can supply current streamflow, monitoring-location, and historical
daily values; the National Water Availability Assessment Data Companion provides
national modeled data at HUC12 scale.^17 These are useful for *internal context*
and time-sensitive reports. Snapshot them for delivery; do not let a later API
refresh change a customer’s already-approved report. The Data Companion explicitly
returns HUC12-scale values even when queried by county, so its granularity must be
shown in report language.^18

## Product recommendations for customer requests

### Offer three products, not a generic “add facilities” toggle

| Customer option | Output | Eligibility rule |
| --- | --- | --- |
| **Water infrastructure context** | Neutral icons/labels for selected public facility classes | Publishable or generalized public records; no consumption claims |
| **Named-facility research note** | A short report appendix with source links, status, and exclusions | Manual review and claim-level provenance required |
| **Water evidence overlay** | Map/report annotations for confirmed permits, relationships, or quantities | Reviewed `water_claim` records only; measure/status/date shown |

This makes the customer’s intent explicit. An art buyer may want visual context;
an institutional customer may require evidence. The second use case needs a
different review SLA and pricing, not merely a different checkbox.

### Design the request form around evidence, not facility names

Ask for geography, facility classes, whether named facilities are required, and
desired treatment (`context` or `evidence-backed`). Return a preview with:

- selected count, excluded count, and reasons;
- source snapshot date and geographic accuracy class;
- labels such as “public water provider,” “permitted discharge,” or “data-center
  candidate”—never a generic “water user”; and
- a choice to approve the reviewed set or remove facilities.

For reports, attach the request/result manifest and cite every facility-level
claim. For images, keep the legend neutral and use a downloadable provenance card
instead of attempting dense citations inside the artwork.

### Add a review policy before exposing data centers

Data-center imagery can imply environmental impact even when the evidence supports
only a location. Require manual review for every named data-center request until
the source catalogue has established display rights, a lifecycle state, and
water-relevance evidence. Use “data-center candidate” for discovery records and
“confirmed water relationship” only for reviewed claims. Do not rank facilities as
water-intensive unless measured/reported site quantities with comparable periods
and source boundaries exist.

## Prioritized improvement plan

1. **Add `water_claim`, bitemporal fields, and display eligibility to #112.** This
   is the highest-leverage change because it protects every later image, report,
   and analysis from overclaiming.
2. **Make DMR discharge and public service-area layers explicit baseline products
   in #113.** They add rich, source-backed visible context while retaining honest
   semantics.
3. **Adopt the source scorecard and source-rights gate before the third pilot.**
   Texas and Virginia can validate the pipeline; Arizona demonstrates why source
   access does not automatically permit customer redistribution.
4. **Build the customer experience as three request types with a reviewed preview,
   not a free-text facility search.** This contains operational cost and makes
   deliverables understandable.
5. **Add a data-alert feed and claim-level caveat rendering.** A visible caveat is
   a product strength when the underlying public record is incomplete or disputed.
6. **Keep regional risk contextual and separately versioned.** Combine facilities
   with USGS HUC12 context or EPA water-quality assessments only in reports, where
   scale, vintage, and inference can be shown. Do not turn proximity into an
   environmental-harm score.

## Sources

[^1]: U.S. Environmental Protection Agency. [“EPA FRS Facilities State Single File CSV Download.”](https://www.epa.gov/frs/epa-frs-facilities-state-single-file-csv-download) Updated May 12, 2026.
[^2]: U.S. Environmental Protection Agency. [“About the Data.”](https://echo.epa.gov/resources/echo-data/about-the-data) Accessed September 13, 2026; [“Website Known Issues.”](https://echo.epa.gov/resources/general-info/website-known-issues) Accessed September 13, 2026.
[^3]: U.S. Environmental Protection Agency. [“Public Water System Service Areas.”](https://www.epa.gov/ground-water-and-drinking-water/public-water-system-service-areas) Accessed September 13, 2026.
[^4]: U.S. Environmental Protection Agency. [“Sewersheds.”](https://www.epa.gov/cwns/sewersheds) Accessed September 13, 2026.
[^5]: U.S. Army Corps of Engineers. [“National Inventory of Dams.”](https://nid.sec.usace.army.mil/nid/) Accessed September 13, 2026; [“National Inventory of Dams API.”](https://nid.sec.usace.army.mil/api/developer) Accessed September 13, 2026.
[^6]: U.S. Environmental Protection Agency. [“ICIS-NPDES DMR Summary and Data Element Dictionary.”](https://echo.epa.gov/tools/data-downloads/icis-npdes-dmr-summary) Accessed September 13, 2026.
[^7]: U.S. Environmental Protection Agency. [“Water Pollutant Loading Tool Modernization.”](https://echo.epa.gov/resources/general-info/loading-tool-modernization) Updated June 2, 2021; [“Technical Background and Methodology.”](https://echo.epa.gov/trends/loading-tool/resources/technical-background-methodology) Accessed September 13, 2026.
[^8]: Virginia Department of Environmental Quality. [“Project Raspberry.”](https://www.deq.virginia.gov/news-info/shortcuts/topics-of-interest/google-s-project-raspberry) Accessed September 13, 2026.
[^9]: U.S. Department of Energy, Federal Energy Management Program. [“Cooling Water Efficiency Opportunities for Federal Data Centers.”](https://www.energy.gov/cmei/femp/cooling-water-efficiency-opportunities-federal-data-centers) Accessed September 13, 2026.
[^10]: Texas Commission on Environmental Quality. [“Water Rights and Water Use Data.”](https://www.tceq.texas.gov/permitting/water_rights/wr-permitting/wrwud/) Accessed September 13, 2026.
[^11]: Texas Commission on Environmental Quality. [“TCEQ Geographic Web Apps.”](https://www.tceq.texas.gov/gis/tceq-geographic-data-viewers) Accessed September 13, 2026.
[^12]: Virginia Department of Environmental Quality. [“Water Withdrawal.”](https://www.deq.virginia.gov/water/water-withdrawal) Accessed September 13, 2026; [“Virginia DEQ EDMA MapServer.”](https://gisdata.deq.virginia.gov/arcgis/rest/services/public/EDMA/MapServer) Accessed September 13, 2026.
[^13]: Arizona Department of Water Resources. [“GIS Data and Maps.”](https://www.azwater.gov/gis-data-and-maps) Accessed September 13, 2026; [“ADWR GIS.”](https://app.azwater.gov/WaterResourceData/Default.aspx) Accessed September 13, 2026.
[^14]: Arizona Department of Water Resources. [“Search Well Registry.”](https://app.azwater.gov/WellRegistry/SearchWellReg.aspx) Accessed September 13, 2026; [“GIS Data and Maps.”](https://www.azwater.gov/gis-data-and-maps) Accessed September 13, 2026.
[^15]: U.S. Environmental Protection Agency. [“Search Results Help — All Media Programs.”](https://echo.epa.gov/help/facility-search/all-data-search-results-help) Accessed September 13, 2026.
[^16]: U.S. Environmental Protection Agency. [“Known Data Problems.”](https://echo.epa.gov/resources/echo-data/known-data-problems) Accessed September 13, 2026.
[^17]: U.S. Geological Survey. [“Water Data APIs.”](https://api.waterdata.usgs.gov/) Accessed September 13, 2026; [“National Water Availability Assessment Data Companion Web Services.”](https://water.usgs.gov/nwaa-data/web-services) Accessed September 13, 2026.
[^18]: U.S. Geological Survey. [“National Water Availability Assessment Data Companion Web Services.”](https://water.usgs.gov/nwaa-data/web-services) Accessed September 13, 2026.
