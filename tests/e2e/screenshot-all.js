const { chromium } = require('playwright');

const PAGES = [
  { name: 'start',          path: '/start.html' },
  { name: 'order-step1',    path: '/order.html' },
  { name: 'riverglyph',     path: '/riverglyph.html' },
  { name: 'gallery',        path: '/gallery.html' },
  { name: 'studio',         path: '/studio.html' },
  { name: 'report',         path: '/report.html' },
  { name: 'delivery',       path: '/delivery.html' },
  { name: 'ops',            path: '/ops.html' },
  { name: 'proof',          path: '/proof.html' },
  { name: 'proto-b-guided', path: '/proto-b-guided.html' },
  { name: 'proto-c-canvas', path: '/proto-c-canvas.html' },
];

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });

  for (const pg of PAGES) {
    const page = await ctx.newPage();
    try {
      await page.goto('http://127.0.0.1:8765' + pg.path, { waitUntil: 'networkidle', timeout: 8000 });
    } catch (e) {
      // networkidle may timeout on API-dependent pages, that's ok
      await page.waitForTimeout(1000);
    }
    await page.screenshot({
      path: '/Users/neilrunde/code/hydro-art/screenshots/' + pg.name + '.png',
      fullPage: true,
    });
    console.log('captured: ' + pg.name);
    await page.close();
  }

  await browser.close();
  console.log('done');
})();
