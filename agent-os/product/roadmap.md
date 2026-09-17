# Product Roadmap

## Open items

| # | Epoch | Item | Status | Blocker |
|---|-------|------|--------|---------|
| 41 | 10 | Real-data smoke harness | Partial (offline guard shipped) | Needs GDAL + NAS host |
| 42 | 10 | DEM alignment on real tiles | Partial (offline guard shipped) | Bundled into #41 |
| 47 | 11 | Add Utah as a supported region | Not started | Revenue gate (#59) |
| 56 | 11.5 | Narrow made-to-order listing | Not started (code core shipped) | Operational |
| 57 | 11.5 | Repeatable fulfillment pack | Not started (code core shipped) | Operational |
| 58 | 11.5 | Instrument the test | Not started | Depends on #56 |
| 59 | 11.5 | Revenue gate | Not started | 60-day window from first listing |
| 66 | 16 | Canal / ditch / pipeline styling | Not started | Descoped from Epoch 16 close |
| 107 | 26 | `--min-order` in pipeline (CONUS prereq) | Proposed | — |
| 108 | 26 | Streaming SVG writer (CONUS prereq) | Proposed | — |
| 109–111 | 26 | CONUS wiring, coloring & hero render | Proposed | #107, #108, data download |
| 112–119 | 27 | Water-facility and data-center intelligence | Proposed | Source-rights and revenue-priority gate |
| 99–106 | 25 | Operations library & ledger | Proposed | — |

**Revenue gate timing:** measure #59 for 60 days from the actual listing go-live date. The
2026-08-30 planning window did not start the measurement clock; record the launch date in the
revenue ledger and calculate the decision date from it.

---

## Completed epochs (collapsed)

### Epoch 1 — 2D hydrographic art foundation · complete

Items #1–#10. Deterministic, editable GIS-to-SVG pipeline: config/CLI → dataset acquisition →
loading/validation/repair → projection/clipping → graph/ordering/watersheds → coloring →
layered SVG rendering → glow/optimization → multi-format export.

### Epoch 1.5 — Waterbody outlines · complete

Items W1–W4. Waterbody polygon ingestion (FType-driven taxonomy), repair/reproject/clip/select,
fill-free outline rendering as dedicated SVG layers, QA + screen/print-state/print-county presets.
Clark County, WA county-level validation drove the print preset split (state vs. county thresholds).

### Epoch 2 — Elevation data foundation · complete

Items #11–#13. `ElevationSettings` + `ElevationProvenance` contracts, 3DEP DEM tile discovery/
download/cache through injectable seams, mosaic-before-warp normalization + multi-resolution
pyramid. Mosaic-before-warp is load-bearing — don't simplify to warp-then-mosaic (see CLAUDE.md
gotchas).

### Epoch 3 — Accurate terrain and hydrography Z · complete

Items #14–#16. Bilinear terrain sampler, river elevation attribution + downstream-inversion QA +
opt-in monotonic repair, adaptive terrain mesh with boundary clipping and LOD controls.

### Epoch 4 — 3D modeling and delivery · complete

Items #17–#19. 3D scene assembly (terrain + Z-rivers + watershed materials + camera), DEM-backed
progressive preview (`web/3d.html`), reproducible GLB + OBJ export with provenance manifest.

### Epoch 5 — Quality, scale, and productization · complete

Items #20–#22. Accuracy validation suite (`src/accuracy.py`), regional scale (portable cache
manifests, tile-budget controls, resumable jobs, packaging preflight, Idaho as fourth region,
settings-driven DEM acquisition), print/experience modes (hillshade, camera paths, web delivery
experience document).

### Epoch 6 — Interactive art-direction UX · complete

Items #23–#28. `color_by`/`width_by` art-direction options promoted to pipeline, `--county` as
first-class build option, monthly-flow rendering option, `web/studio.html` control surface with
live preview + real pipeline integration, presets & shareable render recipes (base64url encode/
decode, `web/shared/hydro-ux.js`).

### Epoch 7 — External storage & data operations · complete

Item #29. `src/storage.py` resolves cache/datasets/output roots to a configurable external drive
(`--external-root` / `$HYDRO_ART_EXTERNAL_ROOT`), mount-aware local fallback, one-time migration
tool. Storage is infrastructure — never affects rendered bytes.

### Epoch 8 — Terrain-aware print output · complete

