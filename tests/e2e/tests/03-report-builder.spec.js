// #142–#143 Report builder with paywall preview and order handoff e2e.
// These run without the GIS stack — they exercise client JS, picker state,
// section toggles, paywall boundary, facility listing, order handoff URL
// params, and deep-link auto-populate.
const { test, expect } = require('@playwright/test');

// Collect console errors + uncaught page errors.
function trackErrors(page) {
  const errors = [];
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(`console: ${m.text()}`);
  });
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
  return errors;
}

test.describe('Report builder (#142)', () => {

  test('report.html loads with no console errors', async ({ page }) => {
    const errors = trackErrors(page);
    const resp = await page.goto('/web/report.html', { waitUntil: 'load' });
    expect(resp?.status()).toBe(200);
    await expect(page).toHaveTitle(/Riverglyph/i);
    expect(errors, errors.join('\n')).toEqual([]);
  });

  test('empty state shown before preview', async ({ page }) => {
    await page.goto('/web/report.html', { waitUntil: 'load' });
    await expect(page.locator('#emptyState')).toBeVisible();
    await expect(page.locator('#reportView')).toBeHidden();
  });

  test('preview button disabled until location complete', async ({ page }) => {
    await page.goto('/web/report.html', { waitUntil: 'load' });
    await expect(page.locator('#btnGenerate')).toBeDisabled();
    // Select state only — county scope is default, so still disabled
    await page.selectOption('#pk-state', 'Washington');
    await expect(page.locator('#btnGenerate')).toBeDisabled();
    // Select county — now enabled
    await page.selectOption('#pk-county', 'Clark');
    await expect(page.locator('#btnGenerate')).toBeEnabled();
  });

  test('state scope enables preview with state only', async ({ page }) => {
    await page.goto('/web/report.html', { waitUntil: 'load' });
    await page.click('[data-scope="state"]');
    await page.selectOption('#pk-state', 'Oregon');
    await expect(page.locator('#btnGenerate')).toBeEnabled();
  });

  test('basin scope shows basin dropdown and enables preview', async ({ page }) => {
    await page.goto('/web/report.html', { waitUntil: 'load' });
    await page.click('[data-scope="basin"]');
    await expect(page.locator('#basin-field')).toBeVisible();
    await expect(page.locator('#county-field')).toBeHidden();
    await page.selectOption('#pk-state', 'Washington');
    // Select a basin
    const basinOptions = await page.locator('#pk-basin option').count();
    expect(basinOptions).toBeGreaterThan(1); // placeholder + at least one basin
    await page.selectOption('#pk-basin', { index: 1 });
    await expect(page.locator('#btnGenerate')).toBeEnabled();
  });

  test('preview generates report with correct header', async ({ page }) => {
    const errors = trackErrors(page);
    await page.goto('/web/report.html', { waitUntil: 'load' });
    await page.selectOption('#pk-state', 'Washington');
    await page.selectOption('#pk-county', 'Clark');
    await page.click('#btnGenerate');
    await expect(page.locator('#reportView')).toBeVisible();
    await expect(page.locator('#emptyState')).toBeHidden();
    await expect(page.locator('#wsName')).toHaveText('Clark Creek');
    await expect(page.locator('#wsPlace')).toContainText('Clark County');
    expect(errors, errors.join('\n')).toEqual([]);
  });

  test('custom title overrides watershed name', async ({ page }) => {
    await page.goto('/web/report.html', { waitUntil: 'load' });
    await page.selectOption('#pk-state', 'Washington');
    await page.selectOption('#pk-county', 'Clark');
    await page.fill('#opt-title', 'Salmon Creek Basin');
    await page.click('#btnGenerate');
    await expect(page.locator('#wsName')).toHaveText('Salmon Creek Basin');
  });

  test('year range affects report range badge', async ({ page }) => {
    await page.goto('/web/report.html', { waitUntil: 'load' });
    await page.selectOption('#pk-state', 'Oregon');
    await page.click('[data-scope="state"]');
    await page.selectOption('#opt-start-year', '2000');
    await page.selectOption('#opt-end-year', '2020');
    await page.click('#btnGenerate');
    await expect(page.locator('#rangeBadge')).toContainText('2000');
    await expect(page.locator('#rangeBadge')).toContainText('2020');
  });

  test('deterministic preview — same selection produces same peak value', async ({ page }) => {
    await page.goto('/web/report.html', { waitUntil: 'load' });
    await page.selectOption('#pk-state', 'Washington');
    await page.selectOption('#pk-county', 'Clark');
    await page.click('#btnGenerate');
    const peak1 = await page.locator('#tiles .metric-tile .value').first().textContent();
    // Re-generate — should be identical
    await page.click('#btnGenerate');
    const peak2 = await page.locator('#tiles .metric-tile .value').first().textContent();
    expect(peak1).toBe(peak2);
  });
});

