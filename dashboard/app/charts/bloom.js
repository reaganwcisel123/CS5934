// "A Commonwealth in Bloom" — every VA county drawn as a dogwood. Four bracts:
// length = an ACS SDoH axis, color = a CDC PLACES outcome; eight bud circles =
// worst-quartile flags. ACS values are null without CENSUS_API_KEY: pending-ness
// shows via the provenance pill and muted/dashed buds, never on the petal outline.
(function(A){
  const { showTT, moveTT, hideTT } = A.tooltip;
  const fmt1 = d3.format(".1f");
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  // Petal axis -> the PLACES outcome that colors it.
  const AXES = [
    { key: "N", pos: "top",    label: "Economic deprivation", measure: "bphigh",     measureLabel: "Hypertension" },
    { key: "E", pos: "right",  label: "Uninsured",             measure: "diabetes",   measureLabel: "Diabetes" },
    { key: "S", pos: "bottom", label: "Demographic demand",    measure: "depression", measureLabel: "Depression" },
    { key: "W", pos: "left",   label: "Access barriers",       measure: "smoking",    measureLabel: "Smoking" },
  ];
  const ANGLE = { N: 180, E: -90, S: 0, W: 90 };

  // The eight bud circles (7 ring + 1 center). group: which record bucket holds it.
  const BUD_VARS = [
    { k: "poverty_rate",    label: "Poverty rate",       group: "sdoh" },
    { k: "uninsured_rate",  label: "Uninsured",          group: "sdoh" },
    { k: "age65_pct",       label: "Age 65 and over",    group: "sdoh" },
    { k: "disability_pct",  label: "Disability",         group: "sdoh" },
    { k: "no_vehicle_pct",  label: "No vehicle",         group: "sdoh" },
    { k: "broadband_pct",   label: "Broadband access",   group: "sdoh", invert: true },
    { k: "bphigh",          label: "Hypertension",       group: "outcomes" },
    { k: "depression",      label: "Depression",         group: "outcomes" },
  ];
  const rawVal = (r, v) => (v.group === "sdoh" ? r.sdoh : r.outcomes)?.[v.k] ?? null;

  // Beyond the 4 pillar petals and 8 bud indicators: the rest of the "vast
  // feature set" a county record carries, checked for whether it is
  // quantitatively dire too. `get` reads straight off the raw record (`r`),
  // not the sdoh/outcomes split BUD_VARS/AXES use, so this can reach fields
  // anywhere on the record. Optional chaining throughout so this never throws
  // on an older atlas snapshot that predates a given field.
  const CRITICAL_CANDIDATES = [
    { id: "obesity", label: "Obesity", unit: "%", get: r => r.outcomes?.obesity },
    { id: "mhlth", label: "Frequent mental distress", unit: "%", get: r => r.outcomes?.mhlth },
    { id: "dom.economic", label: "Economic hardship", unit: "/100", get: r => r.dom?.economic },
    { id: "dom.education", label: "Low educational attainment", unit: "/100", get: r => r.dom?.education },
    { id: "dom.food", label: "Food & housing burden", unit: "/100", get: r => r.dom?.food },
    { id: "dom.environment", label: "Environmental burden", unit: "/100", get: r => r.dom?.environment },
    { id: "dom.access", label: "Care-access burden", unit: "/100", get: r => r.dom?.access },
    { id: "hpsaScore", label: "Primary-care shortage (HPSA)", unit: "/26", get: r => r.hpsaScore },
    { id: "needIndex", label: "Composite unmet-need index", unit: "/100", get: r => r.needIndex },
    // Present once the county-health-indicators expansion has been built; None/undefined otherwise.
    { id: "hpsaScoreMentalHealth", label: "Mental-health shortage (HPSA)", unit: "/26", get: r => r.hpsaScoreMentalHealth },
    { id: "hpsaScoreDental", label: "Dental shortage (HPSA)", unit: "/26", get: r => r.hpsaScoreDental },
    {
      id: "chronicDiseaseRate", label: "Leading hospitalization rate", unit: "/100k",
      get: r => r.chronicDiseaseRisk?.rate,
      detail: r => r.chronicDiseaseRisk?.leadingCondition ? `Leading condition: ${r.chronicDiseaseRisk.leadingCondition}` : null,
    },
  ];
  // The 4 pillar petals and 8 bud indicators, reshaped to the same {id, label,
  // unit, get} shape as CRITICAL_CANDIDATES so all three pools can be ranked
  // together by percentile -- one shared mechanism, not three.
  function _fullCandidatePool(){
    return [
      ...AXES.map(a => ({ id: "ax:" + a.key, label: a.measureLabel, unit: "%", get: r => r.outcomes?.[a.measure] })),
      ...BUD_VARS.map(v => ({ id: "bud:" + v.k, label: v.label, unit: "%", invert: v.invert, get: r => rawVal(r, v) })),
      ...CRITICAL_CANDIDATES,
    ];
  }

  /* ---------------------------- derive real data --------------------------- */
  // Pure transform: county records + geo -> per-county glyph geometry inputs.
  // No DOM here, so it's cheap to recompute on every records/geo change.
  function deriveBloomData(records, geo){
    const byFips = new Map(records.map(r => [r.id, r]));
    const features = geo.features.filter(f => byFips.has(f.properties.county_fips));

    // Petal color pulls from AXES.measure (bphigh/diabetes/depression/smoking),
    // which only partly overlaps BUD_VARS (bphigh/depression are shared; diabetes
    // and smoking are petal-color-only). Build normalization scales over the
    // union so every measure actually driving a visual gets a real domain.
    const MEASURE_DESCRIPTORS = BUD_VARS.concat(
      AXES.filter(a => !BUD_VARS.some(v => v.k === a.measure)).map(a => ({ k: a.measure, group: "outcomes" }))
    );

    // A whole-column stub (e.g. sdoh.* before CENSUS_API_KEY is set) reads as
    // "pending" rather than silently rendering as a fabricated neutral value.
    const pending = new Set();
    BUD_VARS.forEach(v => {
      if(features.every(f => rawVal(byFips.get(f.properties.county_fips), v) == null)) pending.add(v.k);
    });

    // Data-driven normalization: statewide min-max per indicator (not a guessed
    // fixed range), so the glyph reflects whatever the real distribution is.
    const scales = {};
    MEASURE_DESCRIPTORS.forEach(v => {
      const vals = features.map(f => rawVal(byFips.get(f.properties.county_fips), v)).filter(x => x != null);
      if(!vals.length) return;
      const [lo, hi] = d3.extent(vals);
      scales[v.k] = d3.scaleLinear().domain([lo, hi > lo ? hi : lo + 1]).range([0, 1]).clamp(true);
    });
    const norm = (k, raw) => (raw == null || !scales[k]) ? 0.5 : scales[k](raw);
    const normDir = (v, raw) => { const n = norm(v.k, raw); return v.invert ? 1 - n : n; };

    // Worst-quartile threshold per indicator (75th pct; 25th when lower = worse).
    const thr = {};
    BUD_VARS.forEach(v => {
      const vals = features.map(f => rawVal(byFips.get(f.properties.county_fips), v)).filter(x => x != null).sort(d3.ascending);
      if(vals.length) thr[v.k] = d3.quantile(vals, v.invert ? 0.25 : 0.75);
    });

    // Same worst-quartile threshold, applied to the 4 petal-color measures too
    // (not just the 8 bud indicators) -- this is what makes a petal's stroke
    // flip to the stark "dire" treatment below.
    const axThr = {};
    AXES.forEach(a => {
      const vals = features.map(f => byFips.get(f.properties.county_fips).outcomes?.[a.measure]).filter(x => x != null).sort(d3.ascending);
      if(vals.length) axThr[a.key] = d3.quantile(vals, 0.75);
    });

    // Every candidate (4 petals + 8 buds + the wider CRITICAL_CANDIDATES pool)
    // with its own statewide worst-quartile threshold and the sorted value
    // list needed to rank "how dire" a raw value is via percentile -- the
    // common currency that makes a %-scale outcome, a /26 HPSA score, and a
    // /100k hospitalization rate comparable enough to pick a single "most
    // critical" feature per county.
    const candidatePool = _fullCandidatePool().map(d => {
      const vals = features.map(f => d.get(byFips.get(f.properties.county_fips))).filter(x => x != null).sort(d3.ascending);
      const threshold = vals.length ? d3.quantile(vals, d.invert ? 0.25 : 0.75) : null;
      return { ...d, vals, threshold };
    }).filter(d => d.threshold != null);

    const counties = features.map(f => {
      const r = byFips.get(f.properties.county_fips);
      // Defensive: a record from a data source that predates the sdoh field
      // group (e.g. a live DB not yet reloaded) may lack it entirely.
      const sdoh = r.sdoh || {}, outcomes = r.outcomes || {};
      const ax = {
        N: normDir(BUD_VARS[0], sdoh.poverty_rate),
        E: normDir(BUD_VARS[1], sdoh.uninsured_rate),
        S: d3.mean([normDir(BUD_VARS[2], sdoh.age65_pct), normDir(BUD_VARS[3], sdoh.disability_pct)]),
        W: d3.mean([normDir(BUD_VARS[4], sdoh.no_vehicle_pct), normDir(BUD_VARS[5], sdoh.broadband_pct)]),
      };
      const measureNorm = {};
      AXES.forEach(a => { measureNorm[a.key] = norm(a.measure, outcomes[a.measure]); });
      const filled = BUD_VARS.map(v => {
        const raw = rawVal(r, v);
        if(raw == null || thr[v.k] == null) return null; // pending, not "not filled"
        return v.invert ? raw <= thr[v.k] : raw >= thr[v.k];
      });
      const filledCount = filled.filter(x => x === true).length;
      const availableCount = filled.filter(x => x !== null).length;

      const axCritical = {};
      AXES.forEach(a => {
        const raw = outcomes[a.measure];
        axCritical[a.key] = raw != null && axThr[a.key] != null && raw >= axThr[a.key];
      });

      // The single indicator (across all three pools) furthest above its own
      // threshold, ranked by percentile so differently-scaled indicators are
      // comparable. null when nothing about this county crosses a threshold.
      let mostCritical = null;
      for(const d of candidatePool){
        const raw = d.get(r);
        if(raw == null) continue;
        const isCritical = d.invert ? raw <= d.threshold : raw >= d.threshold;
        if(!isCritical) continue;
        const percentile = d.vals.filter(v => v <= raw).length / d.vals.length;
        if(!mostCritical || percentile > mostCritical.percentile){
          mostCritical = {
            id: d.id, label: d.label, unit: d.unit, raw, threshold: d.threshold,
            percentile, detail: d.detail ? d.detail(r) : null,
          };
        }
      }

      return {
        id: f.properties.county_fips, name: f.properties.name, region: f.properties.region,
        feature: f, r, ax, measureNorm, filled, filledCount, availableCount,
        axCritical, mostCritical,
      };
    });

    return { counties, pending, thr, axThr };
  }

  /* -------------------------------- glyph geometry -------------------------------- */
  const BUD_R = 2.15, RING_R = 5.2, CORE = 3.5;
  const LEN = d3.scaleLinear([0, 1], [5, 32]);
  const budPts = [[0, 0]].concat(d3.range(7).map(k => { const a = k * 2 * Math.PI / 7; return [RING_R * Math.cos(a), RING_R * Math.sin(a)]; }));
  const bractW = L => clamp(L * 0.92, 5, 26);
  // Per-axis color (N/E/S/W) — the saturated version drives the petal fill
  // (gradient tip), the desaturated AX_OUTLINE drives the petal's own
  // boundary stroke so the outline reads as a quiet edge, not a second
  // competing color signal.
  const AX_STROKE = { N: "#c65461", E: "#5b83c2", S: "#8a63bd", W: "#d59a33" };
  const muteStroke = hex => { const c = d3.hsl(hex); c.s *= 0.4; c.l = Math.min(0.75, c.l + 0.1); return c.formatHex(); };
  const AX_OUTLINE = Object.fromEntries(Object.entries(AX_STROKE).map(([k, v]) => [k, muteStroke(v)]));
  // Bud cluster scales with breadth of need: 0.50 (nothing in the worst
  // quartile) up to 0.92 (all 8 indicators flagged) — a second, independent
  // visual signal alongside petal length/color.
  const budScale = c => 0.50 + 0.42 * (c.filledCount / 8);
  function bractPath(L){
    const W = bractW(L), tipY = CORE + L, lob = W * 0.18;
    return `M 0 ${CORE}
      C ${-W * 0.16} ${CORE + L * 0.08}, ${-W * 0.44} ${CORE + L * 0.28}, ${-W * 0.50} ${CORE + L * 0.60}
      C ${-W * 0.53} ${CORE + L * 0.80}, ${-W * 0.36} ${CORE + L * 0.985}, ${-lob} ${tipY}
      A ${lob} ${lob * 0.88} 0 0 1 ${lob} ${tipY}
      C ${W * 0.36} ${CORE + L * 0.985}, ${W * 0.53} ${CORE + L * 0.80}, ${W * 0.50} ${CORE + L * 0.60}
      C ${W * 0.44} ${CORE + L * 0.28}, ${W * 0.16} ${CORE + L * 0.08}, 0 ${CORE} Z`;
  }
  function notchStain(L){
    const W = bractW(L), tipY = CORE + L, lob = W * 0.18;
    return `M ${-lob} ${tipY} A ${lob} ${lob * 0.88} 0 0 1 ${lob} ${tipY}`;
  }
  function bractVeins(L){
    const W = bractW(L), tipY = CORE + L;
    return `M 0 ${CORE + 2} L 0 ${tipY - bractW(L) * 0.16 - 1.5}
      M 0 ${CORE + 3} Q ${-W * 0.20} ${CORE + L * 0.5}, ${-W * 0.30} ${CORE + L * 0.88}
      M 0 ${CORE + 3} Q ${W * 0.20} ${CORE + L * 0.5}, ${W * 0.30} ${CORE + L * 0.88}`;
  }
  // Contrast stretch (endpoints and midpoint pinned, 0/0.5/1 -> 0/0.5/1) so
  // high-value petals read as sharply more saturated/colorful than low-value
  // ones instead of the muted gradation a raw linear map gives.
  const CONTRAST_P = 2.6;
  const contrastCurve = n => n <= 0.5 ? 0.5 * Math.pow(2 * n, CONTRAST_P) : 1 - 0.5 * Math.pow(2 * (1 - n), CONTRAST_P);
  // Radial gradient in the petal's local rotated frame (userSpaceOnUse):
  // glows outward from the bud to a saturated tip in the axis's own color.
  function pinkStops(sel, id, rawN, L, color){
    const n = contrastCurve(rawN);
    const m = clamp(1 - (0.08 + 0.72 * n), 0, 1);
    const pink = d3.interpolateLab("#f5e4ea", color)(n);
    const soft = d3.interpolateLab("#f5e4ea", color)(n * 0.85);
    const g = sel.append("radialGradient").attr("id", id).attr("gradientUnits", "userSpaceOnUse")
      .attr("cx", 0).attr("cy", 0).attr("r", CORE + L);
    g.append("stop").attr("offset", 0).attr("stop-color", "#fcfaf2");
    g.append("stop").attr("offset", Math.max(0, m - 0.10)).attr("stop-color", "#fcfaf2");
    g.append("stop").attr("offset", Math.min(1, m + 0.14)).attr("stop-color", soft);
    g.append("stop").attr("offset", 1).attr("stop-color", pink);
  }

  /* --------------------------------- render --------------------------------- */
  // Mounts the whole interactive piece (map + legend flower + detail panel)
  // into `host`. Returns { destroy }. Everything is scoped under `host` so two
  // instances (or a remount) never collide on DOM ids.
  function mountBloom(host, records, geo, opts){
    const sideRoot = (opts && opts.sideRoot) || host;
    const { counties, pending, thr, axThr } = deriveBloomData(records, geo);
    const byId = new Map(counties.map(c => [c.id, c]));
    const W = 1000, H = 640;

    const root = d3.select(host).html("");
    root.append("div").attr("class", "bloom-controls")
      .html(`<div class="bloom-viewname">A bloom for every county — hover for names, click for detail</div>
             <button class="bloom-back">← Back to the blooms</button>`);
    const stage = root.append("div").attr("class", "bloom-stage");
    const svg = stage.append("svg").attr("class", "bloom-svg").attr("viewBox", `0 0 ${W} ${H}`)
      .attr("role", "img").attr("aria-label", "Dogwood cartogram of Virginia county health burden.");
    const panel = stage.append("aside").attr("class", "bloom-panel");
    panel.append("button").attr("class", "bloom-panel-close").attr("aria-label", "Close").text("×");
    const panelBody = panel.append("div").attr("class", "bloom-panel-body");

    const viewName = root.select(".bloom-viewname");
    const backBtn = root.select(".bloom-back");

    const projection = d3.geoConicConformal().parallels([37.5, 39.5]).rotate([79, 0])
      .fitExtent([[36, 40], [W - 36, H - 44]], geo);
    const path = d3.geoPath(projection);

    const defs = svg.append("defs");
    const gMap = svg.append("g").attr("class", "bloom-maplayer");
    const gFlow = svg.append("g");

    counties.forEach(c => {
      const ctr = path.centroid(c.feature);
      c.mx = ctr[0]; c.my = ctr[1];
      c.rot = (Math.sin(parseInt(c.id, 10) * 12.9898) * 43758.5453 % 1) * 70 - 35;
      AXES.forEach(ax => pinkStops(defs, `bloom-g${c.id}${ax.key}`, c.measureNorm[ax.key], LEN(c.ax[ax.key]), AX_STROKE[ax.key]));
    });
    counties.forEach(c => { c.maxL = LEN(Math.max(c.ax.N, c.ax.E, c.ax.S, c.ax.W)); c.R = CORE + c.maxL + 0.4; c.x = c.mx; c.y = c.my; });

    // Petal-aware collision so the bloom relaxes apart without overlapping bracts.
    const DIRS = { N: -90, E: 0, S: 90, W: 180 };
    counties.forEach(c => {
      c.subs = [{ dx: 0, dy: 0, r: (RING_R + BUD_R + 0.9) * budScale(c) + 0.6 }];
      ["N", "E", "S", "W"].forEach(ax => {
        const L = LEN(c.ax[ax]), Wd = bractW(L), a = (DIRS[ax] + c.rot) * Math.PI / 180;
        [[0.32, 0.36], [0.60, 0.52], [0.86, 0.44]].forEach(([t, wf]) => {
          const rr = Math.max(Wd * wf, 2.2), dd = CORE + L * t;
          c.subs.push({ dx: Math.cos(a) * dd, dy: Math.sin(a) * dd, r: rr });
        });
      });
    });
    (function relax(){
      const PAD = 0.9, N = counties.length;
      function pass(pull){
        if(pull) for(const c of counties){ c.x += (c.mx - c.x) * pull; c.y += (c.my - c.y) * pull; }
        for(let a = 0; a < N; a++){
          const A_ = counties[a];
          for(let b = a + 1; b < N; b++){
            const B = counties[b];
            const cdx = A_.x - B.x, cdy = A_.y - B.y, RR = A_.R + B.R;
            if(cdx * cdx + cdy * cdy > RR * RR) continue;
            for(const si of A_.subs) for(const sj of B.subs){
              const wx = (A_.x + si.dx) - (B.x + sj.dx), wy = (A_.y + si.dy) - (B.y + sj.dy);
              const min = si.r + sj.r + PAD, d2 = wx * wx + wy * wy;
              if(d2 >= min * min) continue;
              const d = Math.sqrt(d2) || 1e-4, push = (min - d) / d * 0.5;
              A_.x += wx * push; A_.y += wy * push; B.x -= wx * push; B.y -= wy * push;
            }
          }
        }
      }
      for(let it = 0; it < 200; it++) pass(0.012);
      for(let it = 0; it < 70; it++) pass(0);
    })();
    counties.forEach(c => { c.cx = clamp(c.x, c.R, W - c.R); c.cy = clamp(c.y, c.R, H - c.R); });

    /* choropleth (heat mode) */
    const ramp = t => d3.interpolateLab("#fdfaf7", "#d95f88")(t);
    const cty = gMap.selectAll("path.bloom-cty").data(counties.map(c => c.feature)).join("path")
      .attr("class", "bloom-cty").attr("d", path).attr("fill", "var(--surface-sunken)").style("cursor", "pointer");
    gMap.attr("opacity", 0).style("pointer-events", "none");

    /* flowers */
    const flower = gFlow.selectAll("g.bloom-glyph").data(counties, c => c.id).join("g")
      .attr("class", "bloom-glyph").attr("transform", c => `translate(${c.mx},${c.my})`);
    flower.each(function(c){
      const g = d3.select(this);
      const bloomG = g.append("g").attr("class", "bloom-bloom").attr("transform", `rotate(${c.rot})`);
      ["N", "E", "S", "W"].forEach(axKey => {
        const L = LEN(c.ax[axKey]);
        const rot = bloomG.append("g").attr("transform", `rotate(${ANGLE[axKey]})`);
        // Stark, additive threshold treatment: the gradient fill (severity as
        // a smooth gradient) is untouched; a petal at/above its own statewide
        // worst-quartile threshold instead gets a bold pink outline in place
        // of its normal desaturated axis color, so a dire county is
        // unmistakable at a glance next to a healthy one, not just a shade
        // darker. Every outline is solid — the fill gradient alone carries
        // the color signal, so the boundary always stays a quiet, solid edge.
        const critical = c.axCritical[axKey];
        const br = rot.append("g").attr("class", "bloom-bract" + (critical ? " bloom-bract-critical" : "")).attr("transform", "scale(0)");
        // Outline stays bold and solid even when ACS is pending (see header note).
        br.append("path").attr("d", bractPath(L)).attr("fill", `url(#bloom-g${c.id}${axKey})`)
          .attr("stroke", critical ? "#db2777" : AX_OUTLINE[axKey])
          .attr("stroke-width", critical ? 2.6 : 1.6)
          .attr("stroke-opacity", 1)
          .attr("stroke-linejoin", "round");
        br.append("path").attr("d", bractVeins(L)).attr("fill", "none").attr("stroke", "#c98ba1").attr("stroke-width", 0.6).attr("stroke-opacity", 0.32);
        br.append("path").attr("d", notchStain(L)).attr("fill", "none").attr("stroke", "#8a4a3e").attr("stroke-width", 1.3).attr("stroke-opacity", 0.55).attr("stroke-linecap", "round");
      });
      const bud = g.append("g").attr("class", "bloom-bud").attr("transform", `rotate(${c.rot}) scale(${budScale(c)})`);
      bud.append("circle").attr("r", RING_R + BUD_R + 0.9).attr("class", "bloom-budring");
      budPts.forEach((p, pi) => {
        const isPending = c.filled[pi] === null;
        bud.append("circle").attr("cx", p[0]).attr("cy", p[1]).attr("r", BUD_R)
          .attr("class", "bloom-budc" + (c.filled[pi] ? " on" : "") + (isPending ? " pending" : ""));
      });
      g.append("circle").attr("class", "bloom-hit").attr("r", 11).attr("fill", "transparent");
      // "⚠" only when the county's single most-dire indicator isn't one
      // of the 4 pillar petals (those already read as dire via the stroke
      // treatment above) -- a cue that there's a critical factor hiding
      // outside what the glyph itself draws, worth opening the panel for.
      const hasHiddenCritical = c.mostCritical && !c.mostCritical.id.startsWith("ax:");
      g.append("text").attr("class", "bloom-hoverlbl").attr("y", -(CORE + c.maxL + 7)).attr("text-anchor", "middle")
        .text(c.name + (hasHiddenCritical ? " ⚠" : ""));
    });

    /* modes + lens */
    let mode = "bloom", lens = null, animating = false;
    function lensVal(c, k){
      if(k === "breadth") return c.availableCount ? c.filledCount / c.availableCount : 0.5;
      if(["axN", "axE", "axS", "axW"].includes(k)) return c.ax[k.slice(2)];
      const v = AXES.find(a => a.measure === k);
      return v ? c.measureNorm[v.key] : 0.5;
    }
    function lensPhrase(k){
      if(k === "breadth") return "Pinker counties land in the worst quartile on more of the eight indicators";
      const AX_LABEL = { axN: "economic deprivation", axE: "the uninsured share", axS: "demographic demand", axW: "access barriers" };
      if(AX_LABEL[k]) return `Pinker counties face heavier ${AX_LABEL[k]}`;
      const v = AXES.find(a => a.measure === k);
      return `Pinker counties carry a heavier burden of ${(v ? v.measureLabel : k).toLowerCase()}`;
    }
    function bloomG(g, scale){ g.selectAll(".bloom-bract").interrupt().transition().duration(520).delay((d, i) => i * 45).ease(d3.easeBackOut.overshoot(1.35)).attr("transform", `scale(${scale || 1})`); }
    function collapseG(g){ g.selectAll(".bloom-bract").interrupt().transition().duration(340).ease(d3.easeCubicIn).attr("transform", "scale(0)"); }
    function paintHeat(){
      // CSS (.bloom-cty transition: fill .5s) animates this, not d3 — avoids the
      // two transition systems fighting over the same attribute.
      cty.interrupt().attr("fill", f => { const c = byId.get(f.properties.county_fips); return c ? ramp(lensVal(c, lens)) : "var(--surface-sunken)"; });
      viewName.text(lensPhrase(lens));
    }
    async function setLens(k){
      if(animating) return;
      if(k === null || k === lens){ await toBloom(); return; }
      const wasHeat = mode === "heat";
      lens = k; mode = "heat";
      updateSelectorSel();
      if(wasHeat){ paintHeat(); return; }
      animating = true;
      try{
        closePanel();
        flower.each(function(){ collapseG(d3.select(this)); });
        gFlow.transition().duration(420).attr("opacity", 0);
        gFlow.style("pointer-events", "none");
        await new Promise(r => setTimeout(r, 380));
        gMap.style("pointer-events", "auto");
        gMap.transition().duration(400).attr("opacity", 1);
        paintHeat();
      } finally { animating = false; }
    }
    async function toBloom(){
      if(animating || mode === "bloom") return;
      animating = true;
      try{
        lens = null; mode = "bloom";
        updateSelectorSel(); closePanel();
        viewName.text("A bloom for every county — hover for names, click for detail");
        gMap.transition().duration(400).attr("opacity", 0);
        gMap.style("pointer-events", "none");
        await new Promise(r => setTimeout(r, 300));
        gFlow.attr("opacity", 1).style("pointer-events", "auto");
        flower.each(function(){ bloomG(d3.select(this), 1); });
      } finally { animating = false; }
    }
    backBtn.on("click", () => toBloom());

    /* detail panel */
    function openPanel(c, node){
      flower.select(".bloom-hit").attr("stroke", "none");
      if(node) d3.select(node).select(".bloom-hit").attr("stroke", "#2c5730").attr("stroke-dasharray", "2 3").attr("stroke-width", 1);
      const pendingNote = c.availableCount < BUD_VARS.length
        ? `<p class="bloom-pending-note">${BUD_VARS.length - c.availableCount} of ${BUD_VARS.length} indicators are Census ACS data, pending <code>CENSUS_API_KEY</code>.</p>` : "";
      const axRows = AXES.map(a => {
        const val = c.r.outcomes[a.measure];
        const critical = c.axCritical[a.key];
        const thrTxt = axThr[a.key] != null ? `≥ ${fmt1(axThr[a.key])}%` : "—";
        return `<tr class="${critical ? "bloom-row-critical" : ""}"><td>${a.label} (${a.pos})</td>
          <td class="v">${a.measureLabel}: ${val != null ? fmt1(val) + "%" : "—"}${critical ? " ⚠" : ""}</td>
          <td class="thr">${thrTxt}</td></tr>`;
      }).join("");
      const budRows = BUD_VARS.map((v, i) => {
        const raw = rawVal(c.r, v), f = c.filled[i];
        const cls = f === true ? "on" : f === false ? "" : "pending";
        const val = raw != null ? fmt1(raw) + "%" : "pending";
        return `<tr><td><span class="bloom-num ${cls}">${i + 1}</span>${v.label}</td><td class="v">${val}</td><td class="thr">${thr[v.k] != null ? (v.invert ? "≤ " : "≥ ") + fmt1(thr[v.k]) + "%" : "—"}</td></tr>`;
      }).join("");
      // The quantitative breakdown for whichever single indicator (across all
      // petals, buds, and the wider feature set) this county is furthest
      // above threshold on -- the "why is this county flagged" the user can
      // act on, not just a percentile.
      const criticalNote = c.mostCritical ? `
        <h4>Most critical factor</h4>
        <p class="bloom-critical-note">
          <strong>${c.mostCritical.label}</strong>: ${fmt1(c.mostCritical.raw)}${c.mostCritical.unit}
          vs. a dire threshold of ${fmt1(c.mostCritical.threshold)}${c.mostCritical.unit}
          &mdash; statewide ${Math.round(c.mostCritical.percentile * 100)}th percentile
          ${c.mostCritical.detail ? `<br>${c.mostCritical.detail}` : ""}
        </p>` : "";
      panelBody.html(`
        <h2>${c.name}</h2><p class="bloom-sub">${c.region} region</p>
        <p class="bloom-summary"><strong>${c.filledCount} of ${c.availableCount || 0}</strong> available indicators in the state's worst quartile</p>
        ${pendingNote}
        ${criticalNote}
        <h4>PLACES measures — petal color</h4><table>${axRows}</table>
        <h4>Bud — circles &amp; thresholds</h4><table>${budRows}</table>`);
      panel.classed("open", true);
    }
    function closePanel(){ panel.classed("open", false); flower.select(".bloom-hit").attr("stroke", "none"); }
    panel.select(".bloom-panel-close").on("click", closePanel);

    flower
      .on("pointerenter", function(e, c){
        if(mode !== "bloom") return;
        gFlow.selectAll(".bloom-hoverlbl").interrupt().attr("opacity", 0);
        d3.select(this).raise().select(".bloom-hoverlbl").transition().duration(150).attr("opacity", 1);
      })
      .on("pointerleave", function(){ d3.select(this).select(".bloom-hoverlbl").interrupt().transition().duration(120).attr("opacity", 0); })
      .on("click", function(e, c){ if(mode === "bloom") openPanel(c, this); });
    cty.on("pointerenter", function(e, f){
        if(mode !== "heat") return;
        const c = byId.get(f.properties.county_fips);
        d3.select(this).attr("stroke", "#2c5730").attr("stroke-width", 1.4).raise();
        if(c) showTT(`<b>${c.name}</b><br>${lensPhrase(lens).replace("Pinker counties", "this county")}: <b>${fmt1(lensVal(c, lens) * 100)}/100</b>`, e);
      })
      .on("pointermove", moveTT)
      .on("pointerleave", function(){ d3.select(this).attr("stroke", null).attr("stroke-width", null); hideTT(); })
      .on("click", (e, f) => { if(mode === "heat"){ const c = byId.get(f.properties.county_fips); if(c) openPanel(c); } });

    /* selector flower (side legend, drives setLens) — lives in sideRoot, a
       separate DOM subtree (the JSX sidebar) from host (the viz column). */
    const selHost = d3.select(sideRoot.querySelector(".bloom-selector-mount"));
    let updateSelectorSel = () => {};
    const sideCleanup = [];  // sideRoot listeners/DOM to undo on destroy()
    if(selHost.node()){
      const SK = 2.15, SL = 30, SCX = 131, SCY = 122;
      const sel = selHost.append("svg").attr("width", 262).attr("height", 238).attr("viewBox", "0 0 262 238");
      const selDefs = sel.append("defs");
      AXES.forEach((m, i) => pinkStops(selDefs, "bloom-selg" + i, 0.55, SL, AX_STROKE[m.key]));
      const selRoot = sel.append("g").attr("transform", `translate(${SCX},${SCY})`);
      const petal = selRoot.selectAll("g.p").data(AXES).join("g").attr("class", "p");
      const petalLabels = {};
      petal.each(function(m, i){
        const g = d3.select(this);
        const frame = g.append("g").attr("transform", `scale(${SK}) rotate(${ANGLE[m.key]})`);
        frame.append("path").attr("class", "body").attr("d", bractPath(SL)).attr("fill", `url(#bloom-selg${i})`).attr("stroke", AX_OUTLINE[m.key]).attr("stroke-width", 1.1).attr("stroke-opacity", 0.95);
        frame.append("path").attr("d", bractVeins(SL)).attr("fill", "none").attr("stroke", "#c98ba1").attr("stroke-width", 0.5).attr("stroke-opacity", 0.32);
        const W = bractW(SL);
        frame.append("circle").attr("class", "bloom-hitzone").attr("cy", CORE + SL * 0.30).attr("r", SL * 0.30).attr("fill", "transparent").datum({ lens: "ax" + m.key, petal: g });
        frame.append("circle").attr("class", "bloom-hitzone").attr("cy", CORE + SL * 0.78).attr("r", SL * 0.36).attr("fill", "transparent").datum({ lens: m.measure, petal: g });
        const R = SK * (CORE + SL);
        const pos = { N: [0, -R - 10], E: [R + 8, 4], S: [0, R + 16], W: [-R - 8, 4] }[m.key];
        const anchor = { N: "middle", E: "start", S: "middle", W: "end" }[m.key];
        const t = g.append("text").attr("x", pos[0]).attr("y", pos[1]).attr("text-anchor", anchor).text(m.measureLabel);
        petalLabels[m.measure] = t; t.datum({ lens: m.measure, petal: g }).classed("bloom-hitzone", true);
      });
      const budSel = selRoot.append("g");
      const budRing = budSel.append("circle").attr("class", "bloom-budring bloom-hitzone").attr("r", (RING_R + BUD_R + 0.9) * SK).datum({ lens: "breadth" });
      budPts.forEach((p, pi) => {
        budSel.append("circle").attr("class", "bloom-budc bloom-hitzone" + ([0, 2, 5].includes(pi) ? " on" : "")).attr("cx", p[0] * SK).attr("cy", p[1] * SK).attr("r", BUD_R * SK + 1.2).datum({ lens: "breadth" });
      });
      const hoverNote = sideRoot.querySelector(".bloom-hovernote");
      const rampRow = sideRoot.querySelector(".bloom-ramp-row");
      const keyRows = {};
      sideRoot.querySelectorAll("[data-lens]").forEach(el => { keyRows[el.getAttribute("data-lens")] = el; });
      updateSelectorSel = () => {
        petal.classed("selPink", m => lens === m.measure).classed("selLen", m => lens === "ax" + m.key);
        Object.entries(petalLabels).forEach(([k, t]) => t.classed("sel", lens === k));
        budRing.classed("sel", lens === "breadth");
        Object.entries(keyRows).forEach(([k, el]) => el.classList.toggle("hl-on", lens === k));
        if(rampRow) rampRow.style.visibility = lens ? "visible" : "hidden";
        backBtn.classed("on", !!lens);
      };
      const HOVER_NAME = {
        bphigh: "Hypertension (petal color)", diabetes: "Diabetes (petal color)",
        depression: "Depression (petal color)", smoking: "Smoking (petal color)",
        axN: "Economic deprivation (petal length)", axE: "Uninsured (petal length)",
        axS: "Demographic demand (petal length)", axW: "Access barriers (petal length)",
        breadth: "Breadth of need (bud)",
      };
      sel.selectAll(".bloom-hitzone")
        .on("pointerenter", function(e, d){
          if(!d || !d.lens) return;
          if(hoverNote) hoverNote.textContent = HOVER_NAME[d.lens] || "";
          if(d.petal) d.petal.classed("hovHl", true);
        })
        .on("pointerleave", function(e, d){ if(hoverNote) hoverNote.innerHTML = "&nbsp;"; if(d && d.petal) d.petal.classed("hovHl", false); })
        .on("click", (e, d) => { if(d && d.lens) setLens(d.lens); });
      sideRoot.querySelectorAll("[data-lens]").forEach(el => {
        const onLensClick = () => setLens(el.getAttribute("data-lens"));
        el.addEventListener("click", onLensClick);
        sideCleanup.push(() => el.removeEventListener("click", onLensClick));
      });
    }

    /* entry animation */
    let destroyed = false;
    (async function entry(){
      animating = true;
      try{
        await new Promise(r => setTimeout(r, 250));
        if(destroyed) return;
        await Promise.race([
          flower.transition().duration(1000).ease(d3.easeCubicInOut).attr("transform", c => `translate(${c.cx},${c.cy})`).end().catch(() => {}),
          new Promise(r => setTimeout(r, 1500)),
        ]);
        if(destroyed) return;
        flower.each(function(){ bloomG(d3.select(this), 1); });
      } finally { animating = false; }
    })();
    updateSelectorSel();

    return {
      pending, thr, axThr,
      // Clears the sideRoot mounts too: a re-mount would otherwise stack a
      // second legend flower and duplicate [data-lens] click listeners.
      destroy(){
        destroyed = true;
        root.html("");
        selHost.html("");
        sideCleanup.forEach(fn => fn());
      },
    };
  }

  A.bloom = { mountBloom };
})(window.Atlas);
