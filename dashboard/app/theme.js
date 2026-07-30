// Chart palette from tokens/dataviz.css, read once via getComputedStyle —
// D3's interpolated scales need real hex. Literals here are fallbacks only.
(function(A){
  const css = getComputedStyle(document.documentElement);
  const tok = (name, fallback) => (css.getPropertyValue(name) || "").trim() || fallback;

  const REGION_COLOR = {
    Northern:  tok("--viz-region-northern",  "#0284c7"),
    Central:   tok("--viz-region-central",   "#d97706"),
    Valley:    tok("--viz-region-valley",    "#059669"),
    Southwest: tok("--viz-region-southwest", "#c026d3"),
    Tidewater: tok("--viz-region-tidewater", "#4f46e5"),
  };

  const DIV_NEG = tok("--viz-div-neg", "#0284c7");   // better than baseline
  const DIV_MID = tok("--viz-div-mid", "#e2e8f0");
  const DIV_POS = tok("--viz-div-pos", "#dc2626");   // worse than baseline

  // Sequential need ramp for choropleths (low -> high need).
  const SEQ = [
    tok("--viz-seq-0", "#fdeae5"), tok("--viz-seq-1", "#f6bfb2"),
    tok("--viz-seq-2", "#ea9184"), tok("--viz-seq-3", "#d95f4f"),
    tok("--viz-seq-4", "#b93a2b"), tok("--viz-seq-5", "#8f2317"),
  ];
  const seqNeed = d3.scaleLinear()
    .domain(SEQ.map((_, i) => i / (SEQ.length - 1)))
    .range(SEQ).interpolate(d3.interpolateLab).clamp(true);

  const makeDiv = W => d3.scaleLinear().domain([-W, 0, W])
    .range([DIV_NEG, DIV_MID, DIV_POS]).interpolate(d3.interpolateLab).clamp(true);
  const onFill  = w => Math.abs(w) > 11 ? "#fff" : "#0f172a";       // text on a colored cell
  const divText = w => Math.abs(w) < 1 ? "#94a3b8" : (w > 0 ? DIV_POS : DIV_NEG);

  A.theme = { REGION_COLOR, DIV_NEG, DIV_MID, DIV_POS, seqNeed, makeDiv, onFill, divText };
})(window.Atlas);
