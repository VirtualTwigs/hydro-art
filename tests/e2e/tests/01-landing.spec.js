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
      const asset = u.includes('/output/landing/') || u.includes('/web/shared/fonts/');
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
    test(`catalog "${card}" link navigates to ${dest} without JS errors`, async ({ page }) => {
      const errors = trackErrors(page);
      await page.goto('/web/start.html', { waitUntil: 'load' });
      await Promise.all([
        page.waitForURL(`**${dest}`),
        page.locator(`#catalog-grid a.cover[href="${dest}"]`).click(),
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
