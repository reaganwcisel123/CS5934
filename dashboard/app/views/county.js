// County profile (WHO/WHY): model risk and its reasons, need profile, outcomes,
// quality gaps, forecast snapshot, then the gold CTA into the worklist.
(function(A){
  const Icon = A.Icon;
  const { DOMAINS, OUTCOMES, MEASURES } = A.domain;
  const { fmt0, fmt1, sgn, glyph, judge } = A.format;
  const { navigate } = A.router;
  const { Panel, StatCard, ProvPill } = A.ui;
  const { API_BASE, fetchCountyForecast, fetchResourcePrediction } = A.api;
  const { DIV_NEG, DIV_POS } = A.theme;

  function CountyRiskCard({ county }){
    const risk = county.modelRisk;
    if(risk == null) return null;
    const pct = Math.round(risk * 100);
    const high = risk >= 0.5;
    const tier = high ? { t:"High need", c:"var(--danger-500)" }
               : risk >= 0.25 ? { t:"Elevated need", c:"var(--command-600)" }
               : { t:"Lower need", c:"var(--slate-500)" };
    const drivers = county.modelRiskDrivers || [];
    return (
      <div className={"county-risk" + (high ? " high" : "")} id="risk">
        <div>
          <span className="cr-label"><Icon name="brain" size={13} /> County model risk</span>
          <div className="cr-scorerow">
            <span className="cr-score">{pct}%</span>
            <span className="risk-tier" style={{ color:tier.c, borderColor:tier.c }}>{tier.t}</span>
          </div>
          <div className="cr-sub">Modeled probability this county sits in Virginia's top tier for preventable health need.</div>
          <a className="methods-link" href="#/methods">How is this computed? →</a>
        </div>
        {drivers.length > 0 && (
          <div className="cr-why">
            <p className="cr-why-h">Why this county ranks here</p>
            <div>{drivers.map((d, i) => <span key={i} className="risk-chip">{d}</span>)}</div>
          </div>
        )}
      </div>
    );
  }

  // SDoH domain bars; the tick marks the baseline value on each bar.
  function NeedProfile({ c, baseline }){
    const rows = DOMAINS.map(D => ({ ...D, v:c.dom[D.key], bv:baseline.dom[D.key] })).sort((a,b) => b.v - a.v);
    return (
      <Panel icon="layers" title="Need profile" desc={c.name + " · SDoH burden 0–100 · tick = " + baseline.label}>
        {rows.map(D => (
          <div className="bar-row" key={D.key}>
            <span className="t">{D.short}</span>
            <span className="bar" title={"baseline " + fmt0(D.bv)}>
              <span className="fill" style={{ width: Math.max(2, D.v) + "%" }} />
              <span className="tick" style={{ left: Math.max(0, Math.min(100, D.bv)) + "%" }} />
            </span>
            <span className="v mono">{fmt0(D.v)}</span>
          </div>
        ))}
      </Panel>
    );
  }

  function OutcomeRow({ c, baseline }){
    return (
      <Panel icon="activity" title="Chronic outcomes" desc={"CDC PLACES · vs " + baseline.label}>
        <div className="outcome-row">
          {OUTCOMES.map(O => {
            const v = c.outcomes[O.key], bv = baseline.outcomes[O.key];
            const d = (v != null && bv != null) ? v - bv : null;
            return (
              <div key={O.key} className="outcome-cell">
                <div className="k">{O.short}</div>
                <div className="mono v">{v != null ? fmt1(v) + "%" : "—"}</div>
                {d != null && (
                  <div className="delta mono" style={{ color: Math.abs(d) < 0.5 ? "var(--text-muted)" : (d > 0 ? DIV_POS : DIV_NEG) }}>
                    {glyph(d)} {sgn(d)}{fmt1(d)} vs {baseline.short}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </Panel>
    );
  }

  // The two widest quality gaps only.
  function QualitySummary({ c, baseline, provenance }){
    const gaps = MEASURES.map(mz => {
      const cv = c.measures[mz.key], bv = baseline.measures[mz.key];
      if(cv == null || bv == null) return null;
      const w = mz.better === "high" ? bv - cv : cv - bv; // positive = worse
      return { ...mz, cv, bv, w };
    }).filter(Boolean).sort((a,b) => b.w - a.w).slice(0, 2);
    if(!gaps.length) return null;
    const prov = (provenance && provenance.measures) || { status: "stub" };
    return (
      <Panel icon="target" title="Widest quality gaps" desc="HRSA UDS clinical measures"
        badge={<ProvPill status={prov.status} label={prov.status === "real" ? "live" : "pending"} />}>
        {gaps.map(gz => (
          <div className="gap-row" key={gz.key}>
            <span className="gap-label">{gz.label}</span>
            <span className="mono gap-vals">{fmt1(gz.cv)}% vs {fmt1(gz.bv)}%</span>
            <span className="mono gap-delta" style={{ color: gz.w > 1 ? DIV_POS : "var(--text-muted)" }}>
              {gz.w > 0 ? "▲" : "▼"} {fmt0(Math.abs(gz.w))}pt {judge(gz.w)}
            </span>
          </div>
        ))}
      </Panel>
    );
  }

  // Top county-allocated NNDSS warnings, if a live API is configured.
  function ForecastSnapshot({ fips }){
    const [warnings, setWarnings] = React.useState(null);
    React.useEffect(() => {
      if(!API_BASE){ setWarnings(null); return; }
      let alive = true;
      fetchCountyForecast(fips)
        .then(d => alive && setWarnings((d.warnings || []).slice(0, 2)))
        .catch(() => alive && setWarnings([]));
      return () => { alive = false; };
    }, [fips]);
    if(!API_BASE || !warnings || !warnings.length) return null;
    const f = n => n == null ? "—" : (n >= 100 ? Math.round(n).toLocaleString() : n.toFixed(1));
    return (
      <Panel icon="trending-up" title="Coming in the next 4 weeks" desc="NNDSS early warning · county-allocated">
        {warnings.map(w => (
          <div className="gap-row" key={w.condition}>
            <span className="gap-label">{w.condition}</span>
            <span className="mono gap-vals">{f(w.lower)} – {f(w.upper)} cases</span>
            <span className="chip alloc">allocated, not observed</span>
          </div>
        ))}
        <a className="methods-link" href={"#/trends/" + fips}>Full forecast & supply planning →</a>
      </Panel>
    );
  }

  // 30-day resource-plan snapshot: priority, confidence, and the top-line
  // patient volume, with a link into the full categorized plan.
  function ResourcePlanSnapshot({ fips }){
    const [plan, setPlan] = React.useState(null);
    React.useEffect(() => {
      if(!API_BASE){ setPlan(null); return; }
      let alive = true;
      fetchResourcePrediction(fips, 30)
        .then(d => alive && setPlan(d))
        .catch(() => alive && setPlan(null));
      return () => { alive = false; };
    }, [fips]);
    if(!API_BASE || !plan || plan.status !== "ok") return null;
    return (
      <Panel icon="clipboard-check" title="Resource plan" desc="30-day · medications, supplies, equipment & staffing">
        <div className="gap-row">
          <span className="gap-label">Estimated patient volume</span>
          <span className="mono gap-vals">{plan.estimated_patient_volume.toLocaleString()}</span>
        </div>
        <div className="gap-row">
          <span className="gap-label">Priority</span>
          <span className={"chip priority-" + plan.priority_level.toLowerCase()}>{plan.priority_level}</span>
        </div>
        <div className="gap-row">
          <span className="gap-label">Confidence</span>
          <span className={"chip confidence-" + plan.confidence_level.toLowerCase()}>{plan.confidence_level}</span>
        </div>
        <a className="methods-link" href={"#/resource-plan/" + fips}>Full resource plan →</a>
      </Panel>
    );
  }

  function CountyView({ c, baseline, provenance }){
    const topDom = DOMAINS.map(D => ({ ...D, v:c.dom[D.key] })).sort((a,b) => b.v - a.v)[0];
    const scored = (c.patientsList || []).filter(p => p.risk != null);
    const highN = scored.filter(p => p.riskTier === "High").length;
    return (
      <div className="content">
        <div className="page-head">
          <h1>Why {c.name} ranks here</h1>
          <p>Where unmet need concentrates in <b>{c.name}</b> — federal SDoH, chronic-disease, and shortage-area signals versus the {baseline.label} baseline. Every figure carries its source.</p>
        </div>

        <CountyRiskCard county={c} />

        <div className="stat-grid">
          <div className="stat-cell" title="Composite 0–100 score of unmet health need. Higher means more need.">
            <StatCard label="Unmet-need index" value={fmt0(c.needIndex)} unit="/100" accent="signal" icon={<Icon name="gauge" size={18} />} />
          </div>
          <div className="stat-cell" title="HRSA primary-care shortage score, 0–26. Higher means a worse provider shortage.">
            <StatCard label="Primary-care HPSA" value={String(c.hpsaScore)} unit="/26" accent="signal" icon={<Icon name="map-pin" size={18} />} />
          </div>
          <div className="stat-cell" title="Share of adults with diagnosed diabetes (CDC PLACES).">
            <StatCard label="Diabetes prevalence" value={c.outcomes.diabetes != null ? fmt1(c.outcomes.diabetes) : "—"} unit="%" accent="signal" icon={<Icon name="activity" size={18} />} />
          </div>
          <div className="stat-cell" title="The SDoH domain carrying this county's highest burden right now.">
            <StatCard label={"Top need · " + topDom.short} value={fmt0(topDom.v)} unit="/100" accent="command" icon={<Icon name="alert-triangle" size={18} />} />
          </div>
        </div>

        <div className="county-grid">
          <NeedProfile c={c} baseline={baseline} />
          <div className="county-side">
            <OutcomeRow c={c} baseline={baseline} />
            <QualitySummary c={c} baseline={baseline} provenance={provenance} />
            <ForecastSnapshot fips={c.id} />
            <ResourcePlanSnapshot fips={c.id} />
          </div>
        </div>

        <div className="cta-band" id="next">
          <div>
            <h3>What next?</h3>
            <p>
              {scored.length
                ? <React.Fragment><b>{highN} of {scored.length}</b> patients in the synthetic cohort carry a high preventable-hospitalization risk — each with the reason attached and a next step a nurse can act on today.</React.Fragment>
                : "The live API does not serve a patient roster; the outreach worklist uses the synthetic cohort in static mode."}
            </p>
            <p className="cta-note">A provider always decides. Accept and override are recorded.</p>
          </div>
          {scored.length > 0 && (
            <button className="btn-gold" onClick={() => navigate("/worklist/" + c.id)}>
              Open outreach worklist — {highN} high-risk <Icon name="arrow-right" size={15} />
            </button>
          )}
        </div>
      </div>
    );
  }

  A.views = A.views || {};
  A.views.CountyView = CountyView;
})(window.Atlas);
