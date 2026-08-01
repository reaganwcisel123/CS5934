// Need vs. population scatter: size = HPSA, color = region, click to select.
(function(A){
  const { fmt0, fmtC } = A.format;
  const { REGION_COLOR } = A.theme;
  const { showTT, moveTT, hideTT } = A.tooltip;

  function drawScatter(el, ctx){
    const { records, selectedId, baselineFor, onSelect, byId, baselineMode } = ctx;
    const host = d3.select(el).html("");
    const c = byId(selectedId), b = baselineFor(c);
    const set = baselineMode === "region" ? records.filter(x => x.region === c.region) : records;
    const W = 440, H = 300, m = { top:14, right:16, bottom:42, left:48 };
    const svg = host.append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("width", "100%").attr("role", "img").attr("aria-label", `Scatter of ${set.length} counties: population vs unmet-need index.`);
    // Floor the x-domain to a realistic county-population range (stub pop is 0 without a key).
    const maxPop = d3.max(records, c => c.patients) || 0;
    const x = d3.scaleLinear().domain([0, Math.max(maxPop, 100000) * 1.05]).range([m.left, W - m.right]);
    const y = d3.scaleLinear().domain([0, 100]).range([H - m.bottom, m.top]);
    const xMed = b.patients, yMed = b.needIndex;
    svg.append("rect").attr("x", m.left).attr("y", m.top).attr("width", Math.max(0, x(xMed) - m.left)).attr("height", Math.max(0, y(yMed) - m.top)).attr("fill", "var(--danger-500)").attr("opacity", .07);
    svg.append("text").attr("x", m.left + 8).attr("y", m.top + 14).attr("font-size", 10.5).attr("fill", "var(--danger-700)").attr("font-weight", 700).text("Priority: more need, fewer people served");
    svg.append("line").attr("x1", x(xMed)).attr("x2", x(xMed)).attr("y1", m.top).attr("y2", H - m.bottom).attr("stroke", "var(--slate-300)").attr("stroke-dasharray", "3 3");
    svg.append("line").attr("x1", m.left).attr("x2", W - m.right).attr("y1", y(yMed)).attr("y2", y(yMed)).attr("stroke", "var(--slate-300)").attr("stroke-dasharray", "3 3");
    svg.append("g").attr("class", "axis").attr("transform", `translate(0,${H - m.bottom})`).call(d3.axisBottom(x).ticks(5).tickFormat(d3.format("~s")));
    svg.append("g").attr("class", "axis").attr("transform", `translate(${m.left},0)`).call(d3.axisLeft(y).ticks(5));
    svg.append("text").attr("x", (m.left + W - m.right) / 2).attr("y", H - 6).attr("text-anchor", "middle").attr("font-size", 11).attr("fill", "var(--slate-500)").text("Population (Census)");
    svg.append("text").attr("transform", "rotate(-90)").attr("x", -(H / 2)).attr("y", 13).attr("text-anchor", "middle").attr("font-size", 11).attr("fill", "var(--slate-500)").text("Unmet-need index");
    const r = d3.scaleSqrt().domain([0, 26]).range([4, 12]);
    svg.append("line").attr("x1", x(c.patients)).attr("y1", y(c.needIndex)).attr("x2", x(xMed)).attr("y2", y(yMed)).attr("stroke", "var(--brand)").attr("stroke-width", 1).attr("stroke-dasharray", "4 3").attr("opacity", .7);
    svg.selectAll(".sc-dot").data(set).join("circle").attr("class", "focusable sc-dot").attr("tabindex", 0).attr("role", "button")
      .attr("cx", d => x(d.patients)).attr("cy", d => y(d.needIndex)).attr("r", d => r(d.hpsaScore)).attr("fill", d => REGION_COLOR[d.region]).attr("opacity", .85)
      .attr("stroke", d => d.id === selectedId ? "var(--brand)" : "rgba(15,23,42,.28)").attr("stroke-width", d => d.id === selectedId ? 3 : 1).style("cursor", "pointer")
      .on("mouseover", (e, d) => showTT(`<b>${d.name}</b> · ${d.region}<br>${d.patients ? fmtC(d.patients) : "—"} people · need ${fmt0(d.needIndex)}<br>HPSA ${d.hpsaScore}/26 <span class="src">· size = HPSA, color = region</span>`, e))
      .on("mousemove", moveTT).on("mouseout", hideTT).on("click", (e, d) => onSelect(d.id)).on("keydown", (e, d) => { if(e.key === "Enter" || e.key === " "){ e.preventDefault(); onSelect(d.id); } });
    svg.append("path").attr("d", d3.symbol(d3.symbolDiamond, 150)()).attr("transform", `translate(${x(xMed)},${y(yMed)})`).attr("fill", "#fff").attr("stroke", "var(--slate-900)").attr("stroke-width", 1.5)
      .on("mouseover", e => showTT(`<b>${b.label} average</b><br>${fmtC(Math.round(xMed))} people (median) · need ${fmt0(yMed)}`, e)).on("mousemove", moveTT).on("mouseout", hideTT);
    svg.append("text").attr("x", x(xMed) + 11).attr("y", y(yMed) - 9).attr("font-size", 10).attr("font-weight", 700).attr("fill", "var(--slate-700)").text(b.short + " avg");
  }

  A.charts = A.charts || {};
  A.charts.drawScatter = drawScatter;
})(window.Atlas);
