/* Headless Node tests for the #28 recipe/preset helpers in web/shared/hydro-ux.js.
   Pure client-side logic — no DOM, no datasets. Run: node tests/test_recipe_roundtrip.cjs
   Mirrors the offline posture of the Python suite: stdlib `node` only, no deps. */
"use strict";
const assert = require("assert");
const path = require("path");
const HydroUX = require(path.join(__dirname, "..", "web", "shared", "hydro-ux.js"));

let passed = 0;
function test(name, fn) { fn(); passed++; }

function baseState(over) {
  return Object.assign({
    previewSource: "procedural", loadedName: null,
    state: "Oregon", scope: "state", county: null, huc: "HUC4",
    timeMode: "annual", monthStart: 5, monthEnd: 8, month: 6,
    colorMode: "watershed", palette: "neon", single: "#00e5ff", bg: "#05060a",
    widthMode: "flow", minW: 0.5, maxW: 2.0, gamma: 0.5, glow: false, glowR: 2.5, _nudge: 0,
  }, over || {});
}

// --- toRecipe drops preview-only fields, keeps canonical keys ------------------
test("toRecipe keeps only RECIPE_KEYS", () => {
  const r = HydroUX.toRecipe(baseState());
  const keys = Object.keys(r).sort();
  assert.deepStrictEqual(keys, HydroUX.RECIPE_KEYS.slice().sort());
  assert.ok(!("previewSource" in r) && !("month" in r) && !("_nudge" in r) && !("loadedName" in r));
});

// --- round-trip deep equality across several states ---------------------------
test("round-trip deep-equals toRecipe for many states", () => {
  const states = [
    baseState(),
    baseState({ state: "Washington", scope: "county", county: "Clark", huc: "HUC8" }),
    baseState({ timeMode: "single", monthStart: 0 }),
    baseState({ timeMode: "range", monthStart: 2, monthEnd: 9 }),
    baseState({ colorMode: "single", single: "#ff0080" }),
    baseState({ colorMode: "elevation" }),
    baseState({ widthMode: "uniform", glow: true, glowR: 4.0 }),
    baseState({ state: "California", scope: "county", county: "Fresno", palette: "ember" }),
  ];
  for (const s of states) {
    const decoded = HydroUX.decodeRecipe(HydroUX.encodeRecipe(s));
    assert.deepStrictEqual(decoded, HydroUX.toRecipe(s));
  }
});

// --- determinism --------------------------------------------------------------
test("encodeRecipe is deterministic", () => {
  const s = baseState({ state: "Washington", scope: "county", county: "Clark" });
  assert.strictEqual(HydroUX.encodeRecipe(s), HydroUX.encodeRecipe(s));
});

// --- base64url is URL-safe ----------------------------------------------------
test("encoded string is URL-safe (no + / =)", () => {
  // exercise many payloads to make padding/altchars likely
  for (let i = 0; i < 12; i++) {
    const s = baseState({ single: "#" + (i * 111111).toString(16).padStart(6, "0").slice(0,6),
                          monthStart: i % 12, glowR: i * 0.37 });
    const enc = HydroUX.encodeRecipe(s);
    assert.ok(!/[+/=]/.test(enc), "unsafe char in " + enc);
  }
});

// --- decodeRecipe of garbage returns null (never throws) ----------------------
test("decodeRecipe returns null on garbage", () => {
  for (const junk of ["", "!!!!", "not-base64-$$$", "eyJ", "%%%", null, undefined, 42, "zzzz"]) {
    assert.strictEqual(HydroUX.decodeRecipe(junk), null);
  }
});

