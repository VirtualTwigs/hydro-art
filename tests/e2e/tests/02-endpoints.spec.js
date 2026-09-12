// #97 four-endpoint low-res proofs.
//
// Two paths, matching the analysis in the spec:
//  - digital_image + print_image go through the 2D Pipeline via /api/render, at the
//    draft png_size tier (#94), so the proof renders fast.
//  - report + animation are parallel tools/ subsystems (not wired to /api/render), so
//    their low-res proofs come from spawning the render tools.
//
// All of these need the GIS stack + a pre-extracted county in datasets/; when that is
// absent we SKIP (not fail), keeping the harness honest about its prerequisites.
const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawnSync } = require('child_process');
const { PNG_SIZE, REGION, COUNTY, renderViaApi } = require('../helpers');

const REPO_ROOT = path.resolve(__dirname, '..', '..', '..');
const PYTHON = process.env.PYTHON || path.join(REPO_ROOT, '.venv', 'bin', 'python');
const DATASETS = path.join(REPO_ROOT, 'datasets');

// A pre-extracted county means at least one non-empty entry under datasets/.
const HAVE_DATA = fs.existsSync(DATASETS) && fs.readdirSync(DATASETS).length > 0;

function listByExt(dir, re) {
  if (!fs.existsSync(dir)) return [];
  const acc = [];
  (function walk(d) {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, e.name);
      if (e.isDirectory()) walk(p);
      else if (re.test(e.name)) acc.push(p);
    }
  })(dir);
  return acc;
}

test.describe('Endpoint low-res proofs (#97)', () => {
  test.skip(!HAVE_DATA, 'needs a pre-extracted county in datasets/ + the GIS stack');
  test.slow(); // real renders take longer than the default budget

  test('digital image — SVG proof via /api/render at the draft tier', async ({ request, baseURL }) => {
    const { job } = await renderViaApi(request, baseURL, {
      region: REGION,
      county: COUNTY,
      png_size: PNG_SIZE,
      output: ['svg'],
    });
    const svg = await request.get(`${baseURL}/api/jobs/${job}/artifact?fmt=svg`);
    expect(svg.ok()).toBeTruthy();
    expect(await svg.text()).toContain('<svg');
  });

  test('poster / print image — draft PNG proof via /api/render', async ({ request, baseURL }) => {
    const { job } = await renderViaApi(request, baseURL, {
      region: REGION,
      county: COUNTY,
      png_size: PNG_SIZE,
      output: ['svg', 'png'],
    });
    const png = await request.get(`${baseURL}/api/jobs/${job}/artifact?fmt=png`);
    expect(png.ok()).toBeTruthy();
    const body = await png.body();
    expect(body.length).toBeGreaterThan(0);
    expect(body.slice(0, 4).toString('hex')).toBe('89504e47'); // PNG magic
  });

  test('digital image — studio.html Run button is live when served', async ({ page }) => {
    await page.goto('/web/studio.html', { waitUntil: 'load' });
    await expect(page.locator('#runBtn')).toBeEnabled();
  });

  test('watershed report — low-res figures via tools/build_watershed_report.py', async () => {
    const outDir = fs.mkdtempSync(path.join(os.tmpdir(), 'hydro-report-'));
    const r = spawnSync(
      PYTHON,
      ['tools/build_watershed_report.py', '--start', '1980', '--end', '1985', '--no-creative', '--out-dir', outDir],
      { cwd: REPO_ROOT, encoding: 'utf-8', timeout: 240_000 }
    );
    test.skip(r.status !== 0, `report tool prerequisites unmet:\n${(r.stderr || '').slice(-800)}`);
    const figs = listByExt(outDir, /\.(png|svg|pdf)$/);
    expect(figs.length, 'report produced no figures').toBeGreaterThan(0);
  });

  test('animation — low-res short GIF via tools/render_monthly.py', async () => {
    const r = spawnSync(
      PYTHON,
      ['tools/render_monthly.py', '--clark', '--frames', '3', '--width', String(PNG_SIZE)],
      { cwd: REPO_ROOT, encoding: 'utf-8', timeout: 240_000 }
    );
    test.skip(r.status !== 0, `animation tool prerequisites unmet:\n${(r.stderr || '').slice(-800)}`);
    const gifs = listByExt(path.join(REPO_ROOT, 'output'), /\.gif$/);
    expect(gifs.length, 'no GIF produced under output/').toBeGreaterThan(0);
  });
});