Items #30–#32. Pure hillshade compositing seam (`src/compositing.py`), concrete rasterio-backed
DEM reader/reprojector (`src/raster_io.py`), real-tile validation (terrain-print from 3DEP COGs).
Epoch gate artifact: neon river art composited over accurate shaded relief in EPSG:5070.

### Epoch 9 — Codebase health & maintainability · complete

Items #33–#38. De-duplicated `clip_flowlines` render recipe, canonical `INTERNAL_CRS` in
`src/crs.py`, `STATE_HUC4` derived from `REGION_HUC4`, web view-helper extraction into
`hydro-ux.js`, pipeline orchestrator unit tests, retrospective practice established.

### Epoch 12 — Watershed report analytics · complete

Items #48–#54. Pure `src/flow_metrics.py` engine: peak/low-flow series, center-of-timing,
Richards-Baker flashiness, Mann-Kendall + Sen's slope trends, percentile rank, 30-year rolling
normals, model-vs-gauge validation (bias/r/NSE/RMSE), climate-index teleconnection (ENSO/PDO),
PRISM back-catalog 1895–present, sub-watershed + longitudinal decomposition, parametrized report
builder.

### Epoch 13 — Web watershed-report view · complete

Item #55. `web/report.html` on the shared `web/shared/*` foundation — metric tiles, validation
badge, trend sparkline, ENSO overlay. No `src/` → `web/` dependency.

### Epoch 14 — License-free climate source · complete

Item #60. nClimGrid-Monthly provider replaces PRISM as the default (`--climate-source nclimgrid`).
Federal public domain — sellable with attribution. PRISM stays selectable for A/B only; never
sell a PRISM-derived asset. **PRISM Rights gate retired.**

### Epoch 15 — Natural water features · complete

Items #61–#64. Point-feature taxonomy (`src/point_features.py`: spring/waterfall/rapids, FType-
driven), areal taxonomy (`src/areal_features.py`: wetland/playa/perennial_ice), selection +
clipping (`src/areal_selection.py`), point-glyph + areal rendering in `src/rendering.py` with
dedicated `<g>` layers and configurable z-order, `PointFeatureSettings`/`ArealFeatureSettings` +
screen/print presets + CLI flags, additive pipeline integration (loaded in `validate`, rendered in
`generate_svg`). Default (disabled) build byte-identical. Complementary and disjoint with the
waterbody taxonomy.

**Deferred (non-blocking):** Task Group 0 FType code verification against a real GDB — the
classification rule is fixed, only placeholder numeric codes for falls/rapids need confirming.

### Epoch 16 — Hydro-infrastructure layers · complete (except #66)

Items #65, #67, #68 shipped. Hydro-structure taxonomy (`src/hydro_structures.py`: dam/weir, gate,
lock chamber, gaging station, intake/outflow, spillway, canal/ditch), selection + QA
(`src/hydro_structure_selection.py`, `src/hydro_structure_qa.py`), infrastructure rendering with
point glyphs / line bars / areal paths, `HydroStructureSettings` + presets, pipeline integration.
Real HUC4 1807 validated: 557 structures, 553/557 on-network. Default (disabled) byte-identical.

**Item #66 (canal/ditch/pipeline flowline styling) was descoped** from the epoch close — it styles
*NHDFlowline* engineered FTypes distinctly from natural streams, which is a separate concern from
the structure rendering that shipped. Tracked as open work above.

### Epoch 17 — Watershed report: creative analytics · complete

Items #69–#76. Snow-vs-rain regime classification + melt-timing trend, center-of-timing drift
as hero metric, analog-year finder, drought/flood record book, decade flow-duration curves,
ENSO/PDO composite hydrographs, longitudinal flow-accumulation animation frames. All surfaced
in `tools/report_common.py` figures + `web/report.html` on the shared foundation. Suite 884.

### Epoch 18 — Scale-aware flow-width presets · complete

Items #77–#78. `WIDTH_PRESETS` table (state/basin/watershed), `width_log` setting, `--width-preset`
CLI flag. Logarithmic mapping for statewide (headwaters visible next to trunk), power-law for
basin/watershed scale. Default (no preset, `width_by=uniform`) byte-identical.

---

# Generation 1 — Production Release · complete

Epochs 19–23 hardened the engine into a documented, tested, reproducible **v1.0** with four stable
endpoints, a complete test pyramid, an all-endpoints flagship e2e proof, a rights-clean marketing
gallery, and a tagged release behind a reproducibility gate. No new art features. See
`agent-os/retrospectives/2026-09-06-generation-1-production-release.md`.

