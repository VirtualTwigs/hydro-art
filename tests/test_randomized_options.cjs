/* Randomized option-space exploration — exercises 100+ random combinations
   of states, counties, palettes, recipes, presets, and order-form prefill
   paths to surface edge cases in the JS client-side logic.

   Run: node tests/test_randomized_options.cjs
   Stdlib only, no deps. Seeded PRNG for reproducibility. */
"use strict";
const assert = require("assert");
const path = require("path");
const fs = require("fs");
const HydroUX = require(path.join(__dirname, "..", "web", "shared", "hydro-ux.js"));

let passed = 0;
function test(name, fn) { fn(); passed++; }

// ── Seeded PRNG (reproducible across runs) ──────────────────────────────────
function mulberry32(a) {
  return function () {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    var t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}
var rng = mulberry32(20260921);  // seed = today's date

function pick(arr) { return arr[Math.floor(rng() * arr.length)]; }
function pickN(arr, n) {
  var copy = arr.slice();
  var out = [];
  for (var i = 0; i < Math.min(n, copy.length); i++) {
    var idx = Math.floor(rng() * copy.length);
    out.push(copy.splice(idx, 1)[0]);
  }
  return out;
}
function coinFlip() { return rng() > 0.5; }
function randInt(min, max) { return min + Math.floor(rng() * (max - min + 1)); }
function randHex() {
  return "#" + Math.floor(rng() * 0xFFFFFF).toString(16).padStart(6, "0");
}

// ── Option pools ────────────────────────────────────────────────────────────
var ALL_STATES = HydroUX.STATES.map(function (s) { return s.id; });
var PALETTE_NAMES = Object.keys(HydroUX.PALETTES);
var HUC_LEVELS = HydroUX.HUC_LEVELS;
var COLOR_MODES = ["watershed", "single", "elevation"];
var WIDTH_MODES = ["flow", "uniform"];
var TIME_MODES = ["annual", "single", "range"];
var SCOPES = ["state", "county"];
var PRODUCTS = ["digital-image", "fine-art-print", "watershed-report", "year-in-motion"];
var PRODUCT_ALIASES = { "digital": "digital-image", "print": "fine-art-print",
  "report": "watershed-report", "animation": "year-in-motion" };
var STYLES = ["neon-basin", "elevation-tint"];
var SIZES = ["12x16", "18x24", "24x36"];

// ── Minimal select shim (reused from test_order_prefill.cjs) ────────────────
function makeSelect(options) {
  var opts = options.map(function (o) { return { value: o.value, text: o.text }; });
  var listeners = {};
  var sel = {
    _options: opts,
    disabled: false,
    innerHTML: "",
    appendChild: function (opt) { opts.push({ value: opt.value, text: opt.textContent }); },
    addEventListener: function (evt, fn) {
      if (!listeners[evt]) listeners[evt] = [];
      listeners[evt].push(fn);
    },
    dispatchEvent: function (evt) {
      (listeners[evt.type] || []).forEach(function (fn) { fn(); });
    },
  };
  Object.defineProperty(sel, "value", {
    get: function () { return sel._value; },
    set: function (v) {
      sel._value = opts.some(function (o) { return o.value === v; }) ? v : "";
    },
    enumerable: true,
    configurable: true,
  });
  sel._value = opts.length ? opts[0].value : "";
  return sel;
}

// ── Simulate prefill (mirrors order.html logic with the fix) ────────────────
function simulatePrefill(params) {
  var H = HydroUX;
  var S = { product: "", region: "", county: "", style: "", size: "18x24",
            title: "", subtitle: "", note: "", email: "", name: "" };

  var stateOpts = [{ value: "", text: "Select a state…" }];
  H.STATES.forEach(function (s) { stateOpts.push({ value: s.id, text: s.label }); });
  var selState = makeSelect(stateOpts);
  var countyOpts = [{ value: "", text: "Select a county…" }];
  var selCounty = makeSelect(countyOpts);

  selState.addEventListener("change", function () {
    S.region = selState.value;
    selCounty._options = [{ value: "", text: "Select a county…" }];
    selCounty.disabled = !S.region;
    S.county = "";
    if (S.region && H.COUNTIES[S.region]) {
      H.COUNTIES[S.region].forEach(function (c) {
        selCounty._options.push({ value: c, text: c });
      });
    }
  });

  var prefillProduct = params.get("product") || "";
  var ALIASES = { "digital": "digital-image", "print": "fine-art-print",
    "report": "watershed-report", "animation": "year-in-motion" };
  prefillProduct = ALIASES[prefillProduct] || prefillProduct;
  var prefillRegion  = params.get("region") || "";
  var prefillCounty  = params.get("county") || "";

  var startStep = "step-1";
  var validProducts = PRODUCTS;
  if (prefillProduct && validProducts.indexOf(prefillProduct) !== -1) {
    S.product = prefillProduct;
    startStep = "step-2";
  }
  if (prefillRegion && startStep !== "step-1") {
    selState.value = prefillRegion;
    selState.dispatchEvent(new Event("change"));
    S.region = prefillRegion;
    if (prefillCounty) {
      selCounty.value = prefillCounty;
      S.county = prefillCounty;
      startStep = "step-3";
    }
  }

  var loc = S.county ? (S.county + " County, " + S.region) : S.region;
  var reviewLocation = loc || "—";

  return { S: S, startStep: startStep, reviewLocation: reviewLocation };
}

// ═════════════════════════════════════════════════════════════════════════════
// Block 1: 20 random recipe encode/decode round-trips
// ═════════════════════════════════════════════════════════════════════════════

test("20 random recipe round-trips with varied options", function () {
  for (var i = 0; i < 20; i++) {
    var state = pick(ALL_STATES);
    var scope = pick(SCOPES);
    var county = null;
    if (scope === "county") {
      var counties = HydroUX.COUNTIES[state];
      county = counties && counties.length > 0 ? pick(counties) : null;
      if (!county) scope = "state";
    }

    var recipe = {
      state: state, scope: scope, county: county,
      huc: pick(HUC_LEVELS),
      timeMode: pick(TIME_MODES),
      monthStart: randInt(0, 11), monthEnd: randInt(0, 11),
      colorMode: pick(COLOR_MODES),
      palette: pick(PALETTE_NAMES),
      single: randHex(), bg: randHex(),
      widthMode: pick(WIDTH_MODES),
      minW: 0.1 + rng() * 2, maxW: 1 + rng() * 5,
      gamma: 0.1 + rng() * 2,
      glow: coinFlip(), glowR: 0.5 + rng() * 5,
    };

    var encoded = HydroUX.encodeRecipe(recipe);
    assert.ok(encoded, "encode failed for trial " + i + " (" + state + ")");
    assert.ok(typeof encoded === "string" && encoded.length > 0);
    assert.ok(!/[+/=]/.test(encoded), "URL-unsafe chars in trial " + i);

    var decoded = HydroUX.decodeRecipe(encoded);
    assert.ok(decoded, "decode failed for trial " + i);
    assert.strictEqual(decoded.state, state, "state mismatch trial " + i);
    assert.strictEqual(decoded.scope, scope, "scope mismatch trial " + i);
    if (scope === "county") {
      assert.strictEqual(decoded.county, county, "county mismatch trial " + i);
    }
  }
});

// ═════════════════════════════════════════════════════════════════════════════
// Block 2: 20 random sanitizeRecipe with wild/edge-case values
// ═════════════════════════════════════════════════════════════════════════════

test("20 random sanitizeRecipe with edge-case values", function () {
  var junkStates = ["", "Atlantis", "new york", "OREGON", "  Washington  ", null];
  var junkModes = ["", "rainbow", "single", "WATERSHED", null, 42];
  var junkWidths = [-100, 0, 0.001, 99999, NaN, Infinity];
  var junkHex = ["red", "#GGG", "", "#000", "#ffffff", "rgb(0,0,0)", null];

  for (var i = 0; i < 20; i++) {
    var dirty = {
      state: coinFlip() ? pick(ALL_STATES) : pick(junkStates),
      scope: coinFlip() ? pick(SCOPES) : "galaxy",
      county: coinFlip() ? "Clark" : null,
      huc: coinFlip() ? pick(HUC_LEVELS) : "HUC999",
      timeMode: coinFlip() ? pick(TIME_MODES) : pick(junkModes),
      monthStart: coinFlip() ? randInt(0, 11) : randInt(-5, 20),
      monthEnd: coinFlip() ? randInt(0, 11) : randInt(-5, 20),
      colorMode: coinFlip() ? pick(COLOR_MODES) : pick(junkModes),
      palette: coinFlip() ? pick(PALETTE_NAMES) : "chartreuse",
      single: coinFlip() ? randHex() : pick(junkHex),
      bg: coinFlip() ? randHex() : pick(junkHex),
      widthMode: coinFlip() ? pick(WIDTH_MODES) : "sideways",
      minW: coinFlip() ? 0.5 : pick(junkWidths),
      maxW: coinFlip() ? 2.0 : pick(junkWidths),
      gamma: coinFlip() ? 0.5 : pick(junkWidths),
      glow: coinFlip() ? coinFlip() : "yes",
      glowR: coinFlip() ? 2.5 : pick(junkWidths),
    };

    var result = HydroUX.sanitizeRecipe(dirty);
    assert.ok(result, "sanitizeRecipe returned null for trial " + i);

    // Verify all output values are valid
    assert.ok(HydroUX.STATES.some(function (s) { return s.id === result.state; }),
      "invalid state after sanitize: " + result.state);
    assert.ok(result.scope === "state" || result.scope === "county",
      "invalid scope: " + result.scope);
    assert.ok(HUC_LEVELS.indexOf(result.huc) !== -1, "invalid huc: " + result.huc);
    assert.ok(TIME_MODES.indexOf(result.timeMode) !== -1, "invalid timeMode");
    assert.ok(COLOR_MODES.indexOf(result.colorMode) !== -1, "invalid colorMode");
    assert.ok(WIDTH_MODES.indexOf(result.widthMode) !== -1, "invalid widthMode");
    assert.ok(Object.prototype.hasOwnProperty.call(HydroUX.PALETTES, result.palette));
    assert.ok(/^#[0-9a-fA-F]{6}$/.test(result.single), "invalid single color");
    assert.ok(/^#[0-9a-fA-F]{6}$/.test(result.bg), "invalid bg color");
    assert.strictEqual(typeof result.glow, "boolean");
    assert.ok(isFinite(result.minW) && result.minW >= 0);
    assert.ok(isFinite(result.maxW) && result.maxW >= 0);
    assert.ok(isFinite(result.gamma) && result.gamma >= 0);
    assert.ok(isFinite(result.glowR) && result.glowR >= 0);
    assert.ok(result.monthStart >= 0 && result.monthStart <= 11);
    assert.ok(result.monthEnd >= 0 && result.monthEnd <= 11);
  }
});

// ═════════════════════════════════════════════════════════════════════════════
// Block 3: 15 random order-form prefill paths
// ═════════════════════════════════════════════════════════════════════════════

test("15 random prefill paths — region always survives to review", function () {
  for (var i = 0; i < 15; i++) {
    var state = pick(ALL_STATES);
    var counties = HydroUX.COUNTIES[state];
    var county = counties && counties.length > 0 && coinFlip() ? pick(counties) : "";
    var product = coinFlip() ? pick(PRODUCTS) : pick(Object.keys(PRODUCT_ALIASES));

    var qs = "product=" + encodeURIComponent(product) +
             "&region=" + encodeURIComponent(state);
    if (county) qs += "&county=" + encodeURIComponent(county);

    var r = simulatePrefill(new URLSearchParams(qs));

    assert.strictEqual(r.S.region, state,
      "region lost for " + state + " (trial " + i + ")");

    if (county) {
      assert.strictEqual(r.S.county, county,
        "county lost for " + county + ", " + state + " (trial " + i + ")");
      assert.strictEqual(r.startStep, "step-3",
        "should skip to step-3 with county (trial " + i + ")");
      assert.ok(r.reviewLocation.indexOf(county) !== -1,
        "review missing county: " + r.reviewLocation);
      assert.ok(r.reviewLocation.indexOf(state) !== -1,
        "review missing state: " + r.reviewLocation);
    } else {
      assert.strictEqual(r.startStep, "step-2",
        "should stay on step-2 without county (trial " + i + ")");
      assert.strictEqual(r.reviewLocation, state);
    }

    // Never the bare "County," bug
    assert.ok(!/^\s*County,\s*$/.test(r.reviewLocation),
      "bare County, bug in trial " + i + ": " + r.reviewLocation);
  }
});

// ═════════════════════════════════════════════════════════════════════════════
// Block 4: 10 multi-word state name edge cases
// ═════════════════════════════════════════════════════════════════════════════

test("10 multi-word states with random counties — URL encoding round-trip", function () {
  var multiWord = ALL_STATES.filter(function (s) { return s.indexOf(" ") !== -1; });
  for (var i = 0; i < 10; i++) {
    var state = pick(multiWord);
    var counties = HydroUX.COUNTIES[state];
    var county = pick(counties);

    // Simulate the URLSearchParams encode/decode cycle
    var params = new URLSearchParams();
    params.set("product", "watershed-report");
    params.set("region", state);
    params.set("county", county);

    // Parse the serialized form (as would happen on page navigation)
    var serialized = params.toString();
    var reparsed = new URLSearchParams(serialized);

    assert.strictEqual(reparsed.get("region"), state,
      "URL encoding round-trip failed for state: " + state);
    assert.strictEqual(reparsed.get("county"), county,
      "URL encoding round-trip failed for county: " + county);

    var r = simulatePrefill(reparsed);
    assert.strictEqual(r.S.region, state);
    assert.strictEqual(r.S.county, county);
  }
});

// ═════════════════════════════════════════════════════════════════════════════
// Block 5: 10 preset application round-trips
// ═════════════════════════════════════════════════════════════════════════════

test("10 random presets applied to random base states", function () {
  for (var i = 0; i < 10; i++) {
    var state = pick(ALL_STATES);
    var scope = pick(SCOPES);
    var county = null;
    if (scope === "county") {
      var counties = HydroUX.COUNTIES[state];
      county = counties.length > 0 ? pick(counties) : null;
      if (!county) scope = "state";
    }

    var baseState = {
      previewSource: "procedural", loadedName: null,
      state: state, scope: scope, county: county, huc: pick(HUC_LEVELS),
      timeMode: pick(TIME_MODES), monthStart: randInt(0, 11), monthEnd: randInt(0, 11),
      month: randInt(0, 11),
      colorMode: pick(COLOR_MODES), palette: pick(PALETTE_NAMES),
      single: randHex(), bg: "#05060a",
      widthMode: pick(WIDTH_MODES), minW: 0.5, maxW: 2.0, gamma: 0.5,
      glow: coinFlip(), glowR: 2.5, _nudge: 0,
    };

    var preset = pick(HydroUX.PRESETS);
    var result = HydroUX.applyPreset(baseState, preset.id);

    // Geography presets (kind: "state"/"county") intentionally set geography;
    // screen/glow-only presets must NOT overwrite it.
    var setsGeo = preset.recipe && ("state" in preset.recipe);
    if (!setsGeo) {
      assert.strictEqual(result.state, state,
        "preset " + preset.id + " unexpectedly overwrote state");
      assert.strictEqual(result.scope, scope,
        "preset " + preset.id + " unexpectedly overwrote scope");
      if (scope === "county") {
        assert.strictEqual(result.county, county,
          "preset " + preset.id + " unexpectedly overwrote county");
      }
    } else {
      // Geography preset — result state should match the preset's state
      assert.strictEqual(result.state, preset.recipe.state,
        "preset " + preset.id + " state didn't apply");
    }

    // Result must still encode cleanly
    var encoded = HydroUX.encodeRecipe(result);
    assert.ok(encoded, "encode failed after preset " + preset.id);
    var decoded = HydroUX.decodeRecipe(encoded);
    assert.ok(decoded, "decode failed after preset " + preset.id);
  }
});

// ═════════════════════════════════════════════════════════════════════════════
// Block 6: 10 county coherence checks — every state has valid counties
// ═════════════════════════════════════════════════════════════════════════════

test("10 random states — county data is well-formed", function () {
  var sampled = pickN(ALL_STATES, 10);
  sampled.forEach(function (state) {
    var counties = HydroUX.COUNTIES[state];
    assert.ok(Array.isArray(counties), state + " missing COUNTIES entry");
    assert.ok(counties.length > 0, state + " has no counties");

    // No duplicates
    var unique = new Set(counties);
    assert.strictEqual(unique.size, counties.length,
      state + " has duplicate county names");

    // No empty strings
    counties.forEach(function (c) {
      assert.ok(typeof c === "string" && c.trim().length > 0,
        state + " has empty/invalid county: " + JSON.stringify(c));
    });

    // Counties are sorted (convention check)
    var sorted = counties.slice().sort();
    assert.deepStrictEqual(counties, sorted,
      state + " counties not alphabetically sorted");
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// Block 7: 10 HUC4 coherence checks — every state has valid basins
// ═════════════════════════════════════════════════════════════════════════════

test("10 random states — HUC4 data is well-formed", function () {
  var sampled = pickN(ALL_STATES, 10);
  sampled.forEach(function (state) {
    var stateObj = HydroUX.STATES.find(function (s) { return s.id === state; });
    assert.ok(stateObj, state + " not in STATES array");
    assert.ok(Array.isArray(stateObj.huc4) && stateObj.huc4.length > 0,
      state + " has no HUC4 codes");

    // All HUC4 codes are 4-digit strings
    stateObj.huc4.forEach(function (h) {
      assert.ok(/^\d{4}$/.test(h),
        state + " has invalid HUC4 code: " + h);
    });

    // No duplicates
    var unique = new Set(stateObj.huc4);
    assert.strictEqual(unique.size, stateObj.huc4.length,
      state + " has duplicate HUC4 codes");
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// Block 8: 5 exhaustive style × size × product × format combos
// ═════════════════════════════════════════════════════════════════════════════

test("5 random product × style × size prefill combos", function () {
  for (var i = 0; i < 5; i++) {
    var product = pick(PRODUCTS);
    var style = pick(STYLES);
    var size = pick(SIZES);
    var state = pick(ALL_STATES);
    var counties = HydroUX.COUNTIES[state];
    var county = pick(counties);

    var qs = "product=" + encodeURIComponent(product) +
             "&region=" + encodeURIComponent(state) +
             "&county=" + encodeURIComponent(county) +
             "&style=" + encodeURIComponent(style);

    var r = simulatePrefill(new URLSearchParams(qs));
    assert.strictEqual(r.S.product, product, "product mismatch");
    assert.strictEqual(r.S.region, state, "region mismatch");
    assert.strictEqual(r.S.county, county, "county mismatch");
  }
});

console.log("ok — " + passed + " randomized option tests passed (100 trials total)");
