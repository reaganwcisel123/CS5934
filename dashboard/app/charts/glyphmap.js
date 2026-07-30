// Clinic Needs Forest glyphs (PLACES burden × UDS response), ported from
// clinic-needs-forest.html. DUMMY DATA — replace buildDummyData() when real data exists.
(function(A){
  const { showTT, moveTT, hideTT } = A.tooltip;
  const fmt0 = d3.format(".0f"), fmt1 = d3.format(".1f"), fmtC = d3.format(",");
  const sgn = d => d > 0 ? "+" : "";

  // Four glyph axes, 90° apart: arm length = burden; wedge narrows as response rises.
  const AXES = [
    { key:"htn", label:"Hypertension", pos:"top",    quad:[-Math.PI/4, Math.PI/4],    places:"BPHIGH",    placesLabel:"High blood pressure",
      udsShort:"HTN controlled", color:"#e34948" },
    { key:"dm",  label:"Diabetes",     pos:"right",  quad:[Math.PI/4, 3*Math.PI/4],   places:"DIABETES",  placesLabel:"Diabetes prevalence",
      udsShort:"Diabetes controlled", color:"#2a78d6" },
    { key:"dep", label:"Depression",   pos:"bottom", quad:[3*Math.PI/4, 5*Math.PI/4], places:"DEPRESSION",placesLabel:"Depression prevalence",
      udsShort:"Depression screened", color:"#4a3aa7" },
    { key:"smk", label:"Smoking",      pos:"left",   quad:[5*Math.PI/4, 7*Math.PI/4], places:"CSMOKING",  placesLabel:"Current smoking",
      udsShort:"Tobacco cessation", color:"#eda100" },
  ];

  /* Seeded PRNG so the dummy forest is identical on every reload */
  function mulberry32(a){ return function(){ a|=0; a=a+0x6D2B79F5|0; let t=Math.imul(a^a>>>15,1|a); t=t+Math.imul(t^t>>>7,61|t)^t; return ((t^t>>>14)>>>0)/4294967296; }; }

  const GRANTEE_NAMES = [
    "Blue Ridge Community Health","Tidewater Care Alliance","Shenandoah Valley Health",
    "Central Virginia Health Services","Southwest Mountain Clinics","Piedmont Family Care",
    "Rappahannock Community Health","Eastern Shore Rural Health","Highlands Health Network",
    "James River Health Partners","Roanoke Valley Clinics","Northern Neck Health Coop",
    "Appalachian Care Collective","Chesapeake Bay Health","New River Health Alliance",
    "Old Dominion Family Health","Cumberland Gap Clinics","Peninsula Community Care",
    "Dan River Health Center","Massanutten Health Group",
  ];
  // Anchor each grantee in the region its name implies, so placement reads right.
  const GRANTEE_REGION = {
    "Blue Ridge Community Health":"Valley", "Tidewater Care Alliance":"Tidewater",
    "Shenandoah Valley Health":"Valley", "Central Virginia Health Services":"Central",
    "Southwest Mountain Clinics":"Southwest", "Piedmont Family Care":"Central",
    "Rappahannock Community Health":"Northern", "Eastern Shore Rural Health":"Tidewater",
    "Highlands Health Network":"Southwest", "James River Health Partners":"Central",
    "Roanoke Valley Clinics":"Valley", "Northern Neck Health Coop":"Northern",
    "Appalachian Care Collective":"Southwest", "Chesapeake Bay Health":"Tidewater",
    "New River Health Alliance":"Southwest", "Old Dominion Family Health":"Central",
    "Cumberland Gap Clinics":"Southwest", "Peninsula Community Care":"Tidewater",
    "Dan River Health Center":"Central", "Massanutten Health Group":"Valley",
  };

  function buildDummyData(geo){
    const rng = mulberry32(20260713);
    const rint = (lo,hi) => lo + Math.floor(rng() * (hi - lo + 1));
    const rf = (lo,hi) => lo + rng() * (hi - lo);

    // Per-county PLACES prevalence, with mild regional bias so patterns cluster.
    const REG_BIAS = {
      Northern:{BPHIGH:-3,DIABETES:-1,DEPRESSION:0,CSMOKING:-3},
      Central:{BPHIGH:0,DIABETES:0,DEPRESSION:1,CSMOKING:0},
      Valley:{BPHIGH:1,DIABETES:0,DEPRESSION:0,CSMOKING:1},
      Southwest:{BPHIGH:4,DIABETES:3,DEPRESSION:3,CSMOKING:6},
      Tidewater:{BPHIGH:2,DIABETES:2,DEPRESSION:1,CSMOKING:2},
    };
    const counties = {};
    geo.features.forEach(f => {
      const fips = f.properties.county_fips, reg = f.properties.region;
      const b = REG_BIAS[reg] || REG_BIAS.Central;
      counties[fips] = {
        fips, name: f.properties.name, region: reg,
        centroid: d3.geoCentroid(f), bounds: d3.geoBounds(f),
        BPHIGH:   Math.max(20, Math.min(48, 32 + b.BPHIGH + rf(-5, 5))),
        DIABETES: Math.max(6,  Math.min(20, 11 + b.DIABETES + rf(-3, 3))),
        DEPRESSION: Math.max(12, Math.min(32, 20 + b.DEPRESSION + rf(-4, 4))),
        CSMOKING: Math.max(7,  Math.min(34, 16 + b.CSMOKING + rf(-4, 4))),
      };
    });
    const fipsList = Object.keys(counties);
    const byRegion = {};
    fipsList.forEach(f => { const r = counties[f].region; (byRegion[r] = byRegion[r] || []).push(f); });

    const grantees = GRANTEE_NAMES.map((name, gi) => {
      const pool = byRegion[GRANTEE_REGION[name]] || fipsList;
      const home = pool[Math.floor(rng() * pool.length)];
      const hc = counties[home];
      const near = fipsList
        .map(fp => ({ fp, d: d3.geoDistance(hc.centroid, counties[fp].centroid) }))
        .sort((a,b) => a.d - b.d).slice(0, rint(6, 11)).map(o => o.fp);
      const nClin = rint(3, 6);
      const clinics = [];
      for(let i = 0; i < nClin; i++){
        const cf = near[Math.floor(rng() * near.length)];
        const co = counties[cf];
        const [[w, s], [e, n]] = co.bounds;
        const lng = co.centroid[0] + (rng() - 0.5) * (e - w) * 0.4;
        const lat = co.centroid[1] + (rng() - 0.5) * (n - s) * 0.4;
        clinics.push({ id: `g${gi}c${i}`, name: `${co.name} ${["Health Center","Clinic","Family Care","Community Site"][i % 4]}`,
          county_fips: cf, countyName: co.name, region: co.region, lat, lng, patients: rint(900, 7200) });
      }
      const cCounties = Array.from(new Set(clinics.map(c => c.county_fips)));
      const cRegions = Array.from(new Set(clinics.map(c => c.region)));
      const totPat = d3.sum(clinics, c => c.patients);

      const places = {};
      ["BPHIGH","DIABETES","DEPRESSION","CSMOKING"].forEach(k => {
        places[k] = d3.sum(clinics, c => counties[c.county_fips][k] * c.patients) / totPat;
      });

      const uds = {
        htn_control: rf(48, 90),
        dm_poor:     rf(10, 42),          // higher = worse -> inverted below
        depr_screen: rf(40, 92),
        tob_cessation: rf(38, 88),
        patient_count: totPat,
      };
      rng();  // keep the seeded layout identical across edits
      return { id: `G${gi}`, name, clinics, counties: cCounties, regions: cRegions, places, uds,
               centroid: [d3.mean(clinics, c => c.lng), d3.mean(clinics, c => c.lat)] };
    });

    const placesByAxis = ax => grantees.map(g => g.places[ax.places]);
    const udsPctOf = (g, axKey) => {
      if(axKey === "htn") return g.uds.htn_control;
      if(axKey === "dm")  return 100 - g.uds.dm_poor;   // poor control -> control rate
      if(axKey === "dep") return g.uds.depr_screen;
      return g.uds.tob_cessation;
    };
    const burdenScale = {};
    AXES.forEach(ax => { const v = placesByAxis(ax); burdenScale[ax.key] = d3.scaleLinear().domain([d3.min(v), d3.max(v)]).range([0, 1]).clamp(true); });

    grantees.forEach(g => {
      g.placesByAxis = {}; g.respPct = {}; g.burdenNorm = {};
      AXES.forEach(ax => {
        g.placesByAxis[ax.key] = g.places[ax.places];
        g.respPct[ax.key] = udsPctOf(g, ax.key);
        g.burdenNorm[ax.key] = burdenScale[ax.key](g.places[ax.places]);
      });
      g.meanBurden = d3.mean(AXES, ax => g.burdenNorm[ax.key]);
      g.meanResp   = d3.mean(AXES, ax => g.respPct[ax.key]) / 100;
      g.needScore  = g.meanBurden * (1 - g.meanResp);   // need = high burden AND low response
    });
    return { counties, grantees, geo };
  }

  /* Glyph renderer (shared: small on map, large in the side panel). */
  function outerFor(R, bN){ return R * (0.16 + 0.84 * bN); }        // burden -> outer radius
  const lighten = (c, t) => d3.interpolateRgb(c, "#ffffff")(t);
  const MIN_HALF = 0.05;                                            // sliver still visible at 100% response
  function drawGlyph(g, gr, opts){
    const { R, interactive = false, showRing = false } = opts;
    g.selectAll("*").remove();
    const sw = Math.max(0.8, R * 0.03);
    if(showRing) g.append("circle").attr("r", R).attr("fill", "none").attr("stroke", "var(--slate-300)")
      .attr("stroke-dasharray", "2 3").attr("opacity", 0.5);

    AXES.forEach(ax => {
      const outerR = outerFor(R, gr.burdenNorm[ax.key]);            // burden
      const respF  = Math.max(0, Math.min(1, gr.respPct[ax.key] / 100));
      const center = (ax.quad[0] + ax.quad[1]) / 2;
      const half   = Math.max(MIN_HALF, (Math.PI / 4) * (1 - respF)); // response narrows the wedge
      g.append("path").attr("d", d3.arc().innerRadius(0).outerRadius(outerR)
          .startAngle(center - half).endAngle(center + half).cornerRadius(R * 0.13)())
        .attr("fill", lighten(ax.color, 0.62)).attr("stroke", ax.color).attr("stroke-width", sw).attr("stroke-linejoin", "round");
      if(interactive){
        g.append("path").attr("d", d3.arc().innerRadius(0).outerRadius(R).startAngle(ax.quad[0]).endAngle(ax.quad[1])())
          .attr("fill", "transparent").style("cursor", "help")
          .on("mouseover", e => showTT(
            `<b>${ax.label}</b>` +
            `<br>PLACES burden — ${ax.placesLabel}: <b>${fmt1(gr.placesByAxis[ax.key])}%</b>` +
            `<br>UDS response — ${ax.udsShort}: <b>${fmt1(gr.respPct[ax.key])}%</b>` +
            `<br><span class="src">outward = burden · width = unmet need (narrow = controlled)</span>`, e))
          .on("mousemove", moveTT).on("mouseout", hideTT);
      }
    });
  }

  /* Dual-sided (top/bottom) bar chart for the grantee drill-in. */
  function drawDualBar(el, { rows, colorTop, colorBottom, topLabel, botLabel, note }){
    const host = d3.select(el).html("");
    const n = rows.length, col = Math.max(40, Math.min(74, 620 / n)), bw = Math.min(30, col * 0.54);
    const m = { top: 30, bottom: 110, left: 52, right: 14 }, half = 118, cy = m.top + half;
    const W = m.left + n * col + m.right, H = cy + half + m.bottom;
    const v = d3.scaleLinear().domain([0, 100]).range([0, half]);
    const svg = host.append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("width", "100%")
      .attr("role", "img").attr("aria-label", "Dual-sided bar chart: UDS response above, PLACES burden below.");

    [0, 50, 100].forEach(t => {
      [cy - v(t), cy + v(t)].forEach((yy, idx) => {
        if(t === 0 && idx === 1) return;
        svg.append("line").attr("x1", m.left).attr("x2", W - m.right).attr("y1", yy).attr("y2", yy)
          .attr("stroke", "var(--slate-200)").attr("stroke-width", t === 0 ? 0 : 1).attr("opacity", .9);
        svg.append("text").attr("x", m.left - 8).attr("y", yy + 3).attr("text-anchor", "end")
          .attr("font-size", 9.5).attr("font-family", "var(--font-mono)").attr("fill", "var(--slate-400)").text(t + "%");
      });
    });
    svg.append("line").attr("x1", m.left - 2).attr("x2", W - m.right).attr("y1", cy).attr("y2", cy).attr("stroke", "var(--slate-400)").attr("stroke-width", 1);
    svg.append("text").attr("x", m.left - 46).attr("y", cy - half / 2).attr("transform", `rotate(-90 ${m.left - 46} ${cy - half / 2})`)
      .attr("text-anchor", "middle").attr("font-size", 10).attr("fill", "var(--slate-500)").text("UDS response");
    svg.append("text").attr("x", m.left - 46).attr("y", cy + half / 2).attr("transform", `rotate(-90 ${m.left - 46} ${cy + half / 2})`)
      .attr("text-anchor", "middle").attr("font-size", 10).attr("fill", "var(--slate-500)").text("PLACES burden");

    rows.forEach((row, i) => {
      const x = m.left + i * col + col / 2, ct = colorTop(row, i), cb = colorBottom(row, i);
      const grp = svg.append("g").style("cursor", "default")
        .on("mouseover", e => showTT(
          `<b>${row.label}</b>` +
          `<br>UDS ${row.udsShort || "response"}: <b>${fmt1(row.top)}%</b>` +
          `<br>PLACES ${row.placesShort || "burden"}: <b>${fmt1(row.bottom)}%</b>` +
          `<br><b>Δ UDS−PLACES: ${sgn(row.gap)}${fmt1(row.gap)} pts</b>`, e))
        .on("mousemove", moveTT).on("mouseout", hideTT);
      grp.append("rect").attr("x", x - bw / 2).attr("y", cy - 1 - v(row.top)).attr("width", bw).attr("height", v(row.top)).attr("rx", 3).attr("fill", ct).attr("fill-opacity", 0.95);
      grp.append("rect").attr("x", x - bw / 2).attr("y", cy + 1).attr("width", bw).attr("height", v(row.bottom)).attr("rx", 3).attr("fill", cb).attr("fill-opacity", 0.62);
      svg.append("text").attr("x", x).attr("y", cy - 3 - v(row.top) - 4).attr("text-anchor", "middle")
        .attr("font-size", 10).attr("font-weight", 700).attr("font-family", "var(--font-mono)").attr("fill", "var(--slate-600)")
        .text(sgn(row.gap) + fmt0(row.gap));
      const nm = row.label.length > 18 ? row.label.slice(0, 17) + "…" : row.label;
      svg.append("text").attr("x", x).attr("y", cy + half + 14).attr("transform", `rotate(38 ${x} ${cy + half + 14})`)
        .attr("text-anchor", "start").attr("font-size", 10.5).attr("fill", "var(--slate-600)").text(nm);
    });

    const lg = svg.append("g").attr("transform", `translate(${m.left},14)`);
    lg.append("rect").attr("width", 11).attr("height", 11).attr("rx", 2).attr("fill", rows[0] !== undefined ? colorTop(rows[0], 0) : "#2a78d6").attr("fill-opacity", .95);
    lg.append("text").attr("x", 16).attr("y", 10).attr("font-size", 11).attr("fill", "var(--slate-600)").text(topLabel + " (top)");
    const lg2 = svg.append("g").attr("transform", `translate(${m.left + 150},14)`);
    lg2.append("rect").attr("width", 11).attr("height", 11).attr("rx", 2).attr("fill", rows[0] !== undefined ? colorBottom(rows[0], 0) : "#e34948").attr("fill-opacity", .62);
    lg2.append("text").attr("x", 16).attr("y", 10).attr("font-size", 11).attr("fill", "var(--slate-600)").text(botLabel + " (bottom)");
    if(note) svg.append("text").attr("x", W - m.right).attr("y", 14).attr("text-anchor", "end").attr("font-size", 10.5).attr("fill", "var(--slate-400)").text(note);
  }

  /* The map: faint counties + glyph forest + clinic dots + drill-in zoom. */
  function buildForestMap(host, data, onSelect){
    const W = 880, H = 430;
    const svg = d3.select(host).html("").append("svg").attr("viewBox", `0 0 ${W} ${H}`)
      .attr("role", "img").attr("aria-label", "Virginia map with a forest of clinic-need glyphs.");
    const projection = d3.geoConicConformal().parallels([37.5, 39.5]).rotate([79, 0]).fitExtent([[16, 16], [W - 16, H - 16]], data.geo);

    const gZoom = svg.append("g");                 // zoomed layer: counties + clinics
    gZoom.append("g").selectAll("path").data(data.geo.features).join("path")
      .attr("d", d3.geoPath(projection)).attr("fill", "none").attr("stroke", "var(--slate-300)").attr("stroke-width", 0.7)
      .attr("vector-effect", "non-scaling-stroke");
    const clinicG = gZoom.append("g");
    const gGlyphs = svg.append("g");               // screen-space forest (not zoomed)

    const FR = 24;
    const nodes = data.grantees.map(g => {
      const p = projection(g.centroid);
      const outerMax = outerFor(FR, d3.max(AXES, a => g.burdenNorm[a.key]));
      return { g, R: FR, collide: outerMax + 3, px: p[0], py: p[1], x: p[0], y: p[1] };
    });
    const sim = d3.forceSimulation(nodes)
      .force("x", d3.forceX(d => d.px).strength(0.6)).force("y", d3.forceY(d => d.py).strength(0.6))
      .force("collide", d3.forceCollide(d => d.collide).strength(0.9)).stop();
    for(let i = 0; i < 160; i++) sim.tick();

    const glyphSel = gGlyphs.selectAll("g.glyph").data(nodes, d => d.g.id).join("g").attr("class", "glyph")
      .attr("transform", d => `translate(${d.x},${d.y})`).style("cursor", "pointer")
      .on("mouseover", (e, d) => showTT(`<b>${d.g.name}</b><br>${d.g.clinics.length} clinics · ${d.g.regions.join(", ")}` +
          `<br>burden ${fmt0(d.g.meanBurden * 100)} · response ${fmt0(d.g.meanResp * 100)}%` +
          `<br><span class="src">click to open</span>`, e))
      .on("mousemove", moveTT).on("mouseout", hideTT).on("click", (e, d) => onSelect(d.g.id));
    glyphSel.each(function(d){
      if(Math.hypot(d.x - d.px, d.y - d.py) > 3){
        d3.select(this.parentNode).insert("line", ":first-child")
          .attr("x1", d.x).attr("y1", d.y).attr("x2", d.px).attr("y2", d.py)
          .attr("stroke", "var(--slate-300)").attr("stroke-width", 0.6);
      }
      drawGlyph(d3.select(this).append("g"), d.g, { R: d.R });
      d3.select(this).append("circle").attr("r", d.collide).attr("fill", "transparent"); // hit target
    });

    const zoom = d3.zoom().scaleExtent([1, 12]).on("zoom", ev => {
      gZoom.attr("transform", ev.transform);
      clinicG.selectAll("circle").attr("r", 5 / ev.transform.k).attr("stroke-width", 1.5 / ev.transform.k);
    });
    svg.call(zoom).on("wheel.zoom", null).on("mousedown.zoom", null).on("dblclick.zoom", null).on("touchstart.zoom", null);

    function update(mode, selId){
      if(mode === "grantee" && selId){
        const g = data.grantees.find(x => x.id === selId);
        if(!g) return;
        gGlyphs.transition().duration(350).style("opacity", 0).style("pointer-events", "none");
        const P = g.clinics.map(c => projection([c.lng, c.lat]));
        const x0 = d3.min(P, p => p[0]), x1 = d3.max(P, p => p[0]), y0 = d3.min(P, p => p[1]), y1 = d3.max(P, p => p[1]);
        const bw = Math.max(x1 - x0, 30), bh = Math.max(y1 - y0, 30);
        const k = Math.min(9, 0.72 * Math.min(W / bw, H / bh));
        const t = d3.zoomIdentity.translate(W / 2 - k * (x0 + x1) / 2, H / 2 - k * (y0 + y1) / 2).scale(k);
        svg.transition().duration(750).call(zoom.transform, t);
        const dots = clinicG.selectAll("circle").data(g.clinics, c => c.id);
        dots.join("circle").attr("cx", c => projection([c.lng, c.lat])[0]).attr("cy", c => projection([c.lng, c.lat])[1])
          .attr("r", 5 / k).attr("fill", "var(--brand)").attr("stroke", "#fff").attr("stroke-width", 1.5 / k).style("cursor", "pointer")
          .on("mouseover", (e, c) => showTT(`<b>${c.name}</b><br>${c.countyName} County · ${c.region}<br>${fmtC(c.patients)} patients`, e))
          .on("mousemove", moveTT).on("mouseout", hideTT);
      } else {
        gGlyphs.transition().duration(350).style("opacity", 1).style("pointer-events", "auto");
        clinicG.selectAll("circle").remove();
        svg.transition().duration(650).call(zoom.transform, d3.zoomIdentity);
      }
    }
    return { update };
  }

  A.forest = { AXES, buildDummyData, drawGlyph, drawDualBar, buildForestMap, outerFor, lighten };
})(window.Atlas);
