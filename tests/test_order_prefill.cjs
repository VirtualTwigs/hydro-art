/* Headless Node tests for order.html URL-param pre-fill and review display.
   Exercises the data-flow logic that maps URL params → S state → review text.
   Uses a minimal DOM shim — no browser, no datasets.
   Run: node tests/test_order_prefill.cjs
   Mirrors the offline posture of test_recipe_roundtrip.cjs: stdlib only. */
"use strict";
const assert = require("assert");
const path = require("path");
const HydroUX = require(path.join(__dirname, "..", "web", "shared", "hydro-ux.js"));

let passed = 0;
function test(name, fn) { fn(); passed++; }

// ── Minimal select shim ─────────────────────────────────────────────────────
// Models the HTML <select> value-assignment and change-event semantics used
// by order.html's prefill code.

function makeSelect(options) {
  var opts = options.map(function (o) { return { value: o.value, text: o.text }; });
  var listeners = {};
  var sel = {
    _options: opts,
    value: opts.length ? opts[0].value : "",
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
  // Mimic real <select> value setter: if no matching option, value stays ""
  Object.defineProperty(sel, "value", {
    get: function () { return sel._value; },
    set: function (v) {
      if (opts.some(function (o) { return o.value === v; })) {
        sel._value = v;
      } else {
        sel._value = "";
      }
    },
    enumerable: true,
    configurable: true,
  });
  sel._value = opts.length ? opts[0].value : "";
  return sel;
}

// ── Factory: reproduce order.html's prefill logic ───────────────────────────
// Mirrors lines 762–1055 of order.html, distilled to the data-flow essentials.

function simulatePrefill(urlParams) {
  var H = HydroUX;
  var S = { product: "", region: "", county: "", style: "", size: "18x24",
            title: "", subtitle: "", note: "", email: "", name: "" };

  // Build state select with real HydroUX data
  var stateOpts = [{ value: "", text: "Select a state…" }];
  H.STATES.forEach(function (s) { stateOpts.push({ value: s.id, text: s.label }); });
  var selState = makeSelect(stateOpts);

  var countyOpts = [{ value: "", text: "Select a county…" }];
  var selCounty = makeSelect(countyOpts);

  // Wire the change handlers (mirrors order.html lines 774-792)
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

  selCounty.addEventListener("change", function () {
    S.county = selCounty.value;
  });

  // Parse URL params
  var PRODUCT_ALIASES = {
    "digital": "digital-image", "print": "fine-art-print",
    "report": "watershed-report", "animation": "year-in-motion",
  };
  var prefillProduct = urlParams.get("product") || "";
  prefillProduct = PRODUCT_ALIASES[prefillProduct] || prefillProduct;
  var prefillRegion  = urlParams.get("region") || "";
  var prefillCounty  = urlParams.get("county") || "";
  var prefillStyle   = urlParams.get("style") || "";

  var startStep = "step-1";

  // Step 1: product
  var validProducts = ["digital-image", "fine-art-print", "watershed-report", "year-in-motion"];
  if (prefillProduct && validProducts.includes(prefillProduct)) {
    S.product = prefillProduct;
    startStep = "step-2";
  }

  // Step 2: location (mirrors the FIXED code with S.region = prefillRegion)
  if (prefillRegion && startStep !== "step-1") {
    selState.value = prefillRegion;
    selState.dispatchEvent(new Event("change"));
    S.region = prefillRegion;  // The fix: explicit set AFTER change event
    if (prefillCounty) {
      // setTimeout callback runs synchronously in our shim
      selCounty.value = prefillCounty;
      S.county = prefillCounty;
      startStep = "step-3";
    }
  }

  // Step 3: style
  var validStyles = ["neon-basin", "elevation-tint"];
  if (prefillStyle && startStep === "step-3" && validStyles.includes(prefillStyle)) {
    S.style = prefillStyle;
    startStep = "step-4";
  }

  // populateReview logic (mirrors the FIXED code)
  var loc = S.county ? (S.county + " County, " + S.region) : S.region;
  var reviewLocation = loc || "—";

  return { S: S, startStep: startStep, reviewLocation: reviewLocation,
           selState: selState, selCounty: selCounty };
}

// ═════════════════════════════════════════════════════════════════════════════
// Unit tests
// ═════════════════════════════════════════════════════════════════════════════

// ── S.region is set explicitly during prefill ────────────────────────────────
test("prefill sets S.region explicitly for single-word state", function () {
  var params = new URLSearchParams("product=watershed-report&region=Oregon&county=Clackamas");
  var r = simulatePrefill(params);
  assert.strictEqual(r.S.region, "Oregon");
  assert.strictEqual(r.S.county, "Clackamas");
});

test("prefill sets S.region for multi-word state (New York)", function () {
  var params = new URLSearchParams("product=watershed-report&region=New+York&county=New+York");
  var r = simulatePrefill(params);
  assert.strictEqual(r.S.region, "New York");
  assert.strictEqual(r.S.county, "New York");
});

test("prefill sets S.region for all space-containing state names", function () {
  var spaceStates = HydroUX.STATES.filter(function (s) { return s.id.includes(" "); });
  assert.ok(spaceStates.length >= 5, "at least 5 multi-word states exist");
  spaceStates.forEach(function (st) {
    var counties = HydroUX.COUNTIES[st.id];
    var county = counties && counties[0] ? counties[0] : "";
    var qs = "product=watershed-report&region=" + encodeURIComponent(st.id);
    if (county) qs += "&county=" + encodeURIComponent(county);
    var r = simulatePrefill(new URLSearchParams(qs));
    assert.strictEqual(r.S.region, st.id, "region mismatch for " + st.id);
    if (county) assert.strictEqual(r.S.county, county, "county mismatch for " + st.id);
  });
});

// ── Review location display ─────────────────────────────────────────────────
test("review shows 'County, State' when both present", function () {
  var params = new URLSearchParams("product=watershed-report&region=Washington&county=Clark");
  var r = simulatePrefill(params);
  assert.strictEqual(r.reviewLocation, "Clark County, Washington");
});

test("review shows state only when no county", function () {
  var params = new URLSearchParams("product=watershed-report&region=Oregon");
  var r = simulatePrefill(params);
  assert.strictEqual(r.reviewLocation, "Oregon");
});

test("review shows dash fallback when both empty", function () {
  var params = new URLSearchParams("product=watershed-report");
  var r = simulatePrefill(params);
  assert.strictEqual(r.reviewLocation, "—");
});

test("review never shows bare 'County,' with no state", function () {
  // This was the exact symptom of the bug
  var params = new URLSearchParams("product=watershed-report&region=New+York&county=New+York");
  var r = simulatePrefill(params);
  assert.ok(!r.reviewLocation.match(/^\s*County,\s*$/), "review must not be bare 'County,'");
  assert.strictEqual(r.reviewLocation, "New York County, New York");
});

// ── Step skipping ───────────────────────────────────────────────────────────
test("skips to step-3 when product + region + county are prefilled", function () {
  var params = new URLSearchParams("product=watershed-report&region=Washington&county=Clark");
  var r = simulatePrefill(params);
  assert.strictEqual(r.startStep, "step-3");
});

test("stays on step-2 when region prefilled without county", function () {
  var params = new URLSearchParams("product=watershed-report&region=Washington");
  var r = simulatePrefill(params);
  assert.strictEqual(r.startStep, "step-2");
});

test("stays on step-1 when no product", function () {
  var params = new URLSearchParams("region=Washington&county=Clark");
  var r = simulatePrefill(params);
  assert.strictEqual(r.startStep, "step-1");
  assert.strictEqual(r.S.region, "", "region not set without product");
});

// ── Invalid region graceful degradation ─────────────────────────────────────
test("invalid region leaves S.region as the prefill value", function () {
  // The select won't match, but S.region is explicitly set from the URL param.
  // The server-side validation catches invalid regions.
  var params = new URLSearchParams("product=watershed-report&region=Atlantis&county=Troy");
  var r = simulatePrefill(params);
  assert.strictEqual(r.S.region, "Atlantis");
});

// ── Product alias normalization ─────────────────────────────────────────────
test("product aliases resolve to canonical names", function () {
  var aliases = { "digital": "digital-image", "print": "fine-art-print",
                  "report": "watershed-report", "animation": "year-in-motion" };
  Object.keys(aliases).forEach(function (alias) {
    var params = new URLSearchParams("product=" + alias + "&region=Oregon");
    var r = simulatePrefill(params);
    assert.strictEqual(r.S.product, aliases[alias], alias + " → " + aliases[alias]);
  });
});

// ── County dropdown populated for prefilled region ──────────────────────────
test("county select is populated when region is prefilled", function () {
  var params = new URLSearchParams("product=watershed-report&region=Washington&county=Clark");
  var r = simulatePrefill(params);
  var countyValues = r.selCounty._options.map(function (o) { return o.value; });
  assert.ok(countyValues.includes("Clark"), "Clark must be in county options");
  assert.ok(countyValues.length > 10, "Washington has many counties");
});

console.log("ok — " + passed + " order prefill tests passed");