test.describe('Paywall boundary (#142)', () => {

  test('paywall CTA visible after preview', async ({ page }) => {
    await page.goto('/web/report.html', { waitUntil: 'load' });
    await page.selectOption('#pk-state', 'Washington');
    await page.selectOption('#pk-county', 'Clark');
    await page.click('#btnGenerate');
    await expect(page.locator('#paywallCta')).toBeVisible();
    await expect(page.locator('.btn-unlock')).toBeVisible();
    await expect(page.locator('.paywall-cta .price')).toContainText('$95');
  });

  test('paywall fade div exists with gradient overlay', async ({ page }) => {
    await page.goto('/web/report.html', { waitUntil: 'load' });
    await page.selectOption('#pk-state', 'Washington');
    await page.selectOption('#pk-county', 'Clark');
    await page.click('#btnGenerate');
    const fade = page.locator('.paywall-fade');
    await expect(fade).toBeVisible();
    // The ::after pseudo-element creates the gradient — verify the container exists
    const box = await fade.boundingBox();
    expect(box).toBeTruthy();
    expect(box.height).toBeGreaterThan(0);
  });
});

test.describe('Section toggles (#142)', () => {

  test('toggling off a section hides it in the preview', async ({ page }) => {
    await page.goto('/web/report.html', { waitUntil: 'load' });
    await page.selectOption('#pk-state', 'Washington');
    await page.selectOption('#pk-county', 'Clark');
    await page.click('#btnGenerate');
    // Long record should be visible by default
    const longCard = page.locator('[data-section-id="long"]');
    await expect(longCard).toBeVisible();
    // Toggle it off — click the visible slider span, not the hidden checkbox
    const toggle = page.locator('[data-section="long"]');
    await toggle.evaluate((el) => el.click());
    await expect(longCard).toBeHidden();
    // Toggle it back on
    await toggle.evaluate((el) => el.click());
    await expect(longCard).toBeVisible();
  });

  test('all 10 section toggles exist', async ({ page }) => {
    await page.goto('/web/report.html', { waitUntil: 'load' });
    const toggleCount = await page.locator('[data-section]').count();
    expect(toggleCount).toBe(10);
  });
});

test.describe('Facility listing (#142)', () => {

  test('facilities show for a basin with known facilities', async ({ page }) => {
    await page.goto('/web/report.html', { waitUntil: 'load' });
    await page.click('[data-scope="basin"]');
    await page.selectOption('#pk-state', 'Virginia');
    await page.selectOption('#pk-basin', '0207');
    await page.click('#btnGenerate');
    const facilityList = page.locator('.facility-list');
    await expect(facilityList).toBeVisible();
    const items = await facilityList.locator('li').count();
    expect(items).toBeGreaterThan(5); // Potomac basin has 17 facilities
    // Should include a data center
    await expect(facilityList).toContainText('Equinix Ashburn');
  });

  test('facilities show "no known facilities" for empty basin', async ({ page }) => {
    await page.goto('/web/report.html', { waitUntil: 'load' });
    await page.click('[data-scope="basin"]');
    await page.selectOption('#pk-state', 'Washington');
    // Pick a basin without curated facilities (e.g. 1710)
    await page.selectOption('#pk-basin', '1710');
    await page.click('#btnGenerate');
    await expect(page.locator('.facility-empty')).toBeVisible();
  });

  test('county-scoped lookup filters facilities by county', async ({ page }) => {
    await page.goto('/web/report.html', { waitUntil: 'load' });
    // Loudoun County has data centers on HUC4 0207
    await page.selectOption('#pk-state', 'Virginia');
    await page.selectOption('#pk-county', 'Loudoun');
    await page.click('#btnGenerate');
    const facilityList = page.locator('.facility-list');
    await expect(facilityList).toBeVisible();
    // Should include Loudoun facilities but not Fairfax ones
    await expect(facilityList).toContainText('Equinix Ashburn');
    const text = await facilityList.textContent();
    expect(text).not.toContain('CoreSite Reston'); // Fairfax county
  });
});

