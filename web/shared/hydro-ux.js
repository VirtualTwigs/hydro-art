/* ==========================================================================
   Hydro-Art shared UX engine (classic script — exposes window.HydroUX)
   --------------------------------------------------------------------------
   Common client-side model shared by every web/ prototype so the mockups stay
   consistent and DRY. Loaded with a plain <script src> (not an ES module) so
   the prototypes keep working over file:// without a build or dev server.

   What lives here (the parts every prototype needs):
     - Ground-truth option data (states, counties, palettes, months) mirrored
       from the Python pipeline (src/config.py, src/coloring.py, render_common).
     - A deterministic procedural river-network generator + SVG builder, so a
       preview is available with no datasets (same trick as web/index.html).
     - A seasonal monthly-flow *simulation* mirroring tools/monthly_flow.py:
       widths are scaled on a fixed year-max so seasonal swell/retreat shows.
     - applyStyles(): maps a UX `state` object onto the live SVG.
     - mapping helpers: translate UX selections back into build.py CLI + YAML.
   None of this touches the real pipeline; it is a faithful client-side stand-in.
   ========================================================================== */
"use strict";

(function (global) {

  // ---- Ground-truth option data (mirrors the Python side) -----------------

  // src/config.SUPPORTED_REGIONS. The pipeline is OR/WA today; keep extensible.
  const STATES = [
    { id: "Oregon",     label: "Oregon",     huc4: ["1707","1708","1709","1710","1712","1801"] },
    { id: "Washington", label: "Washington", huc4: ["1701","1702","1703","1707","1708","1710","1711"] },
    { id: "California", label: "California", huc4: ["1710","1712","1801","1802","1803","1804","1805","1806","1807","1808","1809","1810"] },
  ];

  // Real county rosters (Census) for the two supported states. `render_county_clip`
  // clips to one of these polygons. Clark County, WA is the pipeline's demo county.
  const COUNTIES = {
    Oregon: ["Baker","Benton","Clackamas","Clatsop","Columbia","Coos","Crook","Curry",
      "Deschutes","Douglas","Gilliam","Grant","Harney","Hood River","Jackson","Jefferson",
      "Josephine","Klamath","Lake","Lane","Lincoln","Linn","Malheur","Marion","Morrow",
      "Multnomah","Polk","Sherman","Tillamook","Umatilla","Union","Wallowa","Wasco",
      "Washington","Wheeler","Yamhill"],
    Washington: ["Adams","Asotin","Benton","Chelan","Clallam","Clark","Columbia","Cowlitz",
      "Douglas","Ferry","Franklin","Garfield","Grant","Grays Harbor","Island","Jefferson",
      "King","Kitsap","Kittitas","Klickitat","Lewis","Lincoln","Mason","Okanogan","Pacific",
      "Pend Oreille","Pierce","San Juan","Skagit","Skamania","Snohomish","Spokane","Stevens",
      "Thurston","Wahkiakum","Walla Walla","Whatcom","Whitman","Yakima"],
    California: ["Alameda","Alpine","Amador","Butte","Calaveras","Colusa","Contra Costa",
      "Del Norte","El Dorado","Fresno","Glenn","Humboldt","Imperial","Inyo","Kern","Kings",
      "Lake","Lassen","Los Angeles","Madera","Marin","Mariposa","Mendocino","Merced","Modoc",
      "Mono","Monterey","Napa","Nevada","Orange","Placer","Plumas","Riverside","Sacramento",
      "San Benito","San Bernardino","San Diego","San Francisco","San Joaquin","San Luis Obispo",
      "San Mateo","Santa Barbara","Santa Clara","Santa Cruz","Shasta","Sierra","Siskiyou",
      "Solano","Sonoma","Stanislaus","Sutter","Tehama","Trinity","Tulare","Tuolumne","Ventura",
      "Yolo","Yuba"],
  };

  // Palettes. `neon` is the one shipped in src/coloring.PALETTES (config allows
  // only "neon" today); the rest are experimental UX proposals.
  const PALETTES = {
    neon:   ["#00ffff","#0a5cff","#4b0082","#9d00ff","#8f00ff","#ff00ff","#ff7a00","#ffd700","#aaff00","#00ffab","#00e0d1","#00ff5f"],
    aurora: ["#00ff9c","#00e0d1","#38b6ff","#5a7bff","#7a5cff","#00ffab","#2fffd0","#66ffcc","#3fa9ff","#8f7bff","#00d4a0","#41e0ff"],
    ember:  ["#ff3b00","#ff7a00","#ffb300","#ffd700","#ff5e3a","#ff2d55","#e0004d","#ff9c3a","#ffcf5e","#c41e3a","#ff6f61","#ffae42"],
    ice:    ["#e6ffff","#a8f0ff","#66d9ff","#38b6ff","#5a7bff","#b3ecff","#7fe3ff","#4fb0ff","#cfefff","#89cfff","#6fd7ff","#9fd8ff"],
  };
  // Hypsometric ramp for the "elevation" color mode (white summit -> deep-blue
  // sea), mirroring tools/render_state_mono.py.
  const HYPSO = ["#ffffff","#dff0ff","#a8d8ff","#66b6ff","#3f8fe6","#2f6bc4","#1f4a9c","#123a7a","#0a2a5c","#06213f"];

  // src/monthly_flow.MONTH_ABBR (and src/config parses these names in --months).
  const MONTH_ABBR = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  // src/config.SUPPORTED_HUC_LEVELS.
  const HUC_LEVELS = ["HUC2","HUC4","HUC6","HUC8","HUC10","HUC12"];

  // ---- Deterministic PRNG (so previews are reproducible per seed) ----------
  function mulberry32(a){return function(){a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};}
  function hash(str){let h=2166136261;for(let i=0;i<str.length;i++){h^=str.charCodeAt(i);h=Math.imul(h,16777619);}return h>>>0;}

  // ---- Procedural network model -------------------------------------------
  // net = { basins:[{segs:[{pts,flow,children,phase,elev}]}], maxFlow, viewBox, unitScale }
  const VB = { w: 1000, h: 1177 };

  function generateNetwork(seed, nBasins){
    nBasins = nBasins || 6;
    const rnd = mulberry32(seed);
    const basins = Array.from({length: nBasins}, () => ({ segs: [] }));
    const rootX = 500, rootY = 1120, spread = 2.1;
    for (let b = 0; b < nBasins; b++){
      const a0 = -Math.PI/2 - spread/2 + spread*(b+0.5)/nBasins + (rnd()-0.5)*0.15;
      // Each basin gets a seasonal peak month: some snowmelt (spring), some rain (winter).
      basins[b].phase = rnd() < 0.5 ? (3 + rnd()*2) : (11 + rnd()*2) % 12; // 0-based month
      grow(basins[b].segs, rootX, rootY, a0, 250, 10, rnd, basins[b].phase);
    }
    let maxFlow = 1, maxElev = 1;
    for (const basin of basins){
      for (let i = basin.segs.length - 1; i >= 0; i--){
        const s = basin.segs[i];
        s.flow = 1 + s.children.reduce((acc,c)=>acc + c.flow, 0);
        if (s.flow > maxFlow) maxFlow = s.flow;
        if (s.elev > maxElev) maxElev = s.elev;
      }
    }
    return { basins, maxFlow, maxElev, viewBox:{...VB}, unitScale: 1 };
  }

  function grow(out, x, y, ang, len, depth, rnd, phase){
    if (depth <= 0 || len < 6) return null;
    const midJit = (rnd()-0.5) * len * 0.25;
    const nx = x + Math.cos(ang)*len, ny = y + Math.sin(ang)*len;
    const mx = (x+nx)/2 + Math.cos(ang+Math.PI/2)*midJit;
    const my = (y+ny)/2 + Math.sin(ang+Math.PI/2)*midJit;
    // Stylized elevation: headwaters (higher up the tree / lower y) ride high.
    const elev = Math.max(0, (VB.h - ny)) * (0.7 + depth*0.05);
    const seg = { pts: [[x,y],[mx,my],[nx,ny]], children: [], flow: 1, phase, elev };
    out.push(seg);
    const branches = rnd() < 0.78 ? 2 : (rnd() < 0.7 ? 1 : 3);
    const spread = 0.35 + rnd()*0.5;
    for (let k = 0; k < branches; k++){
      const da = branches === 1 ? (rnd()-0.5)*0.4
               : (-spread/2 + spread*(k)/(branches-1)) + (rnd()-0.5)*0.2;
      const child = grow(out, nx, ny, ang + da, len*(0.66+rnd()*0.12), depth-1, rnd, phase);
      if (child) seg.children.push(child);
    }
    return seg;
  }

  // ---- Seasonal monthly-flow simulation (mirrors tools/monthly_flow.py) -----
  // Multiplier in ~[0.35, 1.9] for a basin at a given (0-based) month, peaking at
  // the basin's phase. Deterministic; no real climate data.
  function seasonalMultiplier(month0, phase){
    const amp = 0.55;
    return 1 + amp * Math.cos(2*Math.PI*(month0 - phase)/12);
  }
  // Fixed year-max so a fat January mainstem really looks fatter than August.
  function yearMaxFlow(net){
    let mx = 1;
    for (const b of net.basins) for (const s of b.segs)
      for (let m=0;m<12;m++) mx = Math.max(mx, s.flow * seasonalMultiplier(m, b.phase));
    return mx;
  }

  // ---- SVG builder --------------------------------------------------------
  function dOf(pts){ return "M " + pts.map(p=>p[0].toFixed(1)+","+p[1].toFixed(1)).join(" L "); }

  function buildSvg(net){
    const { basins, viewBox } = net;
    let s = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${viewBox.w} ${viewBox.h}" `
          + `fill="none" stroke-linecap="round" stroke-linejoin="round">`;
    s += `<defs><filter id="glow" x="-20%" y="-20%" width="140%" height="140%">`
       + `<feGaussianBlur id="glowBlur" stdDeviation="0" result="b"/>`
       + `<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>`;
    s += `<rect id="bgRect" x="0" y="0" width="${viewBox.w}" height="${viewBox.h}"/>`;
    basins.forEach((basin, bi) => {
      s += `<g class="basin" data-basin="${bi}">`;
      for (const seg of basin.segs){
        s += `<path data-flow="${seg.flow.toFixed(3)}" data-elev="${(seg.elev||0).toFixed(1)}" d="${dOf(seg.pts)}"/>`;
      }
      s += `</g>`;
    });
    return s + `</svg>`;
  }

  function rampColor(ramp, t){
    t = Math.max(0, Math.min(1, t));
    const x = t * (ramp.length - 1), i = Math.floor(x);
    return ramp[Math.min(ramp.length - 1, i)]; // nearest stop — plenty for a preview
  }

  // ---- Apply a UX `state` onto the live SVG -------------------------------
  // state: { colorMode:'watershed'|'single'|'elevation', palette, single, bg,
  //          widthMode:'flow'|'uniform', minW, maxW, gamma, glow, glowR,
  //          month (0-based, for the currently displayed frame) }
  function applyStyles(svg, net, state){
    if (!svg || !net) return;
    const scale = net.unitScale;
    const pal = PALETTES[state.palette] || PALETTES.neon;
    const yMax = net._yearMax || (net._yearMax = yearMaxFlow(net));
    const month0 = (state.month == null) ? 6 : state.month;

    svg.querySelector("#bgRect").setAttribute("fill", state.bg);
    svg.querySelector("#glowBlur").setAttribute("stdDeviation", state.glow ? (state.glowR*scale).toFixed(2) : "0");

    [...svg.querySelectorAll("g.basin")].forEach((g, bi) => {
      const phase = net.basins[bi].phase;
      const mult = seasonalMultiplier(month0, phase);
      let groupStroke = null;
      if (state.colorMode === "single") groupStroke = state.single;
      else if (state.colorMode === "watershed") groupStroke = pal[bi % pal.length];
      // elevation mode colors per-path below (per-segment), so leave group unset.
      if (groupStroke) g.setAttribute("stroke", groupStroke);
      g.setAttribute("filter", state.glow ? "url(#glow)" : "");

      for (const p of g.querySelectorAll("path")){
        // color
        if (state.colorMode === "elevation"){
          const e = parseFloat(p.getAttribute("data-elev")) / (net.maxElev || 1);
          p.setAttribute("stroke", rampColor(HYPSO, e));
        } else {
          p.removeAttribute("stroke"); // inherit group stroke
        }
        // width
        let wpx;
        if (state.widthMode === "uniform"){
          wpx = state.minW;
        } else {
          const f = parseFloat(p.getAttribute("data-flow")) * mult;
          const t = Math.pow(Math.log(f+1)/Math.log(yMax+1), state.gamma);
          wpx = state.minW + (state.maxW - state.minW) * t;
        }
        p.setAttribute("stroke-width", (wpx*scale).toFixed(3));
      }
    });
  }

  // ---- Mapping: UX selections -> build.py CLI + config.yaml ----------------
  function scopeToken(state){
    if (state.scope === "county" && state.county) return `county:${state.county},${stateAbbr(state.state)}`;
    return `region:${state.state}`;
  }
  function stateAbbr(name){ return {Washington:"WA", Oregon:"OR", California:"CA"}[name] || name; }

  function monthsToken(state){
    if (state.timeMode === "annual") return "annual (mean QAMA)";
    if (state.timeMode === "single") return MONTH_ABBR[state.monthStart] + " (single month)";
    return `${MONTH_ABBR[state.monthStart]}\u2013${MONTH_ABBR[state.monthEnd]} (range \u2192 animation)`;
  }

  // Emits a paste-runnable multi-line command. Roadmap #23 (color_by/width_by),
  // #24 (--county), and #25 (--months) have all SHIPPED, so their flags are now
  // emitted as real `build.py` options (src/cli.py) — no more `(proposed)`
  // markers. Two options are shipped-but-not-yet-rendered by the *2D* pipeline
  // and fail fast in build.py, so they carry an honest caveat note (never an
  // inline comment inside the `\`-continued block, which would break the paste):
  //   - color_by=elevation → needs the DEM subsystem (use tools/render_state_mono.py)
  //   - non-annual --months → parses, but live frames land in #27 (tools/render_monthly.py)
  function cliMapping(state){
    const cmd = [`--region ${state.state}`];
    const notes = [];
    if (state.scope === "county" && state.county)
      cmd.push(`--county "${state.county}"`);
    if (state.huc && state.huc !== "HUC4")
      cmd.push(`--huc-level ${state.huc}`);
    cmd.push(`--color-by ${state.colorMode}`);
    if (state.colorMode === "watershed"){
      cmd.push(`--palette ${state.palette}`);
      if (state.palette !== "neon")
        notes.push(`palette "${state.palette}" is a UX experiment; the pipeline ships only "neon" today.`);
    } else if (state.colorMode === "single"){
      cmd.push(`--single-color ${state.single}`);
    } else if (state.colorMode === "elevation"){
      notes.push("color_by=elevation needs the DEM subsystem; the 2D build.py fails fast (use tools/render_state_mono.py).");
    }
    if (state.widthMode === "flow")
      cmd.push(`--width-by flow --width-min ${state.minW} --width-max ${state.maxW} --width-gamma ${state.gamma}`);
    else
      cmd.push(`--width-by uniform`);
    if (state.timeMode !== "annual"){
      const m = state.timeMode === "single" ? (state.monthStart+1)
              : (state.monthStart+1) + "-" + (state.monthEnd+1);
      cmd.push(`--months ${m}`);
      notes.push("non-annual --months parses but the 2D build.py fails fast; live month frames land in #27 (use tools/render_monthly.py).");
    }
    if (state.glow) cmd.push(`--glow --glow-radius ${state.glowR}`);

    // background + base line width have no CLI flag (config-only) — see YAML.
    let out = ".venv/bin/python build.py \\\n  " + cmd.join(" \\\n  ");
    if (notes.length){
      out += "\n  # notes:";
      for (const n of notes) out += "\n  #   " + n;
    }
    return out;
  }

  function yamlMapping(state){
    const k = s => `<span class="k">${s}</span>`, q = s => `<span class="s">${s}</span>`,
          c = s => `<span class="c">${s}</span>`, nn = s => `<span class="n">${s}</span>`;
    const monthsVal = state.timeMode === "annual" ? "annual"
        : state.timeMode === "single" ? String(state.monthStart+1)
        : (state.monthStart+1) + "-" + (state.monthEnd+1);
    const L = [];
    L.push(c("# config.yaml — from the current studio selection"));
    L.push(`${k("region")}: [${state.state}]`);
    if (state.scope === "county" && state.county)
      L.push(`${k("county")}: ${q('"'+state.county+'"')}`);
    L.push(`${k("huc_level")}: ${state.huc}`);
    L.push(`${k("months")}: ${q('"'+monthsVal+'"')}` +
      (state.timeMode !== "annual" ? `        ${c("# parses; non-annual render lands in #27")}` : ""));
    L.push("");
    L.push(`${k("color_by")}: ${q('"'+state.colorMode+'"')}        ${c("# watershed | single | elevation")}`);
    if (state.colorMode === "watershed")
      L.push(`${k("palette")}: ${state.palette}` +
        (state.palette !== "neon" ? `         ${c("# only 'neon' ships today")}` : ""));
    if (state.colorMode === "single")
      L.push(`${k("single_color")}: ${q('"'+state.single+'"')}`);
    if (state.colorMode === "elevation")
      L.push(c("# elevation tint needs the DEM subsystem (fails fast in 2D build.py)"));
    L.push(`${k("background")}: ${q('"'+state.bg+'"')}`);
    L.push("");
    L.push(`${k("width_by")}: ${q('"'+state.widthMode+'"')}       ${c("# uniform | flow")}`);
    L.push(`${k("line_width")}: ${nn(state.minW)}        ${c("# base / uniform stroke")}`);
    if (state.widthMode === "flow"){
      L.push(`${k("width_min")}: ${nn(state.minW)}`);
      L.push(`${k("width_max")}: ${nn(state.maxW)}        ${c("# clamp so rivers stay visible")}`);
      L.push(`${k("width_gamma")}: ${nn(state.gamma)}      ${c("# 0.5≈sqrt spreads small streams")}`);
    }
    L.push("");
    L.push(`${k("glow")}: ${nn(state.glow)}`);
    if (state.glow) L.push(`${k("glow_radius")}: ${nn(state.glowR)}`);
    return L.join("\n");
  }

  // ---- Mapping self-check (determinism + CLI/YAML agreement) ---------------
  // Pure check that the two renderings of one `state` reference the same core
  // selections (region, county, months, color/width modes) and are stable. Used
  // by a headless Node smoke step; returns { ok, issues: [...] }.
  function mappingSelfCheck(state){
    const issues = [];
    const cli = cliMapping(state);
    // YAML carries HTML spans; strip tags for text matching.
    const yaml = yamlMapping(state).replace(/<[^>]+>/g, "");
    const both = (needle, label) => {
      if (!cli.includes(needle)) issues.push(`CLI missing ${label}: ${needle}`);
      if (!yaml.includes(needle)) issues.push(`YAML missing ${label}: ${needle}`);
    };
    both(state.state, "region");
    if (state.scope === "county" && state.county) both(state.county, "county");
    if (state.colorMode !== "watershed") both(state.colorMode, "color_by");
    // Determinism: identical input yields identical text.
    if (cli !== cliMapping(state)) issues.push("cliMapping is non-deterministic");
    if (yamlMapping(state) !== yamlMapping(state)) issues.push("yamlMapping is non-deterministic");
    return { ok: issues.length === 0, issues };
  }

  // ---- Live-run request payload (roadmap #27) ------------------------------
  // Pure function turning the UX `state` into the structured JSON body the local
  // job runner accepts (POST /api/render). These are real `src/config` keys — the
  // server rebuilds Settings through build_settings, so the emitted CLI string is
  // never shell-executed. Mirrors cliMapping's selections exactly.
  function renderRequest(state){
    const months = state.timeMode === "annual" ? "annual"
        : state.timeMode === "single" ? String(state.monthStart+1)
        : (state.monthStart+1) + "-" + (state.monthEnd+1);
    const req = {
      region: state.state,
      huc_level: state.huc,
      months: months,
      color_by: state.colorMode,
      width_by: state.widthMode,
      background: state.bg,
      line_width: state.minW,
      glow: !!state.glow,
    };
    if (state.scope === "county" && state.county) req.county = state.county;
    if (state.colorMode === "watershed") req.palette = state.palette;
    if (state.colorMode === "single") req.single_color = state.single;
    if (state.widthMode === "flow"){
      req.width_min = state.minW; req.width_max = state.maxW; req.width_gamma = state.gamma;
    }
    if (state.glow) req.glow_radius = state.glowR;
    return req;
  }

  // ---- Render recipes & named presets (roadmap #28) -----------------------
  // A *recipe* is the canonical, serializable subset of `state` that captures
  // exactly the reproducible art-direction selections. Preview-only fields
  // (previewSource/loadedName, the derived `month`, the RNG `_nudge`) are NOT
  // part of a recipe. All helpers here are pure/deterministic and file://-safe;
  // studio.html only wires UI to them. Testable headlessly in Node.

  const RECIPE_KEYS = [
    "state", "scope", "county", "huc", "timeMode", "monthStart", "monthEnd",
    "colorMode", "palette", "single", "bg", "widthMode", "minW", "maxW",
    "gamma", "glow", "glowR",
  ];
  const DEFAULT_RECIPE = {
    state: "Oregon", scope: "state", county: null, huc: "HUC4",
    timeMode: "annual", monthStart: 5, monthEnd: 8,
    colorMode: "watershed", palette: "neon", single: "#00e5ff", bg: "#05060a",
    widthMode: "flow", minW: 0.5, maxW: 2.0, gamma: 0.5, glow: false, glowR: 2.5,
  };
  const HEX6 = /^#[0-9a-fA-F]{6}$/;

  function _num(v) { const n = Number(v); return Number.isFinite(n) ? n : null; }
  function _clamp(n, lo, hi) { return Math.min(hi, Math.max(lo, n)); }
  function _isStateId(id) { return STATES.some((s) => s.id === id); }

  // Validate one recipe field independently; returns the accepted value or
  // `undefined` if the input is unusable (caller decides fallback).
  function _validateKey(key, v) {
    switch (key) {
      case "state": return _isStateId(v) ? v : undefined;
      case "scope": return v === "county" ? "county" : (v === "state" ? "state" : undefined);
      case "county": return (v === null || (typeof v === "string" && v.length)) ? v : undefined;
      case "huc": return HUC_LEVELS.includes(v) ? v : undefined;
      case "timeMode": return ["annual", "single", "range"].includes(v) ? v : undefined;
      case "monthStart":
      case "monthEnd": { const n = _num(v); return n === null ? undefined : _clamp(Math.round(n), 0, 11); }
      case "colorMode": return ["watershed", "single", "elevation"].includes(v) ? v : undefined;
      case "palette": return Object.prototype.hasOwnProperty.call(PALETTES, v) ? v : undefined;
      case "single":
      case "bg": return (typeof v === "string" && HEX6.test(v)) ? v : undefined;
      case "widthMode": return ["flow", "uniform"].includes(v) ? v : undefined;
      case "minW": { const n = _num(v); return n === null ? undefined : _clamp(n, 0.05, 10); }
      case "maxW": { const n = _num(v); return n === null ? undefined : _clamp(n, 0.05, 20); }
      case "gamma": { const n = _num(v); return n === null ? undefined : _clamp(n, 0.05, 4); }
      case "glowR": { const n = _num(v); return n === null ? undefined : _clamp(n, 0, 30); }
      case "glow": return Boolean(v);
      default: return undefined;
    }
  }

  // Reconcile county with scope+state so a recipe is always self-consistent.
  function _coherceCounty(rec) {
    if (rec.scope !== "county") { rec.county = null; return rec; }
    const roster = COUNTIES[rec.state] || [];
    if (!roster.includes(rec.county)) rec.county = roster[0] || null;
    return rec;
  }

  // Full sanitize: every key validated/clamped, missing keys filled from
  // DEFAULT_RECIPE, cross-field county/scope coherence enforced. Returns a
  // complete recipe, or null if `obj` is not a usable plain object.
  function sanitizeRecipe(obj) {
    if (!obj || typeof obj !== "object" || Array.isArray(obj)) return null;
    const out = Object.assign({}, DEFAULT_RECIPE);
    for (const key of RECIPE_KEYS) {
      if (key === "glow") { out.glow = Boolean(obj.glow); continue; }
      const v = _validateKey(key, obj[key]);
      if (v !== undefined) out[key] = v;
    }
    return _coherceCounty(out);
  }

  // Canonical recipe for a live `state` (drops preview-only fields, sanitizes).
  function toRecipe(state) {
    if (!state || typeof state !== "object") return null;
    const picked = {};
    for (const key of RECIPE_KEYS) picked[key] = state[key];
    return sanitizeRecipe(picked);
  }

  // base64url primitives — btoa/atob in the browser, Buffer in Node, so the
  // round-trip is identical in both and testable headlessly.
  function _b64encode(str) {
    if (typeof btoa === "function") return btoa(unescape(encodeURIComponent(str)));
    return Buffer.from(str, "utf-8").toString("base64");
  }
  function _b64decode(b64) {
    if (typeof atob === "function") return decodeURIComponent(escape(atob(b64)));
    return Buffer.from(b64, "base64").toString("utf-8");
  }
  function b64url(str) {
    return _b64encode(str).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }
  function b64urlDecode(s) {
    let t = String(s).replace(/-/g, "+").replace(/_/g, "/");
    while (t.length % 4) t += "=";
    return _b64decode(t);
  }

  function encodeRecipe(state) { return b64url(JSON.stringify(toRecipe(state))); }
  function decodeRecipe(str) {
    try {
      const obj = JSON.parse(b64urlDecode(str));
      return sanitizeRecipe(obj);
    } catch (e) { return null; }
  }

  // Merge a (possibly partial) recipe onto a live state, validating each key
  // that is present. Preview-only fields on `state` are preserved. Absent keys
  // are left untouched (so partial presets only change what they name).
  function applyRecipe(state, recipe) {
    const out = Object.assign({}, state);
    if (recipe && typeof recipe === "object" && !Array.isArray(recipe)) {
      for (const key of RECIPE_KEYS) {
        if (!(key in recipe)) continue;
        const v = _validateKey(key, recipe[key]);
        if (v !== undefined) out[key] = v;
      }
      _coherceCounty(out);
    }
    return out;
  }

  // Named preset catalog. Each `recipe` is a (possibly partial) recipe merged
  // over the current selection. `kind` is a UX grouping hint.
  const PRESETS = [
    { id: "or-screen", label: "Oregon \u00b7 screen", kind: "state",
      recipe: { state: "Oregon", scope: "state", county: null, colorMode: "watershed",
                palette: "neon", widthMode: "flow", glow: false } },
    { id: "clark-print", label: "Clark County \u00b7 print", kind: "county",
      recipe: { state: "Washington", scope: "county", county: "Clark", colorMode: "watershed",
                palette: "ice", widthMode: "uniform", glow: false, bg: "#0a0f14" } },
    { id: "print-mono", label: "Print \u00b7 elevation", kind: "print",
      recipe: { colorMode: "elevation", bg: "#05060a", widthMode: "flow" } },
    { id: "screen-glow", label: "Screen \u00b7 neon glow", kind: "screen",
      recipe: { colorMode: "watershed", palette: "neon", glow: true } },
  ];
  function presetById(id) { return PRESETS.find((p) => p.id === id) || null; }
  function applyPreset(state, id) {
    const p = presetById(id);
    return p ? applyRecipe(state, p.recipe) : Object.assign({}, state);
  }

  // ---- View helpers (DOM; browser-only) -----------------------------------
  // Small helpers shared by the studio + prototype pages so the swatch,
  // month-timeline, county-select, and segmented-control/range view logic lives
  // in one place instead of being copy-pasted per page. They read the already
  // exported option data (PALETTES/COUNTIES/MONTH_ABBR) plus the page's mutable
  // `state`, and write to the fixed element IDs every page shares (#swatches,
  // #county, #timeline, #tlLabel). The event-binding helpers (seg/bindRange)
  // take the page's re-render callback as `after`, since each page repaints
  // differently. `document` is only touched inside the bodies, so this module
  // still loads under Node (the .cjs recipe test never calls these).

  function drawSwatches(state) {
    document.getElementById("swatches").innerHTML =
      PALETTES[state.palette].map((c) => `<i style="background:${c}"></i>`).join("");
  }

  function fillCounties(state) {
    const opts = COUNTIES[state.state];
    document.getElementById("county").innerHTML =
      opts.map((c) => `<option value="${c}">${c}</option>`).join("");
    state.county = opts[0];
  }

  function buildTimeline(state) {
    document.getElementById("timeline").innerHTML =
      MONTH_ABBR.map((m, i) => `<div class="mo" data-m="${i}">${m}</div>`).join("");
    paintTimeline(state);
  }

  function paintTimeline(state) {
    const tl = document.getElementById("timeline");
    [...tl.children].forEach((c, i) => {
      c.classList.remove("in-range", "edge");
      if (state.timeMode === "single" && i === state.monthStart) c.classList.add("edge");
      if (state.timeMode === "range") {
        if (i === state.monthStart || i === state.monthEnd) c.classList.add("edge");
        else if (i > state.monthStart && i < state.monthEnd) c.classList.add("in-range");
      }
    });
    document.getElementById("tlLabel").textContent =
      state.timeMode === "range"
        ? `${MONTH_ABBR[state.monthStart]}\u2013${MONTH_ABBR[state.monthEnd]}`
        : MONTH_ABBR[state.monthStart];
  }

  // Segmented button group: on click, mark the clicked button active, write its
  // `data-v` into `state[key]`, then run `after` (the page's re-render).
  function seg(state, id, key, after) {
    const box = document.getElementById(id);
    box.addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      [...box.children].forEach((x) => x.classList.toggle("active", x === b));
      state[key] = b.dataset.v; after();
    });
  }

  // Range input bound to `state[key]` (parsed float); optionally writes a
  // formatted value into `#valId`, then runs `after`.
  function bindRange(state, id, key, fmt, valId, after) {
    document.getElementById(id).addEventListener("input", (e) => {
      state[key] = parseFloat(e.target.value);
      if (valId) document.getElementById(valId).textContent = fmt(state[key]);
      after();
    });
  }

  // ---- Public surface -----------------------------------------------------
  const HydroUX = {
    STATES, COUNTIES, PALETTES, HYPSO, MONTH_ABBR, HUC_LEVELS,
    mulberry32, hash, generateNetwork, buildSvg, applyStyles,
    seasonalMultiplier, yearMaxFlow,
    cliMapping, yamlMapping, scopeToken, monthsToken, stateAbbr,
    mappingSelfCheck, renderRequest,
    RECIPE_KEYS, DEFAULT_RECIPE,
    toRecipe, sanitizeRecipe, encodeRecipe, decodeRecipe, applyRecipe,
    b64url, b64urlDecode,
    PRESETS, presetById, applyPreset,
    drawSwatches, fillCounties, buildTimeline, paintTimeline, seg, bindRange,
  };
  global.HydroUX = HydroUX;
  if (typeof module !== "undefined" && module.exports) module.exports = HydroUX;

})(typeof window !== "undefined" ? window : (typeof globalThis !== "undefined" ? globalThis : this));
