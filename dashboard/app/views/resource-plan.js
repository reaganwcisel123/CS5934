// Resource plan: predicted medications, supplies, equipment, and staffing for
// the selected county over a configurable planning window (Predictive
// Analytics epic). County-scoped off the global county chip, same as Trends.
(function(A){
  const Icon = A.Icon;
  const { API_BASE, authHeaders, resourcePredictionExportUrl } = A.api;
  const { navigate } = A.router;
  const { Panel, StatCard } = A.ui;

  const WINDOWS = [30, 60, 90];

  const ITEM_LABELS = {
    // medications
    hypertension_medications: "Hypertension medications",
    diabetes_medications_and_insulin: "Diabetes medications & insulin",
    cholesterol_medications: "Cholesterol medications",
    asthma_inhalers: "Asthma inhalers",
    antibiotics: "Antibiotics",
    pain_management_medications: "Pain management medications",
    vaccines: "Vaccines",
    // medical supplies
    syringes: "Syringes", needles: "Needles", gloves: "Gloves", masks: "Masks",
    ppe: "PPE", bandages: "Bandages", iv_supplies: "IV supplies",
    test_strips: "Test strips", specimen_collection_kits: "Specimen collection kits",
    // diagnostic equipment
    blood_pressure_cuffs: "Blood pressure cuffs", glucose_monitors: "Glucose monitors",
    pulse_oximeters: "Pulse oximeters", ecg_equipment: "ECG equipment",
    point_of_care_testing_supplies: "Point-of-care testing supplies",
    // staffing
    physicians: "Physicians", nurse_practitioners: "Nurse practitioners",
    registered_nurses: "Registered nurses", medical_assistants: "Medical assistants",
    behavioral_health_specialists: "Behavioral health specialists",
    care_coordinators: "Care coordinators",
  };
  const label = key => ITEM_LABELS[key] || key.replace(/_/g, " ").replace(/^./, c => c.toUpperCase());

  const fmtInt = n => n == null ? "—" : Math.round(n).toLocaleString();
  const fmtFte = n => n == null ? "—" : n.toFixed(2);

  const PRIORITY_CLASS = { Critical: "priority-critical", High: "priority-high", Medium: "priority-medium", Low: "priority-low" };
  const CONFIDENCE_CLASS = { High: "confidence-high", Medium: "confidence-medium", Low: "confidence-low" };

  function PriorityChip({ level }){
    if(!level) return null;
    return <span className={"chip " + (PRIORITY_CLASS[level] || "")}>{level} priority</span>;
  }
  function ConfidenceChip({ level }){
    if(!level) return null;
    return <span className={"chip " + (CONFIDENCE_CLASS[level] || "")}>{level} confidence</span>;
  }

  function useJson(url){
    const [state, setState] = React.useState({ loading: true, data: null, error: null });
    React.useEffect(() => {
      if(!url){ setState({ loading: false, data: null, error: null }); return; }
      let alive = true;
      setState({ loading: true, data: null, error: null });
      fetch(url, { headers: authHeaders() })
        .then(r => { if(!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
        .then(d => alive && setState({ loading: false, data: d, error: null }))
        .catch(e => alive && setState({ loading: false, data: null, error: e.message }));
      return () => { alive = false; };
    }, [url]);
    return state;
  }

  function CategoryTable({ items }){
    const rows = Object.values(items || {});
    if(!rows.length) return <div className="row-sub unknown">No items in this category.</div>;
    return (
      <table className="fc-table">
        <thead><tr><th>Item</th><th style={{ textAlign: "right" }}>Quantity</th></tr></thead>
        <tbody>
          {rows.map(it => (
            <tr key={it.item}>
              <td>
                {label(it.item)}
                {it.overridden && <span className="chip alloc" style={{ marginLeft: 6 }}>overridden</span>}
                {it.note && <div className="muted" style={{ fontSize: 11 }}>{it.note}</div>}
              </td>
              <td className="qty mono">
                {it.unit === "FTE" ? fmtFte(it.quantity) : fmtInt(it.quantity)}{it.unit ? " " + it.unit : ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  function ExplanationList({ lines }){
    if(!lines || !lines.length) return null;
    return (
      <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, lineHeight: 1.6, color: "var(--text-body)" }}>
        {lines.map((l, i) => <li key={i}>{l}</li>)}
      </ul>
    );
  }

  function ResourcePlanBoard({ c, window: win, data }){
    const review = data.clinical_review;
    return (
      <React.Fragment>
        {review && review.clinical_review !== "approved" && (
          <div className="review">
            <span>&#9998;</span>
            <div><b>These assumptions are pending clinical review.</b> {review.note}</div>
          </div>
        )}

        <div className="disclosure">
          <span>&#9432;</span>
          <div>{data.scope_note}</div>
        </div>

        <div className="stat-grid">
          <div className="stat-cell" title="Total expected patient encounters across the county's primary-care capacity over the selected window.">
            <StatCard label="Estimated patient volume" value={fmtInt(data.estimated_patient_volume)} unit={`/ ${win}d`} icon={<Icon name="user-check" size={18} />} />
          </div>
          <div className="stat-cell" title={data.priority_factors ? data.priority_factors.join(" · ") : ""}>
            <StatCard label="Priority" value={data.priority_level || "—"} unit={data.priority_score != null ? `${data.priority_score}/100` : ""} accent="command" icon={<Icon name="alert-triangle" size={18} />} />
          </div>
          <div className="stat-cell" title="How many source inputs were the county's own observed values vs. a statewide or config fallback.">
            <StatCard label="Confidence" value={data.confidence_level || "—"} unit={data.confidence_detail ? `${data.confidence_detail.fields_from_county_data}/${data.confidence_detail.fields_checked} observed` : ""} icon={<Icon name="gauge" size={18} />} />
          </div>
          <div className="stat-cell" title="Assumptions version, so a prediction can be reproduced against the exact config that produced it.">
            <StatCard label="Assumptions" value={"v" + data.assumptions_version} unit={data.historical_data_used ? "history-adjusted" : "cross-sectional"} icon={<Icon name="clipboard-check" size={18} />} />
          </div>
        </div>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <PriorityChip level={data.priority_level} />
          <ConfidenceChip level={data.confidence_level} />
        </div>

        <Panel icon="info" title="What's driving this plan">
          <ExplanationList lines={data.explanation} />
        </Panel>

        <div className="ew-grid">
          <div className="panel">
            <div className="panel-h"><h3>Medications</h3><span className="desc">medications, vaccines &amp; insulin</span></div>
            <div className="panel-body"><CategoryTable items={data.medications} /></div>
          </div>
          <div className="panel">
            <div className="panel-h"><h3>Staffing</h3><span className="desc">county-wide FTE</span></div>
            <div className="panel-body"><CategoryTable items={data.staffing} /></div>
          </div>
        </div>

        <div className="ew-grid">
          <div className="panel">
            <div className="panel-h"><h3>Medical supplies</h3></div>
            <div className="panel-body"><CategoryTable items={data.medical_supplies} /></div>
          </div>
          <div className="panel">
            <div className="panel-h"><h3>Diagnostic equipment</h3><span className="desc">on-hand estimate</span></div>
            <div className="panel-body"><CategoryTable items={data.diagnostic_equipment} /></div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-h"><h3>Export</h3><span className="desc">for procurement / staffing conversations</span></div>
          <div className="panel-body" style={{ display: "flex", gap: 8 }}>
            <a className="toolbtn" href={resourcePredictionExportUrl(c.id, win, "csv")}>Export CSV</a>
            <a className="toolbtn" href={resourcePredictionExportUrl(c.id, win, "json")}>Export JSON</a>
          </div>
        </div>

        <p className="row-sub muted" style={{ maxWidth: 820 }}>
          {data.disclaimer} See <a href="#/methods">the methods page</a> and{" "}
          <span className="mono">documents/resource-prediction-methodology.md</span> for the full formulas and fallback rules.
        </p>
      </React.Fragment>
    );
  }

  function ResourcePlanView({ c, window: win }){
    const setWindow = w => navigate("/resource-plan" + (c ? "/" + c.id : ""), { query: { window: w }, replace: true });
    const url = API_BASE && c ? `${API_BASE}/resource-predictions/counties/${c.id}?window=${win}` : null;
    const state = useJson(url);
    const data = state.data;

    return (
      <div className="content trends-forecast">
        <div className="page-head trends-head">
          <div>
            <h1>Resource plan{c ? ` — ${c.name}` : ""}</h1>
            <p className="trends-sub">
              Predicted medications, supplies, diagnostic equipment, and staffing this county's primary-care
              capacity is expected to need over the selected planning window, from county health indicators
              and published planning benchmarks.
            </p>
          </div>
          <div className="seg" role="tablist" aria-label="Planning window">
            {WINDOWS.map(w => (
              <button key={w} role="tab" aria-selected={win === w} className={win === w ? "on" : ""} onClick={() => setWindow(w)}>
                {w} days
              </button>
            ))}
          </div>
        </div>

        {!API_BASE && (
          <div className="disclosure">
            <span>&#9432;</span>
            <div>No live resource plan without an API. Append <span className="mono">?api=http://localhost:8010/api</span> to
            this URL, or set <span className="mono">window.CLINIC_ATLAS_API</span> in <span className="mono">config.js</span>.</div>
          </div>
        )}
        {API_BASE && !c && <div className="row-sub muted">Choose a county (top right) to see its resource plan.</div>}
        {API_BASE && c && state.loading && <div className="row-sub muted">Loading…</div>}
        {API_BASE && c && state.error && <div className="err">Could not load this county's resource plan: {state.error}</div>}
        {API_BASE && c && data && data.status === "insufficient_data" && (
          <div className="disclosure"><span>&#9888;</span><div>{data.explanation && data.explanation[0]}</div></div>
        )}
        {API_BASE && c && data && data.status === "ok" && <ResourcePlanBoard c={c} window={win} data={data} />}
      </div>
    );
  }

  A.views = A.views || {};
  A.views.ResourcePlanView = ResourcePlanView;
})(window.Atlas);
