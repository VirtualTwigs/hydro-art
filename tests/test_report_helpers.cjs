/* Headless Node tests for the #55 watershed-report helpers in
   web/shared/hydro-ux.js. Pure client-side formatting/SVG builders — no DOM, no
   datasets. Run: node tests/test_report_helpers.cjs
   Mirrors the offline posture of the Python suite: stdlib `node` only, no deps. */
"use strict";
const assert = require("assert");
const path = require("path");
const HydroUX = require(path.join(__dirname, "..", "web", "shared", "hydro-ux.js"));

let passed = 0;
function test(name, fn) { fn(); passed++; }

// --- ordinal ------------------------------------------------------------------
test("ordinal handles st/nd/rd/th and teens", () => {
  assert.strictEqual(HydroUX.ordinal(1), "1st");
  assert.strictEqual(HydroUX.ordinal(2), "2nd");
  assert.strictEqual(HydroUX.ordinal(3), "3rd");
  assert.strictEqual(HydroUX.ordinal(4), "4th");
  assert.strictEqual(HydroUX.ordinal(11), "11th");
  assert.strictEqual(HydroUX.ordinal(12), "12th");
  assert.strictEqual(HydroUX.ordinal(13), "13th");
  assert.strictEqual(HydroUX.ordinal(92), "92nd");
});

// --- trendArrow ---------------------------------------------------------------
test("trendArrow reflects sign, flat/unknown -> middot", () => {
  assert.strictEqual(HydroUX.trendArrow(5), "\u25b2");
  assert.strictEqual(HydroUX.trendArrow(-0.3), "\u25bc");
  assert.strictEqual(HydroUX.trendArrow(0), "\u00b7");
  assert.strictEqual(HydroUX.trendArrow(NaN), "\u00b7");
});

// --- fmtNum -------------------------------------------------------------------
test("fmtNum trims trailing zeros and handles non-finite", () => {
  assert.strictEqual(HydroUX.fmtNum(665), "665");
  assert.strictEqual(HydroUX.fmtNum(0.1), "0.1");
  assert.strictEqual(HydroUX.fmtNum(12.0), "12");
  assert.strictEqual(HydroUX.fmtNum(NaN), "\u2014");
  assert.strictEqual(HydroUX.fmtNum(3.14159, 2), "3.14");
});

// --- verdict mapping ----------------------------------------------------------
test("verdictClass/Label map to shared status tokens", () => {
  assert.strictEqual(HydroUX.verdictClass("good"), "ok");
  assert.strictEqual(HydroUX.verdictClass("moderate"), "warn");
  assert.strictEqual(HydroUX.verdictClass("weak"), "danger");
  assert.strictEqual(HydroUX.verdictClass("???"), "muted");
  assert.strictEqual(HydroUX.verdictLabel("moderate"), "MODERATE");
});

// --- sparkline geometry -------------------------------------------------------
test("sparklinePoints normalize into the box, y inverted", () => {
  const pts = HydroUX.sparklinePoints([0, 1, 2], 100, 20, 0);
  assert.strictEqual(pts.length, 3);
  // x spans 0..100
  assert.ok(Math.abs(pts[0][0] - 0) < 1e-6);
  assert.ok(Math.abs(pts[2][0] - 100) < 1e-6);
  // min value -> bottom (y == h), max -> top (y == 0)
  assert.ok(Math.abs(pts[0][1] - 20) < 1e-6);
  assert.ok(Math.abs(pts[2][1] - 0) < 1e-6);
});

test("sparklinePoints drops non-finite and handles flat/empty", () => {
  const withGap = HydroUX.sparklinePoints([1, NaN, 3], 100, 20, 0);
  assert.strictEqual(withGap.length, 2); // the NaN sample is dropped, never zero-filled
  assert.deepStrictEqual(HydroUX.sparklinePoints([], 100, 20), []);
  const flat = HydroUX.sparklinePoints([5, 5, 5], 100, 20, 0);
  assert.strictEqual(flat.length, 3); // flat series still renders (centered)
});

test("buildSparkline returns a self-contained svg string", () => {
  const svg = HydroUX.buildSparkline([1, 2, 3, 2, 4], { w: 200, h: 40 });
  assert.ok(svg.startsWith("<svg") && svg.includes("</svg>"));
  assert.ok(svg.includes('class="sparkline"'));
  assert.ok(svg.includes("<path d=\"M"));
  assert.ok(svg.includes("<circle")); // last-point dot
  // empty series -> empty path, no crash, no dot
  const empty = HydroUX.buildSparkline([], { w: 200, h: 40 });
  assert.ok(empty.includes('d=""') && !empty.includes("<circle"));
});

// --- sample report document ---------------------------------------------------
test("REPORT_SAMPLE is deterministic and well-shaped", () => {
  const a = HydroUX.sampleReport(), b = HydroUX.sampleReport();
  assert.deepStrictEqual(a, b); // deterministic (fixed seed)
  const r = HydroUX.REPORT_SAMPLE;
  assert.strictEqual(r.longRecord.years.length, 34); // 1990..2023
  assert.strictEqual(r.longRecord.peak.length, 34);
  assert.strictEqual(r.typicalYear.mean.length, 12);
  assert.ok(["good", "moderate", "weak"].includes(r.validation.verdict));
  assert.ok(r.metrics.peak.pct > 0 && r.metrics.peak.pct <= 1);
});

console.log(`ok — ${passed} report-helper tests passed`);