**Four production endpoints:**

| Endpoint | Deliverable | Entry point |
| --- | --- | --- |
| Digital image | Layered SVG + PNG | `build.py` (2D pipeline) |
| Animation | Year-in-motion GIF/MP4 | `tools/render_monthly.py` · `tools/render_state_yoy.py` |
| Print image | Archival print raster over relief | `tools/render_terrain_print.py` |
| Report | Watershed analytics report | `tools/build_watershed_report.py` |

### Epoch 19 — Production endpoint contracts & hardening · complete
Items #79–#81. Versioned output contracts (`src/endpoints.py`), dispatch consolidation, provenance
+ Rights gate on every endpoint.

### Epoch 20 — Unit & integration test completion · complete
Items #82–#84. Per-module coverage audit, offline endpoint integration tests, coverage gate
(`tools/coverage_report.py --fail-under 90`).

### Epoch 21 — Flagship end-to-end proof · complete
Items #85–#87. Offline all-endpoints orchestration test, real-data `tools/` e2e harness, golden
fixture (extends `tests/fixtures/golden/`).

### Epoch 22 — High-resolution marketing gallery · complete
Items #88–#90. Curated style × region × endpoint matrix, high-res renders, per-asset provenance +
rights ledger on the web surface.

### Epoch 23 — Release packaging, CI & reproducibility gate · complete
Items #91–#93. CI workflows (`ci.yml` + `reproducibility.yml`), double-render reproducibility
gate, v1.0 tag + changelog + distribution packaging.

---

### Epoch 24 — Alpha customer-journey e2e tests · complete

Items #94–#98. Draft `png_size` tier (512–65536), Playwright harness under `tests/e2e/` (boots
`serve.py`, stages a served root), landing + navigation tests, four-endpoint low-res proof e2e
(digital SVG, poster PNG, report figures, animation GIF via live `serve.py`). Non-offline, opt-in.
Clark County `/api/render` proof measured ~6 min (GIS load dominates). See
`agent-os/retrospectives/2026-09-12-epoch-24-alpha-journey-e2e.md`.

---

## Open epochs

### Epoch 10 — Verification & real-data confidence · partially complete

Items #39, #40, #43 shipped. Two items remain:

