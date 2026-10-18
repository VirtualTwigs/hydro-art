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
// Chrome emits a generic "Failed to load resource: …404…" console error for
// any asset that 404s — including optional gallery images that have onerror
// fallbacks on start.html.  These fire during navigation (lazy-load race) and
// carry no URL, so we can't filter by path.  Exclude the network-level 404
// messages entirely; real asset-resolution tests (landing art, order scripts)
// use explicit response-status checks instead.
function trackErrors(page) {
  const errors = [];
  page.on('console', (m) => {
    if (m.type() === 'error') {
      const text = m.text();
      if (text.includes('Failed to load resource')) return;
      errors.push(`console: ${text}`);
    }
  });
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
  return errors;
}

test.describe('Alpha landing (#95, #96)', () => {
  test('missing artwork displays placeholders without removing card links', async ({ page }) => {
    await page.route('**/output/**', (route) => route.fulfill({ status: 404 }));
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.goto('/web/start.html', { waitUntil: 'load' });

    const cards = page.locator('#catalog-grid article');
    for (let index = 0; index < await cards.count(); index++) {
      const card = cards.nth(index);
      await card.scrollIntoViewIfNeeded();
      await expect(card.locator('.img-placeholder')).toBeVisible();
      await expect(card.locator('.img-placeholder')).toHaveText('Artwork preview unavailable');
      await expect(card.locator('a.cover')).toHaveAttribute('href', /\S+/);
    }
    const gallery = page.locator('img[src*="conus-neon-hero"]').locator('..');
    await gallery.scrollIntoViewIfNeeded();
    await expect(gallery.locator('.img-placeholder')).toBeVisible();
    expect(errors).toEqual([]);
  });

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
    await expect(page.locator('.mark .logo')).toBeVisible();
  });

  test('Riverglyph wordmark visible at mobile width (375px)', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/web/start.html', { waitUntil: 'load' });
    await expect(page.locator('.mark .logo')).toBeVisible();
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

  // --- Lightbox tests (Group 3) ---

  for (const { card, page: dest } of CATALOG) {
    test(`catalog "${card}" thumb click opens lightbox with image`, async ({ page }) => {
      const errors = trackErrors(page);
      await page.goto('/web/start.html', { waitUntil: 'load' });
      const article = page.locator('#catalog-grid article', { has: page.getByRole('heading', { name: card }) });
      await article.scrollIntoViewIfNeeded();

      // Click the thumb area — should open the lightbox, not navigate.
      await article.locator('.thumb').click();
      await expect(page.locator('#lightbox')).toBeVisible();

      // The lightbox image src should match the card's thumb image src.
      const cardImgSrc = await article.locator('.thumb img').getAttribute('src');
      const lightboxImgSrc = await page.locator('#lightbox img').getAttribute('src');
      expect(lightboxImgSrc).toBe(cardImgSrc);

      expect(errors, errors.join('\n')).toEqual([]);
    });
  }

  test('lightbox CTA href matches the card order URL', async ({ page }) => {
    await page.goto('/web/start.html', { waitUntil: 'load' });
    for (const { card, page: dest } of CATALOG) {
      const article = page.locator('#catalog-grid article', { has: page.getByRole('heading', { name: card }) });
      await article.scrollIntoViewIfNeeded();
      await article.locator('.thumb').click();
      await expect(page.locator('#lightbox')).toBeVisible();

      // The CTA link in the lightbox should resolve to the card's order page.
      const ctaHref = await page.locator('#lightbox a.lightbox-cta').getAttribute('href');
      const coverHref = await article.locator('a.cover').getAttribute('href');
      expect(ctaHref).toBe(coverHref);

      // Close lightbox before testing the next card.
      await page.keyboard.press('Escape');
      await expect(page.locator('#lightbox')).not.toBeVisible();
    }
  });

  test('lightbox closes on Escape keypress', async ({ page }) => {
    await page.goto('/web/start.html', { waitUntil: 'load' });
    const article = page.locator('#catalog-grid article').first();
    await article.scrollIntoViewIfNeeded();
    await article.locator('.thumb').click();
    await expect(page.locator('#lightbox')).toBeVisible();

    await page.keyboard.press('Escape');
    await expect(page.locator('#lightbox')).not.toBeVisible();
  });

  test('lightbox closes on backdrop click', async ({ page }) => {
    await page.goto('/web/start.html', { waitUntil: 'load' });
    const article = page.locator('#catalog-grid article').first();
    await article.scrollIntoViewIfNeeded();
    await article.locator('.thumb').click();
    await expect(page.locator('#lightbox')).toBeVisible();

    // Click the backdrop (top-left corner of the overlay, away from the image).
    await page.locator('#lightbox').click({ position: { x: 5, y: 5 } });
    await expect(page.locator('#lightbox')).not.toBeVisible();
  });

  test('placeholder cards navigate directly without lightbox', async ({ page }) => {
    // Force all images to 404 so every card shows a placeholder.
    await page.route('**/output/**', (route) => route.fulfill({ status: 404 }));
    await page.goto('/web/start.html', { waitUntil: 'load' });

    const { card, page: dest } = CATALOG[0];
    const article = page.locator('#catalog-grid article', { has: page.getByRole('heading', { name: card }) });
    await article.scrollIntoViewIfNeeded();
    await expect(article.locator('.img-placeholder')).toBeVisible();

    // Clicking the thumb area on a placeholder card should navigate, not open lightbox.
    await Promise.all([
      page.waitForURL(`**${dest.replace(/\?.*/, '')}*`),
      article.locator('.thumb').click(),
    ]);
    // Lightbox should NOT be visible (we navigated away).
    // If we got here, waitForURL succeeded — the card navigated as expected.
  });

  // The cover link still exists and navigates when clicked in the body area.
  // .thumb (z-index:3) intercepts clicks in the image region for the lightbox,
  // but .cover (z-index:2) still handles clicks in the body region below.
  for (const { card, page: dest } of CATALOG) {
    test(`catalog "${card}" cover link navigates without JS errors`, async ({ page }) => {
      const errors = trackErrors(page);
      await page.goto('/web/start.html', { waitUntil: 'load' });
      const article = page.locator('#catalog-grid article', { has: page.getByRole('heading', { name: card }) });
      await article.scrollIntoViewIfNeeded();
      // Click the cover link's lower region (body area) where .thumb doesn't intercept.
      // Use the card's heading as a reliable click target in the body zone.
      await Promise.all([
        page.waitForURL(`**${dest.replace(/\?.*/, '')}*`),
        article.getByRole('heading', { name: card }).click({ force: true }),
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

  test('state dropdown populates with all 50 states', async ({ page }) => {
    await page.goto('/web/order.html', { waitUntil: 'networkidle' });
    // Advance to step 2 by clicking a product card
    await page.click('[data-product="digital-image"]');
    await page.waitForTimeout(300);
    const optionCount = await page.locator('#sel-state option').count();
    // Placeholder + 50 states = 51
    expect(optionCount).toBeGreaterThanOrEqual(51);
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