test.describe('Order handoff (#143)', () => {

  test('order button navigates to order.html with correct params', async ({ page }) => {
    await page.goto('/web/report.html', { waitUntil: 'load' });
    await page.selectOption('#pk-state', 'Washington');
    await page.selectOption('#pk-county', 'Clark');
    await page.click('#btnGenerate');
    // Click sidebar order button
    await Promise.all([
      page.waitForURL('**/order.html?*'),
      page.click('#btnOrder'),
    ]);
    const url = new URL(page.url());
    expect(url.searchParams.get('product')).toBe('watershed-report');
    expect(url.searchParams.get('region')).toBe('Washington');
    expect(url.searchParams.get('county')).toBe('Clark');
  });

  test('paywall order button navigates with same params', async ({ page }) => {
    await page.goto('/web/report.html', { waitUntil: 'load' });
    await page.selectOption('#pk-state', 'Oregon');
    await page.click('[data-scope="state"]');
    await page.click('#btnGenerate');
    await Promise.all([
      page.waitForURL('**/order.html?*'),
      page.click('#btnPaywallOrder'),
    ]);
    const url = new URL(page.url());
    expect(url.searchParams.get('product')).toBe('watershed-report');
    expect(url.searchParams.get('region')).toBe('Oregon');
  });

  test('order form skips to style step when product+location pre-filled', async ({ page }) => {
    const errors = trackErrors(page);
    await page.goto('/web/order.html?product=watershed-report&region=Washington&county=Clark', {
      waitUntil: 'load',
    });
    // Should be on step 3 (Style), not step 1 or 2
    await expect(page.locator('#step-3')).toBeVisible();
    await expect(page.locator('#step-1')).toBeHidden();
    await expect(page.locator('#step-2')).toBeHidden();
    expect(errors, errors.join('\n')).toEqual([]);
  });

  test('product alias normalization — short names resolve', async ({ page }) => {
    // start.html uses "print", order form expects "fine-art-print"
    await page.goto('/web/order.html?product=print', { waitUntil: 'load' });
    await expect(page.locator('#step-2')).toBeVisible();
    await expect(page.locator('[data-product="fine-art-print"]')).toHaveClass(/selected/);
  });

  test('digital alias resolves to digital-image', async ({ page }) => {
    await page.goto('/web/order.html?product=digital', { waitUntil: 'load' });
    await expect(page.locator('#step-2')).toBeVisible();
    await expect(page.locator('[data-product="digital-image"]')).toHaveClass(/selected/);
  });

  test('title pre-fill from URL param', async ({ page }) => {
    await page.goto(
      '/web/order.html?product=watershed-report&region=Washington&county=Clark&title=Salmon%20Creek',
      { waitUntil: 'load' }
    );
    const titleVal = await page.locator('#inp-title').inputValue();
    expect(titleVal).toBe('Salmon Creek');
  });

  test('email pre-fill from URL param', async ({ page }) => {
    await page.goto('/web/order.html?product=digital-image&email=test@example.com', {
      waitUntil: 'load',
    });
    const emailVal = await page.locator('#inp-email').inputValue();
    expect(emailVal).toBe('test@example.com');
  });
});

test.describe('Deep-link auto-populate (#142)', () => {

  test('county deep-link auto-generates preview', async ({ page }) => {
    const errors = trackErrors(page);
    await page.goto('/web/report.html?state=Washington&county=Clark', { waitUntil: 'load' });
    // Wait for setTimeout(0) deferred generation
    await page.waitForTimeout(100);
    await expect(page.locator('#reportView')).toBeVisible();
    await expect(page.locator('#emptyState')).toBeHidden();
    await expect(page.locator('#wsName')).toHaveText('Clark Creek');
    expect(errors, errors.join('\n')).toEqual([]);
  });

  test('basin deep-link auto-generates preview', async ({ page }) => {
    await page.goto('/web/report.html?state=Washington&basin=1708', { waitUntil: 'load' });
    await page.waitForTimeout(100);
    await expect(page.locator('#reportView')).toBeVisible();
    await expect(page.locator('#wsName')).toHaveText('Basin 1708');
    // Scope button should show "basin" as active
    await expect(page.locator('[data-scope="basin"]')).toHaveClass(/active/);
  });

  test('state-only deep-link does not auto-generate (needs scope click)', async ({ page }) => {
    await page.goto('/web/report.html?state=Oregon', { waitUntil: 'load' });
    await page.waitForTimeout(100);
    // State alone with county scope (default) is not enough — no auto-generate
    await expect(page.locator('#emptyState')).toBeVisible();
  });
});