41. [ ] Real-data smoke harness (opt-in, outside the offline suite) — a `tools/`-driven check that
fires exactly the branches fakes skip: the reprojector's non-identity EPSG:4269→5070 warp, multi-tile
mosaic alignment (the #32 class), and the cross-device SMB mover. Gated behind an env flag/marker so
the offline suite is untouched. `M`

42. [ ] DEM alignment invariant on real tiles — a targeted regression asserting mosaicked tiles share a
pixel grid *after* the single warp, on ≥2 real 3DEP tiles at different latitudes (the #32 bug). `S`
(Partial — the **offline** guard shipped 2026-08-30: `tests/test_dem_alignment.py` asserts
`normalize_dem` mosaics two hand-built two-latitude grids *before* the single warp into one
uniform-pixel grid, and that `_require_aligned` accepts `rel_tol=1e-6` warp drift while rejecting a
genuine tier change. The **real-tile** half is bundled into #41's smoke harness and needs a GDAL/NAS
host.)

Epoch gate: a single command proves determinism (double-render byte-identical) and exercises the real
warp/mosaic/cross-device paths, producing a trustworthy pass/fail; the offline suite is still green.

### Epoch 11 — Year-over-year historical flow · partially complete

Items #44–#46 shipped. One item remains:

47. [ ] Add Utah as a supported region — `tools/derive_state_huc4.py` → UT HUC4s; wire
`SUPPORTED_REGIONS`, `datasets.REGION_HUC4`, `counties.STATE_FIPS`, and `render_common.STATE_HUC4`
mirror; download UT NHDPlus HR GDBs. `S`
    **Deferred (2026-08-30 revenue amendment):** do not start until the Epoch 11.5 revenue gate
    passes — the existing four-state scope (OR/WA/CA/ID) is enough to validate demand.

Epoch gate: a render shows the same network's monthly flow for a chosen historical calendar year
driven by real climate for CA/WA/OR/UT/ID, back to a documented start year; the default
synthetic-year render stays byte-identical.

### Epoch 11.5 — Revenue Validation (gated commercial track)

**Sequencing correction, not a technical epoch** (2026-08-30, informed by the initial market
review — `agent-os/product/revenue-validation-amendment.md`). A time-boxed (4–6 week) commercial
experiment that proves a buyer will pay **before** the product surface expands. **No new `src/`
code; no `PIPELINE_STAGES` change.** Sells only **public-domain-sourced** art (USGS NHDPlus HR /
NHD / WBD) — no PRISM-derived assets. Outcome is first revenue, not a storefront.

**Timeline:** experiment window declared 2026-08-30; the ~6-week target is **~2026-10-11**. The
listing (#56) must go live for the 60-day measurement window (#59) to start.

Code core shipped: `src/fulfillment.py` (order validation, Rights gate, deterministic deliverable
plan + provenance manifest; 29 offline tests) + `tools/fulfill_order.py`.

56. [ ] Narrow made-to-order listing — publish an Etsy (or equivalent) made-to-order listing for a
**personalized county watershed print** in the supported geography (OR/WA/CA/ID). Deliver a
print-ready PDF/PNG in 24–48 h; editable SVG + commercial license are paid add-ons. `S`
57. [ ] Repeatable fulfillment pack — customer intake form, two approved art directions,
title/subtitle rules, export checklist, source-credit/attribution line, proof/approval template. `S`
58. [ ] Instrument the test — track listing views, favorites, inquiries, paid orders, fulfillment
time, refund rate, requested locations/styles, and net revenue in
`agent-os/product/revenue-ledger.md`, plus a monthly decision note. `XS`
59. [ ] Revenue gate — proceed to catalog/POD and self-serve **only** after **≥ 8 paid orders or
$500 gross within 60 days**, with median fulfillment **< 45 min**. Otherwise interview 10
non-buyers, revise the visual/offer, and run one further test; do **not** build subscriptions. `XS`

Epoch gate: first paid orders are observed and measured against #59. If the gate passes, unlock
catalog/POD, Utah (#47), and Epoch 25+ commercialization; if it fails, iterate per #59.

---

## Proposed epochs

### Epoch 26 — Continental US flagship render · proposed

Produce a **single wall-art image of the entire contiguous United States** (48 states) showing
every river basin in the CONUS hydrographic network. Today the pipeline renders one state at a
time — each state maps to its HUC4 basins, and the clip/graph/color stages assume a single
region. This epoch adds a `CONUS` (or multi-region) render mode that stitches all ~160 CONUS
HUC4 basins into one seamless image, with watershed coloring that reads continent-wide and
flow-scaled line widths that keep both the Mississippi trunk and Cascade headwaters legible.
The result is the project's most striking single artifact — a hero image for the website,
marketing, and large-format print.

**Data prerequisite:** all NHDPlus HR + WBD archives for the 48 contiguous states downloaded
and extracted. Western states (HU2 09–18) download in progress (2026-09-13, 147 archives to
NAS); eastern states (HU2 01–08) still needed for full CONUS coverage.

**Pre-implementation analysis (2026-09-13)** identified two architectural blockers in the
current pipeline and a critical filtering gap. The items below are sequenced to resolve
blockers first (independently useful), then build CONUS on top.

**Blockers (unfiltered CONUS scale = ~5M flowline features):**
- **SVG generation OOM.** `render_svg` (`src/rendering.py`) builds the entire SVG as a
  `list[str]` then `"\n".join(lines)`. At ~5M `<path>` elements × ~80 bytes = **~400 MB
  in-memory string**. SVGO and most viewers also choke at this size.
- **NetworkX graph won't fit.** `build_graph` (`src/graph.py`) loads all edges into one
  `nx.MultiDiGraph`. A 5M-edge graph takes **8–15 GB RAM** in NetworkX.
- **CONUS boundary union.** `region_boundary` (`src/clipping.py`) calls `unary_union` on all
  loaded WBD polygons. ~2000 HUC4 polygons → slow and complex MultiPolygon.

**What already works (no changes needed):**
- Multi-region config: `Settings.regions` is already a tuple; `resolve_required_files`
  deduplicates shared HUC4s; `_export_stage` slugifies multi-region filenames.
- Width scaling: `width_log=True` (the `state` preset) normalizes globally on a log scale —
  Mississippi trunk vs. Cascade headwater already handled.
- Coloring algorithm: `greedy_color` is topology-based and handles any graph size.
- `--min-order 3` filtering (Strahler) cuts features by **~80–90%** (~5M → ~500K–1M),
  shrinking the SVG to ~80 MB and the graph to ~4–6 GB — feasible on a workstation. This
  filtering exists in `tools/render_common.py` but **not in the main pipeline**.

**Phase 26.1 — Pipeline prerequisites (independently useful)**

107. [ ] Promote `--min-order` to the pipeline — Wire Strahler-order filtering into the
`validate`/`build_graph` stages as a `--min-order N` CLI flag (default `1` = no filter). Drop
flowlines below the threshold before graph construction so memory scales with the displayable
network, not the full NHDPlus HR. Fail-fast `ConfigError` validation. Byte-identical when
`min_order=1`. This is the single most impactful change for CONUS feasibility — without it,
both the graph and the SVG exceed workstation RAM. Also independently useful for any large-state
render (California, Texas). `M`

108. [ ] Streaming SVG writer — Add `render_svg_stream(f: IO, ...)` alongside the existing
`render_svg() -> str`. The pipeline writes SVG directly to disk via the streaming path; the
`str`-return signature stays for tests and small regions. Eliminates the ~400 MB in-memory
string for continent-scale renders. Byte-identical output (same bytes, written incrementally).
Also independently useful for high-resolution multi-feature renders. `M`

**Phase 26.2 — CONUS wiring**

109. [ ] CONUS region alias & eastern state data — Add `"CONUS"` as a pseudo-region alias in
`src/config.py` that expands to all 48 contiguous states. Wire the remaining ~20 eastern states
(HU2 01–08) into `REGION_HUC4`, `STATE_FIPS`, `REGION_BOUNDS` (same `derive_state_huc4.py`
pattern used for western states). Download + extract the eastern NHDPlus HR + WBD archives.
Handle the `unary_union` boundary cost (pre-simplified CONUS outline or chunked clip). `M`

110. [ ] Continental coloring — Default to `huc_level=HUC2` when region is `CONUS` (~18 macro-
basin color families cycling the 12-color neon palette — clean continent-wide). The coloring
algorithm already works at this scale; this is config/default wiring. `S`

**Phase 26.3 — Hero render**

111. [ ] CONUS hero image & gallery entry — Run the pipeline with `--region conus --min-order 3
--width-preset state`, tune Strahler threshold and palette for visual impact at continental
extent, render at marketing/print resolution, add to the gallery with full provenance + rights
ledger entry (all USGS public domain), and publish on the web surface. `M`

Epoch gate: a single deterministic render produces a wall-art-quality image of the contiguous
United States showing every major river basin, with continent-readable coloring and flow-scaled
widths, from documented public-domain sources; the per-state default output stays byte-identical.

---

### Epoch 25 — Operations library, samples & analysis ledger · proposed

Create an **internal-only PostgreSQL operations ledger**, inspectable in Postico 2, for the
samples, completed work, lineage, and analysis evidence that the current JSON request store and
filesystem cannot search or audit reliably. PostgreSQL stores metadata and immutable references;
the `library/` tree/object storage retains the actual files. **Not a pipeline dependency:** a render
must remain runnable offline, without PostgreSQL, and byte-identical whether the ledger is enabled
or not. The detailed operating model lives in `docs/data-management-strategy.md`.

99. [ ] Ledger boundary & migration contract — Schema, migration policy, PostgreSQL version, roles,
bootstrap, backup/restore, `DATABASE_URL` opt-in. Repository protocol so `OrderStore` remains the
default JSON/offline implementation and no `src/` module imports a PostgreSQL driver at load time.
No ORM. `M`

100. [ ] Core operations schema — Migrations for `places`, `requests`, `orders`, `brief_revisions`,
`render_jobs`, `assets`, `asset_lineage`, `deliveries`, and append-only `events`. Stable public IDs,
state-transition validity, foreign keys, checksums, source/rights/visibility allowlists, immutable
artifact storage keys. Files are never BLOBs; URLs generated when needed, never stored permanently.
Every delivery records `delivered_at`, `access_expires_at` (delivery + 90 days), and
`access_revoked_at`; links deny access after expiry/revocation. Asset retention is a separate
policy. `L`

101. [ ] Sample and completed-work catalog — Assets with role (`sample`/`proof`/`final`/`report`/
`thumbnail`/`bundle`), geography, recipe digest, render-job link, source attribution, rights status,
visibility, dimensions, checksum, parent lineage. Default `internal`; `approved_public` requires an
explicit audited action. `M`

102. [ ] PostgreSQL repository adapter — Wire into operations/order routes only when `DATABASE_URL`
is configured. Preserve JSON-store behavior when absent. Transactional writes, event recording,
ledger failure never alters/deletes a completed artifact. `L`

103. [ ] Legacy import & reconciliation tool — Idempotent `tools/` import of existing
`output/orders/*.json`, fulfillment manifests, and selected gallery/market samples. Dry-run default,
creates/updates/skips/conflicts report, checksum verification, refuse public visibility without
recorded rights. Documented rollback/restore before first live import. `M`

104. [ ] Analysis evidence model — `analysis_runs` and `analysis_metrics` linked to place, recipe/
asset, input provenance, metric-definition version, validation status, result payload. Covers
watershed-report observations and operational measures (proof turnaround, revision count, fulfillment
time, conversion, re-render/determinism failures); never presents derived business measures as source
hydrology. `M`

105. [ ] Postico 2 operator workspace & safe query pack — Read-only SQL views and saved queries for
active requests, proof queue, completed work, public-ready samples, assets missing provenance/rights,
failed jobs, operational metrics, expiring/expired deliveries. Least-privilege Postico connection;
production mutation via application only. `S`

106. [ ] Ledger test and verification pyramid — Pure tests for IDs, state transitions, constraints,
visibility/rights rules, lineage, import planning, JSON fallback (no database). Opt-in PostgreSQL
integration tests (migrations, transactions, repository contract, ledger-on vs. ledger-off artifact
hash identity). Keep PostgreSQL and Postico out of the offline Python suite. `L`

Epoch gate: an operator can use Postico 2 to find a completed sample or customer-private order,
trace it through brief → job → immutable assets → delivery and analysis evidence, and identify
missing provenance/rights. Existing JSON orders are reconciled safely; all offline tests remain
database-free; the same render recipe produces the same artifact bytes with or without the ledger.
Customer download links work for 90 days from delivery and reliably deny access afterward.

---

### Epoch 27 — State water-facility and data-center intelligence · proposed

Build a standalone, internal PostgreSQL/PostGIS analytical database for the 50 states plus DC.
It identifies water facilities and data-center sites, preserves immutable source provenance, and
separates a candidate location from a documented water connection, authorized capacity, and actual
water volume. It is **not** the operations ledger and is never a render-pipeline dependency. The
acquisition and evidence model is documented in `docs/water-facilities-database.md`; the detailed
implementation contract is `agent-os/specs/2026-09-13-water-facilities-data-center-intelligence/`.

112. [ ] Water-intelligence boundary and schema contract — Establish the standalone database,
PostGIS/version/migration policy, roles, source-archive layout, and opt-in connection boundary.
Create the facility, identifier, geometry, permit, measurement, evidence, relationship, service-area,
source-snapshot, source-record, state-source-registry, and reviewed `water_claim` schema. Every
mutable fact is bitemporal (valid time + system/retrieval time); claims carry claim-specific
confidence and customer-display eligibility (`internal_only`, `review_required`,
`publishable_precise`, `publishable_generalized`, `excluded`). No ORM; no `src/` import of a database
driver at module load time. `M`

113. [ ] National baseline ingest — Repeatably acquire and normalize EPA FRS, SDWIS, ICIS-NPDES,
DMR discharge records, CWNS/sewersheds, EPA public-water service areas, USACE NID, and USGS water-use
context for all states/DC. Archive source snapshots, retain source-row keys/checksums, and publish
source-date/completeness status by jurisdiction. Service-area and DMR records are explicitly
geographic/discharge context, never proof of customer use or facility intake. `L`

114. [ ] State water-permit adapter framework and pilots — Define a versioned adapter contract for
API, bulk-file, ArcGIS, HTML-download, and manual-record-request sources. Implement three pilot-state
adapters for withdrawal/water-right, reuse, and state permit records; capture license, coverage,
field mapping, lag, refresh behavior, point precision, and customer-display rights. Start with Texas,
then Virginia; select the third state only after a source-rights audit. `L`

115. [ ] Data-center candidate and evidence workflow — Discover candidates from NAICS 518210, public
operator/local records, and open map data; link them only through deterministic, reviewable matching.
Record water relevance as `candidate`, `permitted_or_committed`, `confirmed`, or `unknown`; never
infer use from facility size. Store measured, reported, authorized, withdrawal, delivered, consumed,
and discharged quantities as distinct facts. `M`

116. [ ] Analytical query layer and coverage readout — Produce documented state/county/HUC queries
that separately summarize measured, reported, and authorized quantities; expose facility provenance,
confidence, and last-source-check. Service-area intersection is labelled as geographic context, never
proof of a customer relationship. `M`

117. [ ] Water-intelligence verification pyramid — Offline pure unit tests for normalization, unit
handling, evidence ranking, source provenance, matching decisions, and aggregation; opt-in PostGIS
integration tests for migrations, spatial relationships, constraints, and idempotent re-ingestion.
Sample and manually review auto-matches before each state batch is promoted. `L`

118. [ ] Customer facility-request options for images and reports — Add an opt-in request control to
the image and watershed-report journeys: facility classes, requested named facilities, purpose
(visual context / evidence-backed report), and scope. Offer three explicit products: water
infrastructure context, named-facility research note, and evidence-backed water overlay. Resolve the
request against the water-intelligence database and attach a versioned result manifest to the
render/report brief. Only reviewed, publishable evidence may be shown; an unavailable, ambiguous, or
non-public result is an honest omission/explanation, never a generated claim. Keep the default
image/report unchanged and make facility display a non-pipeline, explicit overlay/annotation option.
`M`

119. [ ] Data quality, caveat, and claim-display layer — Ingest source-specific quality alerts and
restrictions (including federal/state transfer caveats) into a queryable `data_alert` model. Customer
and analytical views must render claim-level source date, precision, confidence, quantity status, and
applicable caveat. Generalize locations where the approved display policy requires it; preserve the
full internal evidence trail. `M`

Epoch gate: a user can select a pilot state and retrieve water facilities and data-center candidates
with raw-source provenance, explicit confidence/relevance labels, and no conflation of authorized or
aggregate water values with measured site consumption. Re-running an unchanged snapshot is idempotent;
the offline suite remains network-, GIS-, and database-free.

---

## Self-serve customer journey (Epochs 28–30)

Implements the automated no-account customer experience: form → queue → proof →
accept/revise → pay → deliver. Builds on the customer-operations-experience
blueprint (`agent-os/specs/2026-09-05-customer-operations-experience/spec.md`)
but replaces concierge operations with automated self-serve for the happy path.
No user accounts or passwords — email is the only identifier. See individual
epoch specs under `agent-os/specs/`.

### Epoch 28 — Self-serve order form & automated proof loop

The core customer journey: a web form captures product choice + customizations,
submits to the render queue, generates a proof, and presents it via a signed
temporary link. The customer accepts (→ payment) or adjusts settings and
re-renders. All without an account. Extends the existing `src/orders.py` state
machine and `src/server.py` API. Email notifications at each transition.

120. [ ] Order form schema & validation — Define the customer-facing request payload
(product type, region, county, art direction, size, title/subtitle, email, optional
note). Validate against `src/config.py` allowlists + `src/fulfillment.py` rights gate.
Pure, offline-testable. `M`

121. [ ] Order form web UI — Guided multi-step form on `web/order.html`: product
selection → region/county → art direction → size/title → email → review & submit.
Progressive disclosure, no GIS jargon. Wired to `POST /api/orders`. `M`

122. [ ] Automated render queue — On order submission, auto-transition
submitted → accepted → rendering. Wire `OrderStore` to `JobRunner` so accepted
orders dispatch a render job. Track `job_id` on the request record. `M`

123. [ ] Proof generation & signed links — On render completion, generate a
watermarked proof image, store it, transition to `proof_ready`. Create a signed
URL (HMAC + expiry) for the proof review page. No login required. `M`

124. [ ] Proof review page — `web/proof.html?token=<signed>`: displays the
watermarked proof, production summary, source credit, and two actions: "Approve"
or "Adjust & re-render." Adjustment returns to a pre-filled form; re-submit
creates a new render cycle. Token-validated, no auth. `M`

125. [ ] Order event log — Append-only `events` list on each request record:
every status transition, render start/complete, proof view, approval, payment,
delivery. Structured JSON for product analytics. `S`

126. [ ] Email notifications — Confirmation on submit, proof-ready with review
link, approval receipt, delivery with download link. Extend existing
`src/email_delivery.py`. `S`

Epoch gate: a customer fills out a form, receives a proof via email link, can
approve or adjust and re-render, and the entire lifecycle is logged as structured
events — all without creating an account.

### Epoch 29 — Payment & delivery

Payment capture on proof approval and time-limited delivery of final artifacts.

127. [ ] Stripe Checkout integration — On proof approval, create a Stripe
Checkout Session with the order total (product price + add-ons). Redirect to
Stripe-hosted payment page. Handle `checkout.session.completed` webhook to
confirm payment. No card data touches our server. `L`

128. [ ] Payment state machine — Extend `STATUSES`/`TRANSITIONS`: approved →
payment_pending → paid → fulfilled. Record Stripe session ID, payment intent,
amount, and timestamp on the request. `S`

129. [ ] Signed delivery links — On payment confirmation, generate the final
(un-watermarked) deliverable. Create a signed download URL that expires after
90 days. Store `delivered_at`, `access_expires_at` on the request. `M`

130. [ ] Delivery page — `web/delivery.html?token=<signed>`: download links for
all formats (SVG, PNG, PDF), attribution/source credit, title, and "save this
link" language. Token-validated, time-limited. `S`

131. [ ] Custom trip overlay (premium) — Accept GPX/KML file upload via
`web/order.html` for a "memorial trip" add-on. Overlay the path on the base art.
50% surcharge applied automatically. Manual review gate for path quality before
proof. `L`

Epoch gate: a customer approves a proof, pays via Stripe, receives a time-limited
download link for the final artifact, and the payment + delivery are logged. Trip
overlays render with a 50% surcharge.

### Epoch 30 — Print fulfillment & product analytics

Print forwarding to a vendor and structured analytics for product improvement.

132. [ ] Print vendor integration — Wire Printful (or Prodigi) API: on paid
print orders, submit the print-ready file + shipping address. Customer covers
print + shipping cost (pass-through). Track print order ID and shipment status
on the request record. `L`

133. [ ] Shipping address capture — Add shipping fields to the order form for
print products. Validate address format. Pass to print vendor on fulfillment. `S`

134. [ ] Print proof-to-production handoff — After payment, auto-submit to
print vendor. Email customer with expected delivery window and tracking number
when available. `M`

135. [ ] Product analytics dashboard — Aggregate event logs: orders by product/
region/art-direction, render times, proof acceptance rate, revision reasons,
payment conversion, fulfillment time. Internal-only `tools/analytics_report.py`
or simple web dashboard. `M`

136. [ ] Render performance instrumentation — Time each pipeline stage, log total
render duration, track queue depth and wait time. Surface in analytics for
capacity planning. `S`

Epoch gate: a print order flows from payment through vendor submission to customer
delivery with tracking; product analytics show conversion funnel and render
performance metrics.

---

## Prior customer-to-operations experience blueprint

The four-artifact catalog, no-account buyer journey, operations intake, production
workspace, proof/revision loop, and asset-library model are documented in
`agent-os/specs/2026-09-05-customer-operations-experience/spec.md`. The compact
cradle-to-grave flowchart is `workflow.mmd` in that directory. This is an
**experimental UX and operations design brief**, not authorization to bypass the
Epoch 11.5 revenue gate for catalog/POD, self-serve, or commercial expansion.

---

> Notes
> - Epochs are gated by a demonstrable artifact, not calendar dates.
> - "Accurate" always means sampled from a documented bare-earth DEM with stated horizontal
>   and vertical CRS/units. Vertical exaggeration is display-only and never overwrites source Z.
> - Effort scale: XS=1 day, S=2–3 days, M=1 week, L=2 weeks, XL=3+ weeks.
> - **Rights gate (commercial data use).** USGS NHDPlus HR / NHD / WBD are U.S. federal public domain and
>   free to sell — but record the source version + attribution line for every sold art asset. **The PRISM
>   climate Rights gate is RETIRED (Epoch 14 #60, 2026-09-01):** the year-over-year / watershed-report
>   climate dependency now defaults to **NOAA NCEI nClimGrid-Monthly, which is U.S. federal public
>   domain** — free to sell with attribution *"Climate data: NOAA NCEI nClimGrid-Monthly (public
>   domain)."* The default `--climate-source nclimgrid` path (spans #45–#55) is therefore commercially
>   clear at $0. PRISM stays selectable via `--climate-source prism` for A/B comparison **only**; **any
>   PRISM-derived asset remains non-sellable** (PRISM is not public domain and its commercial use needs a
>   written PRISM Climate Group arrangement) — so never ship a `--climate-source prism` render
>   commercially.
> - **Revenue gate (commercial expansion).** Catalog/POD, self-serve, subscriptions, and region expansion
>   beyond OR/WA/CA/ID (Utah #47) are gated on the Epoch 11.5 revenue outcome — proven demand, not shipped
>   features. Validation-first: prove a buyer will pay before widening the product surface.