// --- sanitize clamps & allowlist-rejects hand-edited values -------------------
test("sanitizeRecipe validates against catalogs", () => {
  const dirty = {
    state: "Atlantis", scope: "galaxy", county: "Nowhere", huc: "HUC999",
    timeMode: "eon", monthStart: -5, monthEnd: 99,
    colorMode: "rainbow", palette: "chartreuse", single: "red", bg: "#GGGGGG",
    widthMode: "sideways", minW: -3, maxW: 9999, gamma: -1, glow: "yes", glowR: 1e9,
    junkKey: "ignored",
  };
  const r = HydroUX.sanitizeRecipe(dirty);
  assert.ok(Object.keys(HydroUX.STATES ? {} : {}) || true);
  assert.ok(HydroUX.STATES.some(s => s.id === r.state), "state fell back to a real state");
  assert.ok(r.scope === "state" || r.scope === "county");
  assert.ok(HydroUX.HUC_LEVELS.includes(r.huc));
  assert.ok(["annual","single","range"].includes(r.timeMode));
  assert.ok(r.monthStart >= 0 && r.monthStart <= 11 && r.monthEnd >= 0 && r.monthEnd <= 11);
  assert.ok(["watershed","single","elevation"].includes(r.colorMode));
  assert.ok(Object.prototype.hasOwnProperty.call(HydroUX.PALETTES, r.palette));
  assert.ok(/^#[0-9a-fA-F]{6}$/.test(r.single) && /^#[0-9a-fA-F]{6}$/.test(r.bg));
  assert.ok(["flow","uniform"].includes(r.widthMode));
  assert.strictEqual(typeof r.glow, "boolean");
  assert.ok(!("junkKey" in r));
  assert.ok(isFinite(r.minW) && isFinite(r.maxW) && isFinite(r.gamma) && isFinite(r.glowR));
});

test("sanitizeRecipe returns null for non-objects", () => {
  for (const junk of [null, undefined, 3, "str", []]) {
    // arrays are technically objects; helper should still produce a valid recipe OR null.
    const r = HydroUX.sanitizeRecipe(junk);
    if (Array.isArray(junk)) {
      assert.ok(r === null || typeof r === "object");
    } else {
      assert.strictEqual(r, null);
    }
  }
});

// --- county coherence with scope ---------------------------------------------
test("sanitize forces county null when scope=state and valid when county", () => {
  const asState = HydroUX.sanitizeRecipe(HydroUX.toRecipe(baseState({ scope: "state", county: "Clark" })));
  assert.strictEqual(asState.county, null);
  const asCounty = HydroUX.sanitizeRecipe(HydroUX.toRecipe(baseState({ state: "Washington", scope: "county", county: "Bogus" })));
  assert.ok(HydroUX.COUNTIES.Washington.includes(asCounty.county));
});

// --- presets ------------------------------------------------------------------
test("PRESETS are partial recipes merged over current state", () => {
  assert.ok(Array.isArray(HydroUX.PRESETS) && HydroUX.PRESETS.length >= 3);
  const glowPreset = HydroUX.PRESETS.find(p => p.recipe && p.recipe.glow === true);
  assert.ok(glowPreset, "a glow-on preset exists");
  const start = baseState({ state: "California", scope: "county", county: "Fresno", glow: false });
  const next = HydroUX.applyPreset(start, glowPreset.id);
  assert.strictEqual(next.glow, true);
  // geography left intact by a screen/glow partial preset
  assert.strictEqual(next.state, "California");
  assert.strictEqual(next.county, "Fresno");
});

test("applyPreset is a no-op for unknown id", () => {
  const s = baseState();
  const out = HydroUX.applyPreset(s, "does-not-exist");
  assert.deepStrictEqual(HydroUX.toRecipe(out), HydroUX.toRecipe(s));
});

// --- applyRecipe preserves preview-only fields --------------------------------
test("applyRecipe preserves preview-only fields", () => {
  const s = baseState({ previewSource: "loaded", loadedName: "foo.gdb", _nudge: 7, month: 3 });
  const out = HydroUX.applyRecipe(s, HydroUX.toRecipe(baseState({ state: "Washington" })));
  assert.strictEqual(out.previewSource, "loaded");
  assert.strictEqual(out.loadedName, "foo.gdb");
  assert.strictEqual(out._nudge, 7);
  assert.strictEqual(out.state, "Washington");
});

console.log(`ok — ${passed} recipe/preset tests passed`);
