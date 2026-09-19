// Global setup — stage a REAL served web-root for serve.py.
//
// Why this exists: serve.py's static handler resolves symlinks and refuses any
// path that escapes --web-root (src/server.py path-traversal guard). The repo's
// own output/ is a symlink to the NAS, so serving the repo root directly makes
// every /output/landing/*.webp 404 — which trips the landing suite's strict
// "no console errors" assertions.
//
// The real container deploy sidesteps this by bind-mounting deploy/output (a real
// dir) at /output. We mirror that here: copy web/ + deploy/output/ into a real
// staging dir with no escaping symlinks, and serve THAT. Cheap (web/ is ~750K).
//
// playwright.config.js calls stage() at config-load time (NOT via the globalSetup
// hook): Playwright awaits the webServer's readiness probe before running
// globalSetup, so staging there would be too late — the probe would 404 and time
// out. Config load runs first, so the root is populated before serve.py launches.
const fs = require('fs');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '..', '..');
const SERVED_ROOT = path.join(__dirname, '.served-root');

function stage() {
  fs.rmSync(SERVED_ROOT, { recursive: true, force: true });
  fs.mkdirSync(SERVED_ROOT, { recursive: true });

  // /web/* — the customer pages + shared css/js/fonts (real files, no symlinks).
  // Use dereference: true to follow any symlinks and avoid chmod failures on
  // files with extended attributes (macOS xattr from the brand SVG assets).
  fs.cpSync(path.join(REPO_ROOT, 'web'), path.join(SERVED_ROOT, 'web'), {
    recursive: true, dereference: true,
  });

  // /output/* — landing WebP assets + display SVGs the viewer pages fetch. These
  // are the web-optimized copies deploy/stage-artifacts.sh produces; if they are
  // not staged yet, the landing-asset test skips (see 01-landing.spec.js).
  const deployOut = path.join(REPO_ROOT, 'deploy', 'output');
  if (fs.existsSync(deployOut)) {
    fs.cpSync(deployOut, path.join(SERVED_ROOT, 'output'), { recursive: true });
  } else {
    fs.mkdirSync(path.join(SERVED_ROOT, 'output'), { recursive: true });
  }
}

module.exports = async () => {
  stage();
};

module.exports.SERVED_ROOT = SERVED_ROOT;
module.exports.stage = stage;
