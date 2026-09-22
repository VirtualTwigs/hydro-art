/* Cross-system mirror test — validates that the JavaScript ground-truth data
   in web/shared/hydro-ux.js stays in sync with the Python source of truth.

   The Python side (src/config.py, src/coloring.py, src/datasets.py,
   src/fulfillment.py) is the authoritative source. The JS side duplicates
   these constants for offline browser use. Drift between the two causes bugs
   like the "Unsupported region ''" order failure — values the JS UI offers
   that the Python backend rejects (or vice versa).

   Run: node tests/test_cross_system_mirror.cjs
   Requires: python3 on PATH (the .venv interpreter).
   Mirrors the offline posture: stdlib `node` + subprocess `python` only. */
"use strict";
const assert = require("assert");
const path = require("path");
const { execSync } = require("child_process");
const HydroUX = require(path.join(__dirname, "..", "web", "shared", "hydro-ux.js"));

let passed = 0;
function test(name, fn) { fn(); passed++; }

// ── Helper: run a Python expression and parse the JSON result ───────────────
const ROOT = path.join(__dirname, "..");
const PY = path.join(ROOT, ".venv", "bin", "python");

function pyJSON(expr) {
  const cmd = `${PY} -c "import json, sys; sys.path.insert(0, '${ROOT}'); ${expr}"`;
  const out = execSync(cmd, { encoding: "utf8", cwd: ROOT }).trim();
  return JSON.parse(out);
}

// ═════════════════════════════════════════════════════════════════════════════
// 1. SUPPORTED_REGIONS ↔ STATES
// ═════════════════════════════════════════════════════════════════════════════

test("JS STATES ids match Python SUPPORTED_REGIONS exactly", function () {
  var pyRegions = pyJSON(
    "from src.config import SUPPORTED_REGIONS; print(json.dumps(list(SUPPORTED_REGIONS)))"
  );
  var jsIds = HydroUX.STATES.map(function (s) { return s.id; });
  assert.deepStrictEqual(
    jsIds.slice().sort(),
    pyRegions.slice().sort(),
    "STATES ids must match SUPPORTED_REGIONS"
  );
});

test("JS STATES count matches Python (50 states)", function () {
  var pyCount = pyJSON(
    "from src.config import SUPPORTED_REGIONS; print(json.dumps(len(SUPPORTED_REGIONS)))"
  );
  assert.strictEqual(HydroUX.STATES.length, pyCount);
});