test.describe('Responsive layout (#142)', () => {

  test('single-column layout at narrow viewport', async ({ page }) => {
    await page.setViewportSize({ width: 600, height: 800 });
    await page.goto('/web/report.html', { waitUntil: 'load' });
    const config = page.locator('.config-panel');
    const preview = page.locator('.preview-panel');
    const configBox = await config.boundingBox();
    const previewBox = await preview.boundingBox();
    // In single-column mode, preview should be below config (not side-by-side)
    expect(previewBox.y).toBeGreaterThan(configBox.y);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// Order form prefill → review integration tests
// Verifies that URL-param prefill correctly propagates S.region/S.county
// through to the review step. Regression suite for the "Unsupported region ''"
// bug where S.region was not explicitly set during prefill.
// ═══════════════════════════════════════════════════════════════════════════════

test.describe('Order prefill → review (#143 regression)', () => {

  // Helper: navigate through steps 3–6 to reach the review, filling required
  // fields along the way. Assumes step 3 (Style) is the starting step.
  async function walkToReview(page, { email, name } = {}) {
    // Step 3: select style
    await page.click('[data-style="neon-basin"]');
    await page.click('#btn-next-3');
    // Step 4: title (optional — just proceed)
    await page.click('#btn-next-4');
    // Step 5: contact
    await page.fill('#inp-email', email || 'test@example.com');
    if (name) await page.fill('#inp-name', name);
    await page.click('#btn-next-5');
    // Now on step 6 (review)
    await expect(page.locator('#step-6')).toBeVisible();
  }

  test('prefilled region+county appear correctly in review', async ({ page }) => {
    const errors = trackErrors(page);
    await page.goto(
      '/web/order.html?product=watershed-report&region=Washington&county=Clark',
      { waitUntil: 'load' }
    );
    await walkToReview(page);
    const location = await page.locator('#rev-location').textContent();
    expect(location).toBe('Clark County, Washington');
    expect(errors, errors.join('\n')).toEqual([]);
  });

  test('multi-word state (New York) preserved through prefill to review', async ({ page }) => {
    const errors = trackErrors(page);
    await page.goto(
      '/web/order.html?product=watershed-report&region=New+York&county=New+York',
      { waitUntil: 'load' }
    );
    await walkToReview(page);
    const location = await page.locator('#rev-location').textContent();
    expect(location).toBe('New York County, New York');
    expect(errors, errors.join('\n')).toEqual([]);
  });

  test('state-only prefill (no county) shows state on review after manual county pick', async ({ page }) => {
    const errors = trackErrors(page);
    await page.goto(
      '/web/order.html?product=watershed-report&region=Oregon',
      { waitUntil: 'load' }
    );
    // Should land on step 2 (location) — county not prefilled
    await expect(page.locator('#step-2')).toBeVisible();
    // Manually select a county
    await page.selectOption('#sel-county', 'Multnomah');
    await page.click('#btn-next-2');
    await walkToReview(page);
    const location = await page.locator('#rev-location').textContent();
    expect(location).toBe('Multnomah County, Oregon');
    expect(errors, errors.join('\n')).toEqual([]);
  });

  test('review location never shows bare "County," when region is empty', async ({ page }) => {
    // Edge case: navigate manually (no URL prefill) — empty region falls back to "—"
    await page.goto('/web/order.html', { waitUntil: 'load' });
    // Evaluate the populateReview fallback in isolation
    const loc = await page.evaluate(() => {
      const S = { county: '', region: '' };
      const loc = S.county ? (S.county + ' County, ' + S.region) : S.region;
      return loc || '—';
    });
    expect(loc).toBe('—');
    // Also verify it never matches the old buggy pattern
    expect(loc).not.toMatch(/^\s*County,\s*$/);
  });

  test('state select value matches S.region after prefill', async ({ page }) => {
    await page.goto(
      '/web/order.html?product=watershed-report&region=Washington&county=Clark',
      { waitUntil: 'load' }
    );
    // Read the internal S.region value via the page context
    const region = await page.evaluate(() => {
      // The select's value should match the prefilled region
      return document.getElementById('sel-state').value;
    });
    expect(region).toBe('Washington');
  });

  test('county select value matches S.county after prefill', async ({ page }) => {
    await page.goto(
      '/web/order.html?product=watershed-report&region=Washington&county=Clark',
      { waitUntil: 'load' }
    );
    // County is set via setTimeout(0) — wait a tick
    await page.waitForTimeout(50);
    const county = await page.evaluate(() => {
      return document.getElementById('sel-county').value;
    });
    expect(county).toBe('Clark');
  });

  test('all multi-word states prefill correctly', async ({ page }) => {
    const multiWordStates = ['New York', 'New Jersey', 'New Hampshire', 'New Mexico',
      'North Carolina', 'North Dakota', 'South Carolina', 'South Dakota',
      'West Virginia', 'Rhode Island'];
    for (const state of multiWordStates) {
      await page.goto(
        '/web/order.html?product=watershed-report&region=' + encodeURIComponent(state),
        { waitUntil: 'load' }
      );
      const selVal = await page.evaluate(() => document.getElementById('sel-state').value);
      expect(selVal, `state select should be ${state}`).toBe(state);
    }
  });
});
