// Playwright config — alpha customer-journey e2e (Epoch 24, roadmap #95–#98).
//
// NON-OFFLINE / OPT-IN. This suite is intentionally NOT part of the Python offline
// test suite: it boots a live `serve.py` and (for #97) drives real GDAL renders, so
// it needs the GIS stack + a pre-extracted county in `datasets/`. See README.md.
//
// The server is launched with `--web-root <staged>` so `web/start.html`'s
// repo-root-absolute assets (`/web/...`, `/output/...`) AND the `/api/*` render routes
// are all served same-origin — the landing journey and the render backend coexist.
// `global-setup.js` stages that root with REAL (non-symlinked) files, because the
// repo's own output/ is a NAS symlink that serve.py's path-traversal guard refuses.
const { defineConfig, devices } = require('@playwright/test');
const path = require('path');
const { SERVED_ROOT, stage } = require('./global-setup');

// Stage the served root NOW, at config load — Playwright awaits the webServer's
// readiness (a GET on /web/start.html) BEFORE running globalSetup, so staging in
// globalSetup would be too late and readiness would 404-timeout. Config load runs
// first, so the root is populated before serve.py launches.
stage();

const PORT = Number(process.env.PORT || 8080);
const BASE_URL = process.env.BASE_URL || `http://127.0.0.1:${PORT}`;
const REPO_ROOT = path.resolve(__dirname, '..', '..');
const PYTHON = process.env.PYTHON || path.join(REPO_ROOT, '.venv', 'bin', 'python');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  // Launch the real control-surface server (with /api) rooted at the repo. Set
  // BASE_URL to reuse an already-running serve.py instead (must expose /api).
  webServer: {
    command: `${PYTHON} serve.py --web-root ${SERVED_ROOT} --port ${PORT}`,
    cwd: REPO_ROOT,
    url: `${BASE_URL}/web/start.html`,
    reuseExistingServer: !!process.env.BASE_URL,
    timeout: 120_000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
});
