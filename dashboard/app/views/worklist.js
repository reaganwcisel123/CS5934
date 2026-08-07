// Worklist (WHAT NEXT): the funnel band + ranked patient table with per-patient
// Accept/Override review (US-021/022), persisted locally and posted to the audit API.
(function(A){
  const { interventionsForTier } = A.domain;
  const { fmt0, fmtC } = A.format;
  const { Panel, ProvPill } = A.ui;
  const { postEvent } = A.api;

  const TIER = { High:"var(--danger-500)", Medium:"var(--command-600)", Low:"var(--slate-500)" };

  // Narrowing-the-field funnel; each stage names its source.
  function FunnelBand({ records, c, scored, highN }){
    const statewide = d3.sum(records, r => r.patients) || 0;
    const stages = [
      { n: statewide, label: "Virginians", src: "Census PEP" },
      { n: c.patients, label: c.name, src: "county population" },
      { n: scored.length, label: "synthetic panel", src: "non-PHI cohort" },
      { n: highN, label: "high risk — act now", src: "model-ranked", hot: true },
    ].filter(s => s.n != null);
    const max = Math.max(...stages.map(s => s.n), 1);
    return (
      <div className="funnel" role="img" aria-label={"Narrowing the field: " + stages.map(s => fmtC(s.n) + " " + s.label).join(", then ")}>
        {stages.map((s, i) => (
          <React.Fragment key={i}>
            {i > 0 && <span className="funnel-arrow" aria-hidden="true">→</span>}
            <div className={"funnel-stage" + (s.hot ? " hot" : "")}>
              <div className="mono fn">{fmtC(s.n)}</div>
              <div className="fl">{s.label}</div>
              <div className="fs">{s.src}</div>
              <div className="fbar"><span style={{ width: Math.max(2, Math.sqrt(s.n / max) * 100) + "%" }} /></div>
            </div>
          </React.Fragment>
        ))}
      </div>
    );
  }

  // Per-patient review state, keyed atlas_hitl_<fips>_<patientKey>.
  function useReview(fips, patientKey){
    const KEY = "atlas_hitl_" + fips + "_" + patientKey;
    const read = () => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch(e){ return {}; } };
    const [state, setState] = React.useState(read);
    React.useEffect(() => { setState(read()); }, [KEY]);
    const save = next => {
      setState(next);
      try { localStorage.setItem(KEY, JSON.stringify(next)); } catch(e){}
      // Audit trail: the same decision goes to the server when an API is on.
      postEvent("patient_review", fips, { patient: patientKey, status: next.status, note: next.note || "" });
    };
    return [state, save];
  }

  function PatientRow({ p, idx, fips, expanded, onToggle, onReviewed }){
    const [review, saveRaw] = useReview(fips, idx);
    const save = next => { saveRaw(next); onReviewed && onReviewed(); };
    const [note, setNote] = React.useState("");
    const status = review.status || "pending";
    const actions = interventionsForTier(p.riskTier);
    return (
      <React.Fragment>
        <tr className={"wl-row" + (expanded ? " open" : "")} onClick={onToggle}>
          <td className="wl-name">{p.name} <span className="risk-sub">· {p.age}</span></td>
          <td className="mono">{Math.round((p.risk || 0) * 100)}%</td>
          <td><span className="risk-tier" style={{ color:TIER[p.riskTier], borderColor:TIER[p.riskTier] }}>{p.riskTier}</span></td>
          <td>{(p.riskDrivers || []).map((d, j) => <span key={j} className="risk-chip">{d}</span>)}</td>
          <td className="wl-next">{actions[0]}</td>
          <td onClick={e => e.stopPropagation()}>
            <div className="wl-actions">
              <button className={"wl-btn" + (status === "accepted" ? " ok" : "")}
                onClick={() => save({ status: status === "accepted" ? "pending" : "accepted" })}>
                {status === "accepted" ? "✓ Accepted" : "Accept"}</button>
              <button className={"wl-btn" + (status === "overridden" ? " ov" : "")}
                onClick={onToggle}>{status === "overridden" ? "Overridden" : "Override"}</button>
            </div>
          </td>
        </tr>
        {expanded && (
          <tr className="wl-expand">
            <td colSpan={6}>
              <div className="wl-detail">
                <div>
                  <div className="wl-detail-h">All suggested steps for {p.riskTier} risk</div>
                  <ul>{actions.map((a, i) => <li key={i}>{a}</li>)}</ul>
                </div>
                <div>
                  <div className="wl-detail-h">Provider override</div>
                  <textarea rows={3} value={note} onChange={e => setNote(e.target.value)}
                    placeholder="Describe the provider's alternative action…" aria-label="Override note" />
                  <div className="wl-detail-btns">
                    <button className="wl-btn ov" onClick={() => save({ status: "overridden", note })}>Save override</button>
                    {status !== "pending" && <button className="wl-btn" onClick={() => save({ status: "pending" })}>Reset to pending</button>}
                  </div>
                  {status === "overridden" && review.note && <p className="wl-note"><b>Override note:</b> {review.note}</p>}
                </div>
              </div>
            </td>
          </tr>
        )}
      </React.Fragment>
    );
  }

  function WorklistView({ c, records }){
    const [expanded, setExpanded] = React.useState(null);
    const [, bump] = React.useReducer(x => x + 1, 0);   // re-count after a row saves
    const scoredIdx = (c.patientsList || []).map((p, i) => ({ p, i })).filter(x => x.p.risk != null);
    const ranked = scoredIdx.slice().sort((a, b) => (b.p.risk || 0) - (a.p.risk || 0));
    const highN = ranked.filter(x => x.p.riskTier === "High").length;
    const reviewed = ranked.filter(x => {
      try { const s = JSON.parse(localStorage.getItem("atlas_hitl_" + c.id + "_" + x.i)) || {}; return s.status && s.status !== "pending"; }
      catch(e){ return false; }
    }).length;

    if(!ranked.length) return (
      <div className="content">
        <div className="page-head"><h1>Outreach worklist</h1></div>
        <div className="empty">No scored patients are available for {c.name}. The live API does not serve a
          patient roster — the worklist uses the synthetic cohort in static mode.
          {" "}<a href={"#/county/" + c.id}>Back to the county profile</a>.</div>
      </div>
    );

    return (
      <div className="content">
        <div className="page-head wl-head">
          <div>
            <h1>Today's outreach worklist</h1>
            <p>Model-ranked and reviewable — the reason and the next step attached to every name. <b>A provider decides; the Atlas only recommends.</b></p>
          </div>
          <div className="wl-head-right">
            <ProvPill status="synthetic" label="synthetic cohort" />
            <span className="wl-progress mono">{reviewed} of {ranked.length} reviewed</span>
          </div>
        </div>

        <FunnelBand records={records} c={c} scored={ranked} highN={highN} />

        <Panel icon="list-checks" title={"Ranked by risk — " + c.name} desc={highN + " high-risk of " + ranked.length + " · click a row for all steps"}>
          <div className="wl-scroll">
            <table className="risk-table wl-table">
              <thead><tr><th>Patient</th><th>Risk</th><th>Tier</th><th>Why (top drivers)</th><th>Recommended next step</th><th>Review</th></tr></thead>
              <tbody>
                {ranked.map(({ p, i }) => (
                  <PatientRow key={i} p={p} idx={i} fips={c.id} onReviewed={bump}
                    expanded={expanded === i} onToggle={() => setExpanded(expanded === i ? null : i)} />
                ))}
              </tbody>
            </table>
          </div>
          <p className="risk-note">Synthetic non-PHI cohort, generated for this prototype. Risk is a model estimate for
            prioritization; accept/override decisions are recorded {A.api.AUTH_ON ? "to the audit trail" : "in this browser (sign in to a live API for the shared audit trail)"}.</p>
        </Panel>
      </div>
    );
  }

  A.views = A.views || {};
  A.views.WorklistView = WorklistView;
})(window.Atlas);
