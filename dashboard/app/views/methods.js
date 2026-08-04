// Methods & data: the signal-flow explainer, source/provenance tables, and a
// summary of documents/forecast-model-card.md.
(function(A){
  const Icon = A.Icon;
  const { Panel, ProvPill, normalizeProvenance } = A.ui;

  /* US-32 diagram, ported from signal.html. The deployed model is a logistic
     regression, so the copy says "weighted combination", never "neural network". */
  const NN_IN_X = 165, NN_H1_X = 390, NN_H2_X = 550, NN_OUT_X = 675, NN_OUT_Y = 174;
  const NN_IN_Y = [62, 118, 174, 230, 286], NN_H1_Y = [90, 146, 202, 258], NN_H2_Y = [118, 174, 230];
  const NN_INPUTS = ["Economic hardship", "Food & housing", "Care access", "Provider shortage", "Need index"];
  // Cubic Bezier with horizontal tangents: reads as flow, not hairball.
  function nnEdge(x1, y1, x2, y2){ const dx = (x2 - x1) * 0.45; return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`; }
  // Pulses ride a hand-picked edge subset; staggered timing keeps only a few lit at once.
  const NN_PULSES = [
    { d: nnEdge(NN_IN_X, NN_IN_Y[0], NN_H1_X, NN_H1_Y[0]), dur: 5.2, delay: 0 },
    { d: nnEdge(NN_IN_X, NN_IN_Y[2], NN_H1_X, NN_H1_Y[1]), dur: 6.4, delay: 1.6 },
    { d: nnEdge(NN_IN_X, NN_IN_Y[4], NN_H1_X, NN_H1_Y[3]), dur: 4.6, delay: 3.1 },
    { d: nnEdge(NN_IN_X, NN_IN_Y[1], NN_H1_X, NN_H1_Y[2]), dur: 7.2, delay: 0.8 },
    { d: nnEdge(NN_H1_X, NN_H1_Y[0], NN_H2_X, NN_H2_Y[0]), dur: 5.8, delay: 2.4 },
    { d: nnEdge(NN_H1_X, NN_H1_Y[3], NN_H2_X, NN_H2_Y[2]), dur: 4.2, delay: 4.6 },
    { d: nnEdge(NN_H1_X, NN_H1_Y[1], NN_H2_X, NN_H2_Y[1]), dur: 6.8, delay: 1.2 },
    { d: nnEdge(NN_H2_X, NN_H2_Y[1], NN_OUT_X, NN_OUT_Y),  dur: 4.9, delay: 3.7 },
  ];
  function NeuralFlowViz(){
    const ref = React.useRef(null);
    // Pause pulses while the diagram is off-screen or the tab is hidden.
    React.useEffect(() => {
      const el = ref.current; if(!el) return;
      let offscreen = false;
      const set = () => el.classList.toggle("paused", offscreen || document.hidden);
      const io = new IntersectionObserver(es => { offscreen = !es[0].isIntersecting; set(); }, { threshold: 0.05 });
      io.observe(el);
      document.addEventListener("visibilitychange", set);
      return () => { io.disconnect(); document.removeEventListener("visibilitychange", set); };
    }, []);
    const edges = [
      ...NN_IN_Y.flatMap(y1 => NN_H1_Y.map(y2 => nnEdge(NN_IN_X, y1, NN_H1_X, y2))),
      ...NN_H1_Y.flatMap(y1 => NN_H2_Y.map(y2 => nnEdge(NN_H1_X, y1, NN_H2_X, y2))),
      ...NN_H2_Y.map(y1 => nnEdge(NN_H2_X, y1, NN_OUT_X, NN_OUT_Y)),
    ];
    return (
      <div className="nnviz" ref={ref}>
        <svg viewBox="0 0 800 340" role="img"
          aria-label="Diagram of the county model: five county factors (economic hardship, food and housing, care access, provider shortage, and the composite need index) flow through a weighted combination into one need signal for the county.">
          <text className="nn-cap" x={NN_IN_X} y={26} textAnchor="middle">County factors</text>
          <text className="nn-cap" x={(NN_H1_X + NN_H2_X) / 2} y={26} textAnchor="middle">Weighted combination</text>
          <text className="nn-cap" x={NN_OUT_X} y={26} textAnchor="middle">Prediction</text>
          <g>{edges.map((d, i) => <path key={i} className="nn-edge" d={d} />)}</g>
          <g aria-hidden="true">{NN_PULSES.map((p, i) => (
            <path key={i} className="pulse" d={p.d} pathLength={100}
              style={{ animationDuration: p.dur + "s", animationDelay: p.delay + "s" }} />
          ))}</g>
          {NN_IN_Y.map((y, i) => (
            <g key={i}>
              <circle className="nn-in" cx={NN_IN_X} cy={y} r={7} />
              <text className="nn-label" x={NN_IN_X - 16} y={y + 4} textAnchor="end">{NN_INPUTS[i]}</text>
            </g>
          ))}
          {NN_H1_Y.map((y, i) => <circle key={i} className="nn-hid" cx={NN_H1_X} cy={y} r={5} />)}
          {NN_H2_Y.map((y, i) => <circle key={i} className="nn-hid" cx={NN_H2_X} cy={y} r={5} />)}
          <circle className="nn-out" cx={NN_OUT_X} cy={NN_OUT_Y} r={9} />
          <text className="nn-out-label" x={NN_OUT_X} y={NN_OUT_Y + 28} textAnchor="middle">Need signal</text>
        </svg>
        <p className="nn-caption">How the signal flows from data to prediction: a logistic-regression model weighs these county factors into one calibrated need score. Higher signal means the county is likelier to sit in Virginia's top need tier.</p>
      </div>
    );
  }

  function MethodsView({ provenance }){
    const provRows = normalizeProvenance(provenance);
    return (
      <div className="content methods">
        <div className="page-head">
          <h1>Methods &amp; data</h1>
          <p>Where every number comes from and how each model works. Explainable by design: every score carries its reasons, every field carries its source, and a provider always decides.</p>
        </div>

        <Panel icon="brain" title="From data to prediction" desc="county factors → weighted combination → prediction">
          <NeuralFlowViz />
        </Panel>

        <Panel icon="layers" title="The data sources" desc="status straight from the dataset's own provenance metadata">
          {Object.keys(provRows).length ? (
            <table className="fc-table methods-table">
              <thead><tr><th>Field group</th><th>Source</th><th>Status</th></tr></thead>
              <tbody>
                {Object.entries(provRows).sort((a,b) => d3.ascending(a[1].status, b[1].status)).map(([field, p]) => (
                  <tr key={field}>
                    <td className="mono">{field}</td>
                    <td>{p.source_id}</td>
                    <td><ProvPill status={p.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p className="hint">Provenance metadata loads with the atlas dataset.</p>}
          <div className="glossary">
            <div><ProvPill status="real" /> <span>Live federal public data, refreshed at build time.</span></div>
            <div><ProvPill status="synthetic" /> <span>Generated, non-PHI stand-in (the patient cohort). Never real people.</span></div>
            <div><ProvPill status="stub" /> <span>A neutral placeholder while ingestion is pending — badged so it can't masquerade as a finding.</span></div>
          </div>
        </Panel>

        <div id="forecast" />
        <Panel icon="trending-up" title="Forecast model card — notifiable-disease early warning" desc="summary of documents/forecast-model-card.md">
          <div className="mc">
            <p><b>The one thing to know first: county numbers are allocated, not observed.</b> CDC NNDSS reports at the
              state level only; every county figure is Virginia's forecast split by county population share. It shows
              relative expected load, never a count of local cases.</p>
            <ul>
              <li><b>Model.</b> Per-condition gradient-boosted quantile regression over CDC NNDSS weekly counts
                (2022–2026, 11 of 139 conditions). Features are strictly past values — a leakage guard fails the build otherwise.</li>
              <li><b>Intervals.</b> Conformalized (split-CQR): the 80% band is widened using held-out residuals, and
                measured coverage is 81% against the nominal 80%.</li>
              <li><b>Skill.</b> Beats the naive baseline on 6 of 8 backtested conditions (skill 0.91 vs naive, 0.81 vs
                seasonal). <b>Chlamydia and Giardiasis lose to the naive baseline</b> and should be read as such.</li>
              <li><b>Threat ranking.</b> A separate "what is unusual right now" score over all 139 conditions: recent
                weekly mean vs the same MMWR weeks in prior years, corroborated against six neighbouring states. Its
                biggest weakness: a cleared reporting backlog looks identical to an outbreak.</li>
              <li><b>Fairness.</b> No demographic feature enters the model. The equity risk is in the population-share
                allocation: nonmetro-adjacent counties (RUCC 4–6) are under-allocated by ~1.5 percentage points — treat
                their figures as a floor, not an estimate.</li>
              <li><b>Human in the loop.</b> Supply quantities come from a hand-authored, reviewable mapping — never from
                the model — and every item is overridable per clinic.</li>
            </ul>
            <p className="hint">Full card: <span className="mono">documents/forecast-model-card.md</span> · plain-language
              guide: <span className="mono">documents/user-guide-early-warning.md</span> (in the project repository).</p>
          </div>
        </Panel>

        <Panel icon="user-check" title="The synthetic cohort" desc="non-PHI by design">
          <div className="mc">
            <p>Patient records shown in the worklist come from a <b>synthetic, non-PHI cohort</b> built for this
              prototype — no live protected health information at any stage, no production EHR connection, and no
              automated clinical decisions. Community conditions are real federal public data. Every patient-level
              screen carries the <ProvPill status="synthetic" label="synthetic cohort" /> badge.</p>
            <p>A provider always decides: accept and override are recorded per patient, with the note on the record.</p>
          </div>
        </Panel>
      </div>
    );
  }

  A.views = A.views || {};
  A.views.MethodsView = MethodsView;
})(window.Atlas);
