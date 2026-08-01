// Shared number/format helpers (extracted from clinic-needs-atlas-signal.html).
(function(A){
  const fmt0 = d3.format(".0f"), fmt1 = d3.format(".1f"), fmtC = d3.format(",");
  const sgn = d => d > 0 ? "+" : "";
  const judge = w => Math.abs(w) < 1 ? "on par" : (w > 0 ? "worse" : "better");
  const glyph = d => Math.abs(d) < 0.5 ? "≈" : (d > 0 ? "▲" : "▼");
  A.format = { fmt0, fmt1, fmtC, sgn, judge, glyph };
})(window.Atlas);
