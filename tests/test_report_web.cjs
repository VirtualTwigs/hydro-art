/* Headless Node tests for the #76 report-surfacing helpers in web/shared/hydro-ux.js.
   Pure client-side logic — no DOM, no datasets. Run: node tests/test_report_web.cjs
   Mirrors the offline posture of the Python suite: stdlib `node` only, no deps.
   The report figures live in tools/ (heavy GIS + matplotlib, outside every suite);
   what is testable offline is the pure JS that the static report page renders. */
"use strict";
const assert = require("assert");
const path = require("path");
const HydroUX = require(path.join(__dirname, "..", "web", "shared", "hydro-ux.js"));

let passed = 0;
function test(name, fn) { fn(); passed++; }

// --- classifyRegime mirrors src.flow_metrics thresholds (#69) -----------------
test("classifyRegime labels snowmelt / transitional / rain by fraction", () => {
  assert.strictEqual(HydroUX.classifyRegime(0.7), "snowmelt");
  assert.strictEqual(HydroUX.classifyRegime(0.4), "snowmelt");   // >= snow_min
  assert.strictEqual(HydroUX.classifyRegime(0.3), "transitional");
  assert.strictEqual(HydroUX.classifyRegime(0.2), "rain");       // <= rain_max
  assert.strictEqual(HydroUX.classifyRegime(0.05), "rain");
});

test("classifyRegime honours custom thresholds and rejects bad ones", () => {
  assert.strictEqual(HydroUX.classifyRegime(0.5, 0.6, 0.3), "transitional");
  assert.strictEqual(HydroUX.classifyRegime(0.65, 0.6, 0.3), "snowmelt");
  for (const bad of [[0.2, 0.4], [-0.1, 0.5], [0.5, 1.2]]) {
    assert.throws(() => HydroUX.classifyRegime(0.5, bad[0], bad[1]));
  }
});

// --- centerOfTimingIndex is a 0-based flow-weighted month ----------------------
test("centerOfTimingIndex returns the flow-weighted month index", () => {
  const spike = [0, 0, 0, 10, 0, 0, 0, 0, 0, 0, 0, 0];
  assert.strictEqual(HydroUX.centerOfTimingIndex(spike), 3);     // all weight at Apr(idx3)
  const uniform = new Array(12).fill(5);
  assert.ok(Math.abs(HydroUX.centerOfTimingIndex(uniform) - 5.5) < 1e-9);
  const twoPeak = [0, 0, 6, 0, 0, 0, 0, 0, 6, 0, 0, 0];         // idx2 & idx8 -> 5
  assert.ok(Math.abs(HydroUX.centerOfTimingIndex(twoPeak) - 5) < 1e-9);
});

test("centerOfTimingIndex is NaN for empty / all-zero input", () => {
  assert.ok(Number.isNaN(HydroUX.centerOfTimingIndex([])));
  assert.ok(Number.isNaN(HydroUX.centerOfTimingIndex(new Array(12).fill(0))));
});

// --- sampleReport carries the new #76 sections with sane shapes ---------------
test("sampleReport carries regime / analogs / recordBook / fdc / composites", () => {
  const doc = HydroUX.sampleReport();

  // regime (#69): label consistent with its fraction
  assert.ok(doc.regime && typeof doc.regime.fraction === "number");
  assert.strictEqual(doc.regime.label, HydroUX.classifyRegime(doc.regime.fraction));
  assert.ok(doc.regime.meltCenterMonth >= 0 && doc.regime.meltCenterMonth <= 11);

  // analogs (#71): sorted by descending similarity, target excluded
  assert.ok(Array.isArray(doc.analogs) && doc.analogs.length >= 3);
  for (let i = 1; i < doc.analogs.length; i++) {
    assert.ok(doc.analogs[i - 1].similarity >= doc.analogs[i].similarity);
  }

  // recordBook (#72): driest + wettest leaderboards, rank 1 first
  assert.ok(doc.recordBook.driest.length >= 1 && doc.recordBook.wettest.length >= 1);
  assert.strictEqual(doc.recordBook.driest[0].rank, 1);
  assert.strictEqual(doc.recordBook.wettest[0].rank, 1);

  // fdc (#73): each decade curve non-increasing in exceedance quantile
  assert.ok(Array.isArray(doc.fdc) && doc.fdc.length >= 2);
  for (const d of doc.fdc) {
    assert.strictEqual(d.flows.length, doc.fdcQuantiles.length);
    for (let i = 1; i < d.flows.length; i++) {
      assert.ok(d.flows[i] <= d.flows[i - 1] + 1e-9, "FDC must be non-increasing in q");
    }
  }

  // composites (#74): warm/neutral/cool each a 12-month hydrograph
  for (const k of ["warm", "neutral", "cool"]) {
    assert.strictEqual(doc.composites[k].length, 12);
  }
});

console.log(`ok — ${passed} report-web tests passed`);
