// Deviation heatmap: every county vs. baseline across the five SDoH domains.
(function(A){
  const { DOMAINS } = A.domain;
  const { fmt0, sgn, judge, glyph } = A.format;
  const { makeDiv, onFill, divText } = A.theme;
  const { showTT, moveTT, hideTT } = A.tooltip;

  function drawHeatmap(el, ctx){
    const { records, selectedId, baselineFor, onSelect, baselineMode } = ctx;
    const host = d3.select(el).html("");
    const dev = c => { const b = baselineFor(c); return { c, b, d: Object.fromEntries(DOMAINS.map(D => [D.key, c.dom[D.key] - b.dom[D.key]])), total: d3.sum(DOMAINS, D => c.dom[D.key] - b.dom[D.key]) }; };
    const rows = records.map(dev).sort((a,b) => b.total - a.total), div = makeDiv(22);
    const m = { top:46, right:16, bottom:12, left:150 }, cellH = 22, cellW = 80;
    const W = m.left + cellW * DOMAINS.length + m.right, H = m.top + cellH * rows.length + m.bottom;
    // width:100% + viewBox, no fixed height, so the grid fills the box without empty bands.
    const svg = host.append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("width", "100%").attr("role", "img")
      .attr("aria-label", `Deviation heatmap: ${rows.length} counties versus the ${baselineMode === "region" ? "region" : "all-Virginia"} baseline.`);
    DOMAINS.forEach((D, j) => {
      svg.append("text").attr("x", m.left + j * cellW + cellW / 2).attr("y", m.top - 16).attr("text-anchor", "middle").attr("font-size", 11).attr("font-weight", 600).attr("fill", "var(--slate-700)").text(D.short);
      svg.append("text").attr("x", m.left + j * cellW + cellW / 2).attr("y", m.top - 4).attr("text-anchor", "middle").attr("font-size", 9).attr("fill", "var(--slate-400)").text(D.source.split(" ")[0]);
    });
    rows.forEach((row, i) => {
      const c = row.c, selected = c.id === selectedId;
      const ranked = DOMAINS.map(D => ({ k: D.key, v: c.dom[D.key] })).sort((a,b) => b.v - a.v), rankMap = {};
      ranked.slice(0, 3).forEach((d, ri) => rankMap[d.k] = ri + 1);
      const g = svg.append("g").attr("transform", `translate(0,${m.top + i * cellH})`).attr("tabindex", 0).attr("class", "focusable").attr("role", "button").style("cursor", "pointer")
        .on("click", () => onSelect(c.id)).on("keydown", e => { if(e.key === "Enter" || e.key === " "){ e.preventDefault(); onSelect(c.id); } });
      if(selected) g.append("rect").attr("x", 2).attr("y", 0).attr("width", W - 4).attr("height", cellH).attr("fill", "none").attr("stroke", "var(--brand)").attr("stroke-width", 2).attr("rx", 4);
      g.append("text").attr("x", m.left - 10).attr("y", cellH / 2 + 4).attr("text-anchor", "end").attr("font-size", 11).attr("font-weight", selected ? 700 : 400).attr("fill", selected ? "var(--brand)" : "var(--slate-700)").text(c.name.length > 22 ? c.name.slice(0, 21) + "…" : c.name);
      DOMAINS.forEach((D, j) => {
        const dv = row.d[D.key], tcol = onFill(dv);
        const cell = g.append("g").on("mouseover", e => showTT(`<b>${c.name}</b><br>${D.short}: burden ${fmt0(c.dom[D.key])} vs ${row.b.label} ${fmt0(row.b.dom[D.key])}<br><b style="color:${divText(dv)}">${glyph(dv)} ${sgn(dv)}${fmt0(dv)} — ${judge(dv)}</b>` + (rankMap[D.key] ? `<br>#${rankMap[D.key]} need` : ""), e)).on("mousemove", moveTT).on("mouseout", hideTT);
        cell.append("rect").attr("x", m.left + j * cellW + 1).attr("y", 1).attr("width", cellW - 2).attr("height", cellH - 2).attr("rx", 3).attr("fill", div(dv));
        cell.append("text").attr("x", m.left + j * cellW + cellW / 2).attr("y", cellH / 2 + 4).attr("text-anchor", "middle").attr("font-size", 10.5).attr("font-weight", 600).attr("font-family", "var(--font-mono)").attr("fill", tcol).text(`${glyph(dv)} ${sgn(dv)}${fmt0(dv)}`);
        if(rankMap[D.key]) cell.append("text").attr("x", m.left + j * cellW + cellW - 7).attr("y", 10).attr("text-anchor", "end").attr("font-size", 10).attr("font-weight", 800).attr("fill", tcol).text("①②③"[rankMap[D.key] - 1]);
      });
    });
  }

  A.charts = A.charts || {};
  A.charts.drawHeatmap = drawHeatmap;
})(window.Atlas);
