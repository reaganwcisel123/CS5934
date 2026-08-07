// Quality-gap dumbbell: UDS clinical measures vs. baseline.
(function(A){
  const { MEASURES } = A.domain;
  const { fmt0, fmt1, sgn, judge, glyph } = A.format;
  const { DIV_NEG, DIV_POS } = A.theme;
  const { showTT, moveTT, hideTT } = A.tooltip;

  function drawGap(el, ctx){
    const { byId, selectedId, baselineFor } = ctx;
    const host = d3.select(el).html("");
    const c = byId(selectedId), b = c && baselineFor(c);
    if(!c || !b){ host.append("div").attr("class", "empty").text("Select a county to compare."); return; }
    const W = 980, rowH = 46, m = { top:22, right:48, bottom:36, left:250 }, H = m.top + rowH * MEASURES.length + m.bottom;
    const svg = host.append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("width", "100%").attr("role", "img").attr("aria-label", `Quality gap from ${b.label}.`);
    const x = d3.scaleLinear().domain([0, 100]).range([m.left, W - m.right]);
    svg.append("g").attr("class", "axis").attr("transform", `translate(0,${H - m.bottom})`).call(d3.axisBottom(x).ticks(6).tickFormat(d => d + "%"));
    svg.append("text").attr("x", (m.left + W - m.right) / 2).attr("y", H - 4).attr("text-anchor", "middle").attr("font-size", 11).attr("fill", "var(--slate-500)").text("% of eligible patients");
    MEASURES.forEach((mz, i) => {
      const yc = m.top + i * rowH + rowH / 2, cv = c.measures[mz.key], bv = b.measures[mz.key];
      if(cv == null || bv == null) return;
      const w = mz.better === "high" ? bv - cv : cv - bv, col = Math.abs(w) < 1 ? "var(--slate-400)" : (w > 0 ? DIV_POS : DIV_NEG);
      svg.append("text").attr("x", m.left - 14).attr("y", yc - 2).attr("text-anchor", "end").attr("font-size", 12.5).attr("fill", "var(--slate-800)").text(mz.label);
      svg.append("text").attr("x", m.left - 14).attr("y", yc + 13).attr("text-anchor", "end").attr("font-size", 9.5).attr("fill", "var(--slate-400)").text(`${mz.source} · ${mz.better === "high" ? "higher better" : "lower better"}`);
      svg.append("line").attr("x1", x(bv)).attr("x2", x(cv)).attr("y1", yc).attr("y2", yc).attr("stroke", col).attr("stroke-width", 3).attr("opacity", .5);
      svg.append("circle").attr("cx", x(bv)).attr("cy", yc).attr("r", 6).attr("fill", "#fff").attr("stroke", "var(--violet-500)").attr("stroke-width", 2).on("mouseover", e => showTT(`<b>${b.label} baseline</b><br>${mz.label}: ${fmt1(bv)}%`, e)).on("mousemove", moveTT).on("mouseout", hideTT);
      svg.append("circle").attr("cx", x(cv)).attr("cy", yc).attr("r", 6.5).attr("fill", col).on("mouseover", e => showTT(`<b>${c.name}</b><br>${mz.label}: ${fmt1(cv)}%<br>${judge(w)} vs ${b.label} (${fmt1(bv)}%)`, e)).on("mousemove", moveTT).on("mouseout", hideTT);
      svg.append("text").attr("x", x(cv) + (cv >= bv ? 13 : -13)).attr("y", yc + 4).attr("text-anchor", cv >= bv ? "start" : "end").attr("font-size", 11).attr("font-weight", 700).attr("font-family", "var(--font-mono)").attr("fill", col).text(glyph(cv - bv) + " " + sgn(cv - bv) + fmt0(cv - bv) + "pt");
    });
    const lg = svg.append("g").attr("transform", `translate(${m.left},${m.top - 6})`);
    lg.append("circle").attr("r", 5).attr("fill", "#fff").attr("stroke", "var(--violet-500)").attr("stroke-width", 2);
    lg.append("text").attr("x", 10).attr("y", 4).attr("font-size", 10).attr("fill", "var(--slate-500)").text("baseline");
    lg.append("circle").attr("cx", 78).attr("r", 5).attr("fill", DIV_POS);
    lg.append("text").attr("x", 88).attr("y", 4).attr("font-size", 10).attr("fill", "var(--slate-500)").text("this county");
  }

  A.charts = A.charts || {};
  A.charts.drawGap = drawGap;
})(window.Atlas);
