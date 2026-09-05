/* ==========================================================================
   Hydro-Art experiments — feature-preview extension (window.HydroFeatures)
   --------------------------------------------------------------------------
   The shared web/shared/hydro-ux.js engine renders only the FLOWLINE stack
   (color / width / glow / seasonal flow). It does not yet preview the newer
   pipeline layers, so a customer-facing mockup can't show them changing. This
   module is a thin, browser-only extension that layers those newer features
   onto the same procedural network, so the two end-user prototypes in this
   folder can demonstrate them live:

     - Waterbodies (Epoch 1.5): lakes / ponds / reservoirs as outlined polygons
       (src/waterbodies.py + WATERBODY_PRESETS: outline #2ec4ff, "below").
     - Natural point features (Epoch 15): springs (dot), waterfalls (chevron),
       rapids (tick) — glyph shapes + colors mirror src/rendering.POINT_GLYPHS
       and DEFAULT_POINT_STYLES exactly.
     - Areal features (Epoch 15): wetlands (hatch), perennial ice (solid),
       playas (dashed) — mirror src/rendering.DEFAULT_AREAL_STYLES.
     - Scale-aware width presets (Epoch 18): state / basin / watershed, values
       mirrored from src/config.WIDTH_PRESETS.

   Everything here is deterministic (seeded from the network) and DOM-only. It
   depends on window.HydroUX (loaded first) for the network + flowline styling;
   it never touches the real pipeline. The area / spacing thresholds used to
   declutter for print are *preview proxies* (in viewBox px) for the real m² /
   m thresholds in the POINT/AREAL/WATERBODY presets — tuned so the difference
   between screen, print-county, and print-state reads at a glance.
   ========================================================================== */
"use strict";

