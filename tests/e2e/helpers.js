// Shared helpers + fixtures for the alpha customer-journey e2e (Epoch 24).
const { expect } = require('@playwright/test');

// Draft raster tier (Epoch 24 #94) keeps proof renders fast during design iteration.
// Any SUPPORTED_PNG_SIZES value works; the small tiers (512/1024/2048) are the point.
const PNG_SIZE = Number(process.env.PNG_SIZE || 1024);

// The pipeline's demo county — public-domain USGS NHDPlus HR; the landing showcases it.
// COUNTY is the Census cartographic-boundary `NAME` value (bare, no " County"
// suffix), because src/counties.py's CensusCountyProvider matches on NAME — the
// shapefile stores "Clark" in NAME and "Clark County" only in NAMELSAD.
const REGION = process.env.HARNESS_REGION || 'Washington';
const COUNTY = process.env.HARNESS_COUNTY || 'Clark';

// The four catalog pages the landing (web/start.html) fans out to, one per product
// endpoint (src/endpoints.py). Hrefs are the repo-root-absolute paths start.html uses.
const CATALOG = [
  { endpoint: 'print_image', card: 'Archival poster', page: '/web/proto-b-guided.html' },
  { endpoint: 'report', card: 'Watershed report', page: '/web/report.html' },
  { endpoint: 'digital_image', card: 'Digital image', page: '/web/studio.html' },
  { endpoint: 'animation', card: 'Year in motion', page: '/web/proto-c-canvas.html' },
];

// POST a render to the live /api/render backend and poll /api/jobs/<id> to a terminal
// state. Mirrors studio.html's own submit+poll flow (server.py routes).
//
// The default deadline is generous (10 min, override via RENDER_TIMEOUT_MS). A Clark
// County proof measures ~6 min wall-clock: `validate` loads the whole Washington
// region (27 layers, ~2.3M geometries) and repair+reproject over that dominates —
// the actual county clip → graph → watersheds → SVG → PNG export is only ~13s once
// reprojected. So the draft png_size (#94) barely helps: the cost is the fixed
// pre-clip GIS load, not rasterization. Pair with test.slow() in the spec.
async function renderViaApi(
  request,
  baseURL,
  payload,
  { timeoutMs = Number(process.env.RENDER_TIMEOUT_MS || 600_000) } = {}
) {
  const res = await request.post(`${baseURL}/api/render`, { data: payload });
  expect(res.status(), await res.text()).toBe(202);
  const { job } = await res.json();
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    if (Date.now() > deadline) throw new Error(`render job ${job} timed out`);
    await new Promise((r) => setTimeout(r, 1000));
    const s = await request.get(`${baseURL}/api/jobs/${job}`);
    expect(s.ok()).toBeTruthy();
    const envelope = await s.json();
    if (envelope.state === 'succeeded') return { job, envelope };
    if (envelope.state === 'failed') throw new Error(`render failed: ${envelope.error}`);
  }
}

module.exports = { PNG_SIZE, REGION, COUNTY, CATALOG, renderViaApi };
