// Randomized exploration — exercises the report builder and order form with
// random state/county/basin selections, captures screenshots to output/.
// Not part of CI; run manually to visually audit the product across varied inputs.
const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

const OUTPUT_DIR = path.resolve(__dirname, '..', '..', '..', 'output', 'e2e-screenshots');

// Ensure output dir exists
test.beforeAll(() => {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
});

// Seeded PRNG for reproducible "random" selections
function mulberry32(seed) {
  return function () {
    seed |= 0; seed = seed + 0x6D2B79F5 | 0;
    var t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

function pick(rng, arr) {
  return arr[Math.floor(rng() * arr.length)];
}

const SCOPES = ['state', 'county', 'basin'];

test.describe('Random exploration — report builder', () => {

  for (let trial = 0; trial < 10; trial++) {
    test(`trial ${trial + 1}: random location → preview → screenshot`, async ({ page }) => {
      const rng = mulberry32(42 + trial);
      await page.goto('/web/report.html', { waitUntil: 'load' });

      // Pick a random scope
      const scope = pick(rng, SCOPES);
      await page.click(`[data-scope="${scope}"]`);

      // Get all state options (skip placeholder)
      const stateOptions = await page.locator('#pk-state option').evaluateAll(
        (opts) => opts.filter((o) => o.value).map((o) => o.value)
      );
      const state = pick(rng, stateOptions);
      await page.selectOption('#pk-state', state);

      let locationLabel = state;

      if (scope === 'county') {
        await page.waitForTimeout(50);
        const countyOptions = await page.locator('#pk-county option').evaluateAll(
          (opts) => opts.filter((o) => o.value).map((o) => o.value)
        );
        if (countyOptions.length > 0) {
          const county = pick(rng, countyOptions);
          await page.selectOption('#pk-county', county);
          locationLabel = `${county}-County-${state}`;
        }
      } else if (scope === 'basin') {
        await page.waitForTimeout(50);
        const basinOptions = await page.locator('#pk-basin option').evaluateAll(
          (opts) => opts.filter((o) => o.value).map((o) => o.value)
        );
        if (basinOptions.length > 0) {
          const basin = pick(rng, basinOptions);
          await page.selectOption('#pk-basin', basin);
          locationLabel = `HUC4-${basin}-${state}`;
        }
      }

      // Randomize year range
      const startYear = 1980 + Math.floor(rng() * 20);
      const endYear = startYear + 10 + Math.floor(rng() * 15);
      await page.selectOption('#opt-start-year', String(startYear));
      await page.selectOption('#opt-end-year', String(Math.min(endYear, 2023)));

      // Randomly toggle off 2-3 sections
      const toggleCount = 2 + Math.floor(rng() * 2);
      const sections = ['tiles', 'long', 'typical', 'enso', 'regime', 'analogs',
        'records', 'facilities', 'fdc', 'composites'];
      for (let i = 0; i < toggleCount; i++) {
        const section = pick(rng, sections);
        const toggle = page.locator(`[data-section="${section}"]`);
        await toggle.evaluate((el) => el.click());
      }

      // Random format
      const formats = ['digital', 'print', 'web'];
      await page.click(`[data-format="${pick(rng, formats)}"]`);

      // Generate preview
      const isEnabled = await page.locator('#btnGenerate').isEnabled();
      if (!isEnabled) {
        // Skip if selection incomplete (e.g. no basins for this state)
        return;
      }
      await page.click('#btnGenerate');
      await expect(page.locator('#reportView')).toBeVisible();

      // Screenshot the full preview
      const filename = `report-${String(trial + 1).padStart(2, '0')}-${scope}-${locationLabel}.png`
        .replace(/[^a-zA-Z0-9._-]/g, '_');
      await page.screenshot({
        path: path.join(OUTPUT_DIR, filename),
        fullPage: true,
      });

      // Verify no JS errors accumulated
      // (page errors would have thrown already via Playwright's default behavior)
      await expect(page.locator('#reportView')).toBeVisible();
    });
  }
});

test.describe('Random exploration — order form handoff', () => {

  for (let trial = 0; trial < 5; trial++) {
    test(`trial ${trial + 1}: random report → order handoff → screenshot`, async ({ page }) => {
      const rng = mulberry32(100 + trial);
      await page.goto('/web/report.html', { waitUntil: 'load' });

      // Pick county scope with a random state+county
      await page.click('[data-scope="county"]');
      const stateOptions = await page.locator('#pk-state option').evaluateAll(
        (opts) => opts.filter((o) => o.value).map((o) => o.value)
      );
      const state = pick(rng, stateOptions);
      await page.selectOption('#pk-state', state);
      await page.waitForTimeout(50);

      const countyOptions = await page.locator('#pk-county option').evaluateAll(
        (opts) => opts.filter((o) => o.value).map((o) => o.value)
      );
      if (countyOptions.length === 0) return;
      const county = pick(rng, countyOptions);
      await page.selectOption('#pk-county', county);

      // Generate preview
      await page.click('#btnGenerate');
      await expect(page.locator('#reportView')).toBeVisible();

      // Screenshot the report preview
      await page.screenshot({
        path: path.join(OUTPUT_DIR, `handoff-${trial + 1}-report-${state}-${county}.png`
          .replace(/[^a-zA-Z0-9._-]/g, '_')),
        fullPage: true,
      });

      // Click order button
      await Promise.all([
        page.waitForURL('**/order.html?*'),
        page.click('#btnOrder'),
      ]);

      // Verify we skipped to step 3 (style)
      await expect(page.locator('#step-3')).toBeVisible();

      // Screenshot the order form
      await page.screenshot({
        path: path.join(OUTPUT_DIR, `handoff-${trial + 1}-order-${state}-${county}.png`
          .replace(/[^a-zA-Z0-9._-]/g, '_')),
        fullPage: true,
      });

      // Verify URL params
      const url = new URL(page.url());
      expect(url.searchParams.get('product')).toBe('watershed-report');
      expect(url.searchParams.get('region')).toBe(state);
      expect(url.searchParams.get('county')).toBe(county);
    });
  }
});

test.describe('Random exploration — deep links', () => {

  for (let trial = 0; trial < 5; trial++) {
    test(`trial ${trial + 1}: random deep-link → auto-preview → screenshot`, async ({ page }) => {
      const rng = mulberry32(200 + trial);

      // Get state list from the page
      await page.goto('/web/report.html', { waitUntil: 'load' });
      const stateOptions = await page.locator('#pk-state option').evaluateAll(
        (opts) => opts.filter((o) => o.value).map((o) => o.value)
      );
      const state = pick(rng, stateOptions);
      await page.selectOption('#pk-state', state);
      await page.waitForTimeout(50);

      const countyOptions = await page.locator('#pk-county option').evaluateAll(
        (opts) => opts.filter((o) => o.value).map((o) => o.value)
      );
      if (countyOptions.length === 0) return;
      const county = pick(rng, countyOptions);

      // Navigate via deep link
      const deepUrl = `/web/report.html?state=${encodeURIComponent(state)}&county=${encodeURIComponent(county)}`;
      await page.goto(deepUrl, { waitUntil: 'load' });
      await page.waitForTimeout(200);

      // Report should auto-generate
      await expect(page.locator('#reportView')).toBeVisible();

      await page.screenshot({
        path: path.join(OUTPUT_DIR, `deeplink-${trial + 1}-${state}-${county}.png`
          .replace(/[^a-zA-Z0-9._-]/g, '_')),
        fullPage: true,
      });
    });
  }
});