(function (global) {
  const H = global.HydroUX;

  // ---- Style tables (mirrored from src/rendering.py) ----------------------
  const WATERBODY = { color: "#2ec4ff", stroke: 1.1 };
  const POINT_STYLES = {
    spring:    { color: "#7fe3ff", glyph: "dot",     size: 5.0 },
    waterfall: { color: "#eaf6ff", glyph: "chevron", size: 7.0 },
    rapids:    { color: "#bfefff", glyph: "tick",    size: 7.0 },
  };
  const AREAL_STYLES = {
    wetland:       { color: "#4fae86", fill: "hatch" },
    perennial_ice: { color: "#dbeeff", fill: "solid", opacity: 0.35 },
    playa:         { color: "#c9a86a", fill: "none",  dash: "5,4" },
  };

  // Named "detail" presets → preview declutter proxies. Mirrors the intent of
  // POINT/AREAL/WATERBODY *_PRESETS (screen shows everything; print thins).
  //   ptSpacing : min spacing (vb px) between kept points of one family.
  //   minRadius : min blob radius (vb px) an areal / waterbody must exceed.
  const DETAIL_PRESETS = {
    "screen":       { label: "Screen",        ptSpacing: 0,  minRadius: 0,  wbStroke: 1.0 },
    "print-county": { label: "Print · county", ptSpacing: 34, minRadius: 6,  wbStroke: 1.4 },
    "print-state":  { label: "Print · state",  ptSpacing: 92, minRadius: 11, wbStroke: 1.6 },
  };

  // src/config.WIDTH_PRESETS (Epoch 18). The preview always log-normalizes the
  // flow ramp (HydroUX.applyStyles), so only min/max/gamma are surfaced here;
  // that already makes state (10:1) vs watershed (4:1) visibly different.
  const WIDTH_PRESETS = {
    state:     { label: "State",     minW: 0.35, maxW: 3.5, gamma: 1.0 },
    basin:     { label: "Basin",     minW: 0.35, maxW: 2.1, gamma: 0.45 },
    watershed: { label: "Watershed", minW: 0.35, maxW: 1.4, gamma: 0.5 },
  };

  // Per-family caps — the procedural network has thousands of segments, so a
  // tasteful preview samples a capped subset deterministically rather than
  // marking every candidate (which would be visual noise). Real renders show
  // every feature; these caps are a *preview* readability choice.
  const CAPS = { spring: 40, waterfall: 12, rapids: 16, lake: 24, wetland: 14, playa: 7, perennial_ice: 6 };

  // Feature anchor for a segment: its downstream endpoint. Works for both the
  // procedural 3-point segs (last === pts[2]) and the real-geometry polylines
  // (variable length) — so features scatter across the actual river network.
  function anchor(seg) { const p = seg.pts; return p[p.length - 1]; }

  // ---- Real geometry → procedural `net` shape -----------------------------
  // Convert a HydroGeo record (real simplified NHD flowlines extracted from a
  // rendered pipeline export by tools/extract_preview_geo.py) into the exact
  // `net` object HydroUX.buildSvg / applyStyles and augment() consume. This is
  // what makes the preview read as actual Washington / Clark County while every
  // live control (palette, width preset, glow, seasonal, feature toggles) keeps
  // restyling it. geo = { w, h, groups:[{huc,color,paths:[{w,pts}]}] }.
  function netFromGeo(geo) {
    // Fit native projected bounds into the procedural viewBox, preserving aspect.
    const s = Math.min(1000 / geo.w, 1177 / geo.h);
    const vw = geo.w * s, vh = geo.h * s;
    const rnd = H.mulberry32(0x6E0 ^ geo.groups.length ^ Math.round(geo.w));

    // Width quantiles → synthesize drainage topology (children count) so the
    // augment heuristics (headwater tips vs. confluences) fire on real lines:
    // thin reaches read as leaves (springs/ice), fat reaches as confluences.
    const widths = [];
    geo.groups.forEach((g) => g.paths.forEach((p) => widths.push(p.w)));
    widths.sort((a, b) => a - b);
    const q = (f) => widths[Math.floor(f * (widths.length - 1))] || 0;
    const wLo = q(0.55), wHi = q(0.9);

    let maxFlow = 1;
    const basins = geo.groups.map((g) => {
      const phase = rnd() < 0.5 ? (3 + rnd() * 2) : (11 + rnd() * 2) % 12;
      const segs = g.paths.map((p) => {
        const pts = p.pts.map((xy) => [xy[0] * s, xy[1] * s]);
        const flow = p.w;
        if (flow > maxFlow) maxFlow = flow;
        const nCh = flow >= wHi ? 2 : (flow >= wLo ? 1 : 0);
        return { pts, flow, children: new Array(nCh), phase, elev: 0 };
      });
      return { segs, phase, color: g.color, huc: g.huc };
    });

    // Stylized elevation is the inverse of flow (thin tributaries ride high),
    // so springs/perennial-ice land on headwater tips and wetlands on the big
    // low-gradient reaches — geographically plausible without a real DEM.
    let maxElev = 1;
    basins.forEach((b) => b.segs.forEach((sg) => {
      sg.elev = maxFlow - sg.flow;
      if (sg.elev > maxElev) maxElev = sg.elev;
    }));

    return { basins, maxFlow, maxElev, viewBox: { w: vw, h: vh }, unitScale: 1, geo: true };
  }

  // Build a net for a UX `state`, preferring real geometry when the matching
  // HydroGeo record is loaded; falls back to the procedural network otherwise.
  // Washington whole-state → HydroGeo.wa; Clark County drill-down → HydroGeo.clark.
  function netForState(state) {
    const G = global.HydroGeo || {};
    const wantCounty = state.scope === "county" && state.county === "Clark";
    if (wantCounty && G.clark) {
      const net = netFromGeo(G.clark);
      net.countyNative = true; // already the county — don't crop the viewBox
      return net;
    }
    if (state.state === "Washington" && G.wa) return netFromGeo(G.wa);
    return H.generateNetwork(H.hash(state.state + (state.county || "")));
  }

  // Deterministic Fisher-Yates shuffle (seeded) → stable sample per network.
  function shuffle(arr, rnd) {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(rnd() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  }

  // ---- Deterministic augmentation -----------------------------------------
  // Attach net._features = { waterbodies:[{pts,cls,r}], points:[{x,y,family}],
  // areals:[{pts,family,r}] } once per network. Candidate segments are collected
  // by drainage position (springs at headwater tips, waterfalls/rapids on steep
  // reaches, lakes at confluences, wetlands/playas on valley floors, ice on the
  // highest tips), then each family is shuffled + capped. Seeded → identical for
  // a given network.
  function augment(net) {
    if (!net || net._features) return net;
    const rnd = H.mulberry32(0xF3A7 ^ Math.round((net.maxFlow || 1) * 131));
    const eMax = net.maxElev || 1;
    const cand = { spring: [], waterfall: [], rapids: [], lake: [], wetland: [], playa: [], perennial_ice: [] };

    net.basins.forEach((basin) => {
      basin.arid = rnd() < 0.34; // arid basins → playas (no wetlands)
      for (const seg of basin.segs) {
        const end = anchor(seg);
        const eNorm = (seg.elev || 0) / eMax;
        const isLeaf = seg.children.length === 0;
        if (isLeaf && eNorm > 0.55) cand.spring.push(seg);
        if (isLeaf && eNorm > 0.82 && !basin.arid) cand.perennial_ice.push(seg);
        if (!isLeaf && eNorm > 0.35 && eNorm < 0.82 && seg.flow > 2) {
          cand.waterfall.push(seg); cand.rapids.push(seg);
        }
        if (seg.children.length >= 2) cand.lake.push(seg);
        // Valley floors are wetlands broadly; arid basins also host playas.
        if (eNorm < 0.34 && seg.children.length >= 1) {
          cand.wetland.push(seg);
          if (basin.arid) cand.playa.push(seg);
        }
      }
    });

    // Keep waterfalls & rapids on distinct segments.
    const pick = (fam) => shuffle(cand[fam].slice(), rnd).slice(0, CAPS[fam]);
    const wf = pick("waterfall");
    const usedWf = new Set(wf);
    const rp = shuffle(cand.rapids.filter((s) => !usedWf.has(s)), rnd).slice(0, CAPS.rapids);

    const points = [];
    const P = (s) => { const a = anchor(s); return { x: a[0], y: a[1] }; };
    for (const s of pick("spring")) points.push({ ...P(s), family: "spring" });
    for (const s of wf) points.push({ ...P(s), family: "waterfall" });
    for (const s of rp) points.push({ ...P(s), family: "rapids" });

    // Mix big confluences (reservoirs/lakes that survive print declutter) with
    // some smaller ponds (pruned at print-state) so detail level visibly thins.
    const byFlow = cand.lake.slice().sort((a, b) => b.flow - a.flow);
    const nBig = Math.ceil(CAPS.lake * 0.6);
    const lakeSel = shuffle(
      byFlow.slice(0, nBig).concat(shuffle(byFlow.slice(nBig), rnd).slice(0, CAPS.lake - nBig)),
      rnd,
    );
    const waterbodies = lakeSel.map((s) => {
      const big = s.flow > net.maxFlow * 0.18;
      const cls = big ? "reservoir" : (s.flow > net.maxFlow * 0.05 ? "lake" : "pond");
      const rad = (cls === "pond" ? 9 : cls === "lake" ? 16 : 23) * (0.75 + rnd() * 0.5);
      const a = anchor(s);
      return Object.assign(blob(a[0], a[1], rad, rnd), { cls });
    });

    // Playas first, then wetlands off the remaining valley-floor segments.
    const pl = pick("playa");
    const usedPl = new Set(pl);
    const wl = shuffle(cand.wetland.filter((s) => !usedPl.has(s)), rnd).slice(0, CAPS.wetland);
    const areals = [];
    for (const s of wl) {
      const a = anchor(s);
      areals.push(blob(a[0] + (rnd() - 0.5) * 26, a[1], 12 + rnd() * 12, rnd, "wetland"));
    }
    for (const s of pl) {
      const a = anchor(s);
      areals.push(blob(a[0] + (rnd() - 0.5) * 30, a[1], 14 + rnd() * 14, rnd, "playa"));
    }
    for (const s of pick("perennial_ice")) {
      const a = anchor(s);
      areals.push(blob(a[0], a[1] - 6, 10 + rnd() * 10, rnd, "perennial_ice"));
    }

    net._features = { waterbodies, points, areals };
    return net;
  }

  // Irregular closed polygon around (cx,cy); `r` is a nominal radius (also used
  // as the declutter size proxy).
  function blob(cx, cy, r, rnd, family) {
    const n = 8 + Math.floor(rnd() * 4), pts = [];
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2;
      const rr = r * (0.72 + rnd() * 0.5);
      pts.push([cx + Math.cos(a) * rr, cy + Math.sin(a) * rr * 0.82]);
    }
    return { pts, r, family };
  }

  // ---- Deterministic density thinning (mirrors min_spacing / min_area) -----
  function thinPoints(items, spacing) {
    if (spacing <= 0) return items;
    const kept = [];
    for (const p of items) {
      if (kept.every((q) => Math.hypot(q.x - p.x, q.y - p.y) >= spacing)) kept.push(p);
    }
    return kept;
  }

  // ---- SVG helpers --------------------------------------------------------
  const SVGNS = "http://www.w3.org/2000/svg";
  function poly(pts) { return "M " + pts.map((p) => p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" L ") + " Z"; }
  function ensureGroup(svg, id, before) {
    let g = svg.querySelector("#" + id);
    if (!g) {
      g = document.createElementNS(SVGNS, "g");
      g.setAttribute("id", id);
      if (before) svg.insertBefore(g, before); else svg.appendChild(g);
    }
    g.innerHTML = "";
    return g;
  }

  // One point glyph as an SVG string. Shapes mirror POINT_GLYPHS: springs=dot,
  // waterfalls=chevron, rapids=tick.
  function glyph(p) {
    const st = POINT_STYLES[p.family], s = st.size, c = st.color;
    if (st.glyph === "dot")
      return `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="${(s / 2).toFixed(1)}" fill="${c}" stroke="none"/>`;
    if (st.glyph === "chevron")
      return `<path d="M ${(p.x - s / 2).toFixed(1)},${(p.y + s / 2).toFixed(1)} L ${p.x.toFixed(1)},${(p.y - s / 2).toFixed(1)} L ${(p.x + s / 2).toFixed(1)},${(p.y + s / 2).toFixed(1)}" fill="none" stroke="${c}" stroke-width="1.6"/>`;
    // tick — a short slanted zigzag
    return `<path d="M ${(p.x - s / 2).toFixed(1)},${(p.y + s / 3).toFixed(1)} L ${p.x.toFixed(1)},${(p.y - s / 3).toFixed(1)} L ${(p.x + s / 2).toFixed(1)},${(p.y + s / 3).toFixed(1)}" fill="none" stroke="${c}" stroke-width="1.6"/>`;
  }

  // Make sure the wetland hatch <pattern> exists in <defs> once.
  function ensureHatch(svg) {
    let defs = svg.querySelector("defs");
    if (!defs) { defs = document.createElementNS(SVGNS, "defs"); svg.insertBefore(defs, svg.firstChild); }
    if (svg.querySelector("#wetHatch")) return;
    const p = document.createElementNS(SVGNS, "pattern");
    p.setAttribute("id", "wetHatch");
    p.setAttribute("width", "7"); p.setAttribute("height", "7");
    p.setAttribute("patternUnits", "userSpaceOnUse");
    p.setAttribute("patternTransform", "rotate(45)");
    p.innerHTML = `<line x1="0" y1="0" x2="0" y2="7" stroke="${AREAL_STYLES.wetland.color}" stroke-width="1.1"/>`;
    defs.appendChild(p);
  }

  // ---- Render the feature layers onto a live preview SVG ------------------
  // state.feat = { lakes, natural, terrain } booleans; state.detail is a
  // DETAIL_PRESETS key. Areals + waterbodies render BELOW the flowline basins;
  // points render ABOVE. Called after HydroUX.applyStyles.
  function render(svg, net, state) {
    if (!svg || !net) return;
    augment(net);
    ensureHatch(svg);
    const det = DETAIL_PRESETS[state.detail] || DETAIL_PRESETS.screen;
    const F = net._features;
    const feat = state.feat || {};
    const firstBasin = svg.querySelector("g.basin");

    // Areals (below) — kept if radius clears the print threshold.
    const gA = ensureGroup(svg, "featAreals", firstBasin);
    if (feat.terrain) {
      for (const a of F.areals) {
        if (a.r < det.minRadius) continue;
        const st = AREAL_STYLES[a.family];
        if (st.fill === "hatch")
          gA.innerHTML += `<path d="${poly(a.pts)}" fill="url(#wetHatch)" stroke="${st.color}" stroke-width="0.8"/>`;
        else if (st.fill === "solid")
          gA.innerHTML += `<path d="${poly(a.pts)}" fill="${st.color}" fill-opacity="${st.opacity}" stroke="${st.color}" stroke-width="0.6"/>`;
        else
          gA.innerHTML += `<path d="${poly(a.pts)}" fill="none" stroke="${st.color}" stroke-width="0.9" stroke-dasharray="${st.dash}"/>`;
      }
    }

    // Waterbodies (below flowlines, above areals) — outlined polygons.
    const gW = ensureGroup(svg, "featWaterbodies", firstBasin);
    if (feat.lakes) {
      for (const wb of F.waterbodies) {
        if (wb.r < det.minRadius) continue;
        gW.innerHTML += `<path d="${poly(wb.pts)}" fill="none" stroke="${WATERBODY.color}" stroke-width="${det.wbStroke}"/>`;
      }
    }

    // Points (above everything) — thinned per family by the detail preset.
    const gP = ensureGroup(svg, "featPoints", null);
    if (feat.natural) {
      for (const fam of ["spring", "waterfall", "rapids"]) {
        const items = thinPoints(F.points.filter((p) => p.family === fam), det.ptSpacing);
        for (const p of items) gP.innerHTML += glyph(p);
      }
    }
  }

  // Count what's currently visible (for a "23 lakes · 8 waterfalls…" caption).
  function counts(net, state) {
    augment(net);
    const det = DETAIL_PRESETS[state.detail] || DETAIL_PRESETS.screen;
    const F = net._features, feat = state.feat || {};
    const c = { lake: 0, spring: 0, waterfall: 0, rapids: 0, wetland: 0, playa: 0, perennial_ice: 0 };
    if (feat.lakes) F.waterbodies.forEach((w) => { if (w.r >= det.minRadius) c.lake++; });
    if (feat.terrain) F.areals.forEach((a) => { if (a.r >= det.minRadius) c[a.family]++; });
    if (feat.natural) ["spring", "waterfall", "rapids"].forEach((fam) => {
      c[fam] = thinPoints(F.points.filter((p) => p.family === fam), det.ptSpacing).length;
    });
    return c;
  }

  // Apply a width preset onto `state` (mutates minW/maxW/gamma, sets widthMode
  // to flow). Returns the preset record for labels.
  function applyWidthPreset(state, name) {
    const p = WIDTH_PRESETS[name]; if (!p) return null;
    state.widthMode = "flow"; state.minW = p.minW; state.maxW = p.maxW; state.gamma = p.gamma;
    state.widthPreset = name;
    return p;
  }

  global.HydroFeatures = {
    WATERBODY, POINT_STYLES, AREAL_STYLES, DETAIL_PRESETS, WIDTH_PRESETS,
    augment, render, counts, applyWidthPreset,
    netFromGeo, netForState,
  };
})(typeof window !== "undefined" ? window : this);
