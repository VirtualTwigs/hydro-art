// #95 smoke + #96 landing/navigation e2e for the alpha customer site (web/start.html).
// These run without the GIS stack — they only exercise static delivery + client JS.
const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');
const { CATALOG } = require('../helpers');

// global-setup.js stages a real served root from deploy/output/, so /output/landing/*
// maps to deploy/output/landing/*. Those WebP assets come from deploy/stage-artifacts.sh;
// skip the asset check when they haven't been staged there yet.
const REPO_ROOT = path.resolve(__dirname, '..', '..', '..');
const LANDING_DIR = path.join(REPO_ROOT, 'deploy', 'output', 'landing');

// Collect console errors + uncaught page errors on the current page.
function trackErrors(page) {
  const errors = [];
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(`console: ${m.text()}`);
  });
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
  return errors;
}

test.describe('Alpha landing (#95, #96)', () => {
  test('start.html loads with no console errors', async ({ page }) => {
    const errors = trackErrors(page);
    const resp = await page.goto('/web/start.html', { waitUntil: 'load' });
    expect(resp?.status()).toBe(200);
    await expect(page).toHaveTitle(/Riverglyph/i);
    await expect(page.locator('h1.head')).toBeVisible();
    expect(errors, errors.join('\n')).toEqual([]);
  });

  test('Riverglyph wordmark visible at desktop width (1280px)', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto('/web/start.html', { waitUntil: 'load' });
    await expect(page.getByText('Riverglyph').first()).toBeVisible();
  });

  test('Riverglyph wordmark visible at mobile width (375px)', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/web/start.html', { waitUntil: 'load' });
    await expect(page.getByText('Riverglyph').first()).toBeVisible();
  });

  test('landing art + font assets resolve (no 404s)', async ({ page }) => {
    test.skip(
      !fs.existsSync(LANDING_DIR),
      'landing assets not staged at the served root — run deploy/stage-artifacts.sh (or mount the NAS) so /output/landing/* resolves'
    );
    const failed = [];
    page.on('response', (r) => {
      const u = r.url();
      const asset = u.includes('/output/landing/') || u.includes('/shared/fonts/');
      if (asset && r.status() >= 400) failed.push(`${r.status()} ${u}`);
    });
    await page.goto('/web/start.html', { waitUntil: 'networkidle' });
    expect(failed, failed.join('\n')).toEqual([]);
  });

  test('catalog shows the four endpoint cards + how-it-works', async ({ page }) => {
    await page.goto('/web/start.html');
    await expect(page.locator('#catalog-grid .card')).toHaveCount(4);
    for (const { card } of CATALOG) {
      await expect(
        page.locator('#catalog-grid').getByRole('heading', { name: card })
      ).toBeVisible();
    }
    await expect(page.locator('.steps .step')).toHaveCount(3);
  });

  for (const { card, page: dest } of CATALOG) {
    test(`catalog "${card}" link navigates without JS errors`, async ({ page }) => {
      const errors = trackErrors(page);
      await page.goto('/web/start.html', { waitUntil: 'load' });
      // Find the card by its heading, then click the cover link in the same article.
      const article = page.locator('#catalog-grid article', { has: page.getByRole('heading', { name: card }) });
      await Promise.all([
        page.waitForURL(`**${dest.replace(/\?.*/, '')}*`),
        article.locator('a.cover').click(),
      ]);
      await page.waitForLoadState('load');
      expect(errors, errors.join('\n')).toEqual([]);
    });
  }

  test('gallery link resolves', async ({ page }) => {
    const resp = await page.goto('/web/gallery.html', { waitUntil: 'load' });
    expect(resp?.status()).toBe(200);
  });
});

test.describe('Order form (#138, #140)', () => {
  test('order.html loads with no console errors', async ({ page }) => {
    const errors = trackErrors(page);
    const resp = await page.goto('/web/order.html', { waitUntil: 'load' });
    expect(resp?.status()).toBe(200);
    await expect(page).toHaveTitle(/Riverglyph/i);
    expect(errors, errors.join('\n')).toEqual([]);
  });

  test('hydro-ux.js loads and HydroUX is available', async ({ page }) => {
    const errors = trackErrors(page);
    await page.goto('/web/order.html', { waitUntil: 'networkidle' });
    const hasHydroUX = await page.evaluate(() => typeof window.HydroUX === 'object');
    expect(hasHydroUX, 'HydroUX should be on window').toBe(true);
    expect(errors, errors.join('\n')).toEqual([]);
  });

  test('state dropdown populates with at least 4 states', async ({ page }) => {
    await page.goto('/web/order.html', { waitUntil: 'networkidle' });
    // Advance to step 2 by clicking a product card
    await page.click('[data-product="digital-image"]');
    await page.waitForTimeout(300);
    const optionCount = await page.locator('#sel-state option').count();
    // Placeholder + at least OR/WA/CA/ID = 5+
    expect(optionCount).toBeGreaterThanOrEqual(5);
  });

  test('selecting a state populates the county dropdown', async ({ page }) => {
    await page.goto('/web/order.html', { waitUntil: 'networkidle' });
    await page.click('[data-product="digital-image"]');
    await page.waitForTimeout(300);
    await page.selectOption('#sel-state', 'Washington');
    const countyCount = await page.locator('#sel-county option').count();
    // Placeholder + at least some counties
    expect(countyCount).toBeGreaterThanOrEqual(2);
    const disabled = await page.locator('#sel-county').isDisabled();
    expect(disabled).toBe(false);
  });

  test('no 404s on order page scripts and fonts', async ({ page }) => {
    const failed = [];
    page.on('response', (r) => {
      const u = r.url();
      const asset = u.includes('hydro-ux.js') || u.includes('/shared/fonts/') || u.includes('.css');
      if (asset && r.status() >= 400) failed.push(`${r.status()} ${u}`);
    });
    await page.goto('/web/order.html', { waitUntil: 'networkidle' });
    expect(failed, failed.join('\n')).toEqual([]);
  });
});