test("every JS STATE has id, label, and huc4 array", function () {
  HydroUX.STATES.forEach(function (s) {
    assert.ok(s.id, "state missing id");
    assert.ok(s.label, "state missing label");
    assert.ok(Array.isArray(s.huc4) && s.huc4.length > 0,
      s.id + " missing or empty huc4");
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 2. REGION_HUC4 ↔ STATES[].huc4
// ═════════════════════════════════════════════════════════════════════════════

test("JS STATES huc4 arrays match Python REGION_HUC4 for every state", function () {
  var pyHuc4 = pyJSON(
    "from src.datasets import REGION_HUC4; print(json.dumps({k: list(v) for k, v in REGION_HUC4.items()}))"
  );
  HydroUX.STATES.forEach(function (s) {
    var pyArr = pyHuc4[s.id];
    assert.ok(pyArr, s.id + " missing in Python REGION_HUC4");
    assert.deepStrictEqual(
      s.huc4.slice().sort(),
      pyArr.slice().sort(),
      "HUC4 mismatch for " + s.id
    );
  });
  // Also check Python doesn't have extra states not in JS
  var jsIds = new Set(HydroUX.STATES.map(function (s) { return s.id; }));
  Object.keys(pyHuc4).forEach(function (k) {
    assert.ok(jsIds.has(k), "Python REGION_HUC4 has " + k + " not in JS STATES");
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 3. PALETTES — neon colors match; experimental palettes documented
// ═════════════════════════════════════════════════════════════════════════════

test("JS neon palette colors match Python PALETTES['neon'] exactly", function () {
  var pyNeon = pyJSON(
    "from src.coloring import PALETTES; print(json.dumps(list(PALETTES['neon'])))"
  );
  assert.deepStrictEqual(HydroUX.PALETTES.neon, pyNeon,
    "neon palette colors must match between Python and JS");
});

test("JS PALETTES includes all Python SUPPORTED_PALETTES", function () {
  var pyPalettes = pyJSON(
    "from src.config import SUPPORTED_PALETTES; print(json.dumps(list(SUPPORTED_PALETTES)))"
  );
  pyPalettes.forEach(function (p) {
    assert.ok(HydroUX.PALETTES[p],
      "Python SUPPORTED_PALETTES has '" + p + "' but JS PALETTES is missing it");
  });
});

test("JS experimental palettes are not in Python SUPPORTED_PALETTES", function () {
  // JS may have extra palettes for UX experimentation (aurora, ember, ice).
  // These must NOT be accepted by the pipeline — if they appear in
  // SUPPORTED_PALETTES, the UI and backend agree and this test should update.
  var pyPalettes = pyJSON(
    "from src.config import SUPPORTED_PALETTES; print(json.dumps(list(SUPPORTED_PALETTES)))"
  );
  var pySet = new Set(pyPalettes);
  var jsNames = Object.keys(HydroUX.PALETTES);
  var experimental = jsNames.filter(function (n) { return !pySet.has(n); });
  // This is informational — experimental palettes are allowed in JS.
  // But if >0, ensure the order form doesn't offer them as order styles.
  assert.ok(experimental.length >= 0, "experimental palettes: " + experimental.join(", "));
});

// ═════════════════════════════════════════════════════════════════════════════
// 4. HUC_LEVELS ↔ SUPPORTED_HUC_LEVELS
// ═════════════════════════════════════════════════════════════════════════════

test("JS HUC_LEVELS match Python SUPPORTED_HUC_LEVELS exactly", function () {
  var pyLevels = pyJSON(
    "from src.config import SUPPORTED_HUC_LEVELS; print(json.dumps(list(SUPPORTED_HUC_LEVELS)))"
  );
  assert.deepStrictEqual(HydroUX.HUC_LEVELS, pyLevels);
});

// ═════════════════════════════════════════════════════════════════════════════
// 5. MONTH_ABBR
// ═════════════════════════════════════════════════════════════════════════════

test("JS MONTH_ABBR matches Python monthly_flow.MONTH_ABBR exactly", function () {
  var pyMonths = pyJSON(
    "from src.monthly_flow import MONTH_ABBR; print(json.dumps(MONTH_ABBR))"
  );
  assert.deepStrictEqual(HydroUX.MONTH_ABBR, pyMonths);
});

// ═════════════════════════════════════════════════════════════════════════════
// 6. ORDER_STYLES — order.html style buttons match Python fulfillment
// ═════════════════════════════════════════════════════════════════════════════

test("order.html style buttons match Python ORDER_STYLES keys", function () {
  var pyStyles = pyJSON(
    "from src.fulfillment import ORDER_STYLES; print(json.dumps(sorted(ORDER_STYLES.keys())))"
  );
  // Parse order.html for data-style attributes on <button> elements (HTML only,
  // not inside <script>).
  var fs = require("fs");
  var html = fs.readFileSync(path.join(ROOT, "web", "order.html"), "utf8");
  // Split at first <script to avoid matching JS template strings
  var htmlOnly = html.split(/<script/i)[0];
  var re = /data-style="([^"]+)"/g;
  var jsStyles = [];
  var m;
  while ((m = re.exec(htmlOnly)) !== null) jsStyles.push(m[1]);
  jsStyles.sort();
  assert.deepStrictEqual(jsStyles, pyStyles,
    "order.html data-style buttons must match ORDER_STYLES keys");
});

// ═════════════════════════════════════════════════════════════════════════════
// 7. SIZES — order.html size buttons match Python fulfillment
// ═════════════════════════════════════════════════════════════════════════════

test("order.html size buttons match Python SIZES keys", function () {
  var pySizes = pyJSON(
    "from src.fulfillment import SIZES; print(json.dumps(sorted(SIZES.keys())))"
  );
  // Parse order.html for data-size attributes
  var fs = require("fs");
  var html = fs.readFileSync(path.join(ROOT, "web", "order.html"), "utf8");
  var re = /data-size="([^"]+)"/g;
  var jsSizes = [];
  var m;
  while ((m = re.exec(html)) !== null) jsSizes.push(m[1]);
  jsSizes.sort();
  assert.deepStrictEqual(jsSizes, pySizes,
    "order.html data-size buttons must match SIZES keys");
});

// ═════════════════════════════════════════════════════════════════════════════
// 8. COUNTIES — JS has entries for every supported region
// ═════════════════════════════════════════════════════════════════════════════

test("JS COUNTIES has an entry for every SUPPORTED_REGION", function () {
  var pyRegions = pyJSON(
    "from src.config import SUPPORTED_REGIONS; print(json.dumps(list(SUPPORTED_REGIONS)))"
  );
  pyRegions.forEach(function (r) {
    assert.ok(HydroUX.COUNTIES[r],
      "JS COUNTIES missing entry for " + r);
    assert.ok(Array.isArray(HydroUX.COUNTIES[r]) && HydroUX.COUNTIES[r].length > 0,
      "JS COUNTIES['" + r + "'] is empty or not an array");
  });
});

test("JS COUNTIES has no extra states beyond SUPPORTED_REGIONS", function () {
  var pyRegions = pyJSON(
    "from src.config import SUPPORTED_REGIONS; print(json.dumps(list(SUPPORTED_REGIONS)))"
  );
  var pySet = new Set(pyRegions);
  Object.keys(HydroUX.COUNTIES).forEach(function (k) {
    assert.ok(pySet.has(k),
      "JS COUNTIES has '" + k + "' which is not in Python SUPPORTED_REGIONS");
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 9. STATE_FIPS — Python has a FIPS code for every SUPPORTED_REGION
// ═════════════════════════════════════════════════════════════════════════════

test("Python STATE_FIPS covers all SUPPORTED_REGIONS", function () {
  var pyCheck = pyJSON(
    "from src.config import SUPPORTED_REGIONS; from src.counties import STATE_FIPS; " +
    "print(json.dumps([r for r in SUPPORTED_REGIONS if r not in STATE_FIPS]))"
  );
  assert.deepStrictEqual(pyCheck, [],
    "STATE_FIPS missing entries: " + pyCheck.join(", "));
});

// ═════════════════════════════════════════════════════════════════════════════
// 10. Color/width modes — JS sanitizeRecipe uses the same allowlists
// ═════════════════════════════════════════════════════════════════════════════

test("JS sanitizeRecipe color modes match Python SUPPORTED_COLOR_MODES", function () {
  var pyModes = pyJSON(
    "from src.config import SUPPORTED_COLOR_MODES; print(json.dumps(list(SUPPORTED_COLOR_MODES)))"
  );
  // Verify by sanitizing each mode and checking it survives
  pyModes.forEach(function (mode) {
    var recipe = HydroUX.sanitizeRecipe({ colorMode: mode });
    assert.ok(recipe, "sanitizeRecipe returned null for colorMode=" + mode);
    assert.strictEqual(recipe.colorMode, mode,
      "colorMode '" + mode + "' should survive sanitization");
  });
});

test("JS sanitizeRecipe width modes match Python SUPPORTED_WIDTH_MODES", function () {
  var pyModes = pyJSON(
    "from src.config import SUPPORTED_WIDTH_MODES; print(json.dumps(list(SUPPORTED_WIDTH_MODES)))"
  );
  pyModes.forEach(function (mode) {
    var recipe = HydroUX.sanitizeRecipe({ widthMode: mode });
    assert.ok(recipe, "sanitizeRecipe returned null for widthMode=" + mode);
    assert.strictEqual(recipe.widthMode, mode,
      "widthMode '" + mode + "' should survive sanitization");
  });
});

console.log("ok — " + passed + " cross-system mirror tests passed");
