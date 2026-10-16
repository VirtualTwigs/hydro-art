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
const { execSync } = require('child_process');

const REPO_ROOT = path.resolve(__dirname, '..', '..');
const SERVED_ROOT = path.join(__dirname, '.served-root');

function stage() {
  // Shell rm + mkdir: fs.rmSync can fail with ENOTEMPTY on macOS when files
  // carry SIP-protected extended attributes (com.apple.provenance).
  execSync(`rm -rf "${SERVED_ROOT}"`);
  fs.mkdirSync(SERVED_ROOT, { recursive: true });

  // /web/* — the customer pages + shared css/js/fonts (real files, no symlinks).
  // Shell cp -RL for the same macOS xattr reason as /output below.
  const servedWeb = path.join(SERVED_ROOT, 'web');
  fs.mkdirSync(servedWeb, { recursive: true });
  execSync(`cp -RL "${path.join(REPO_ROOT, 'web')}/." "${servedWeb}/"`);

  // /output/* — landing WebP assets + display SVGs the viewer pages fetch. These
  // are the web-optimized copies deploy/stage-artifacts.sh produces; if they are
  // not staged yet, the landing-asset test skips (see 01-landing.spec.js).
  //
  // Shell cp -R instead of fs.cpSync: macOS com.apple.provenance xattr (SIP-
  // protected, can't be stripped) makes Node's cpSync fail with ENOENT during
  // chmodSync on files that carry it (e.g. large SVGs from the NAS).
  const deployOut = path.join(REPO_ROOT, 'deploy', 'output');
  const servedOutput = path.join(SERVED_ROOT, 'output');
  if (fs.existsSync(deployOut)) {
    fs.mkdirSync(servedOutput, { recursive: true });
    execSync(`cp -RL "${deployOut}/." "${servedOutput}/"`);
  } else {
    fs.mkdirSync(servedOutput, { recursive: true });
  }
}

module.exports = async () => {
  stage();
};

module.exports.SERVED_ROOT = SERVED_ROOT;
module.exports.stage = stage;
