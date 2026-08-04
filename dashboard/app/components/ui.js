// Shared UI primitives. StatCard/Tabs are local reimplementations of the only
// DS-bundle components the app used — the bundle itself is no longer loaded.
(function(A){
  const Icon = A.Icon;

  const REQUIRED_PROVENANCE = {
    patientsList: { source_id: "synthetic_clinical_dataset", status: "synthetic" },
    chronicDiseaseRisk: { source_id: "virginia_chronic_disease_hospitalization", status: "real" },
  };

  function normalizeProvenance(provenance){
    const base = provenance && typeof provenance === "object" ? provenance : {};
    const out = { ...base };
    for(const [field, meta] of Object.entries(REQUIRED_PROVENANCE)){
      if(!out[field]) out[field] = meta;
    }
    return out;
  }

  function StatCard({ label, value, unit, icon, accent }){
    return (
      <div className={"statcard" + (accent ? " accent-" + accent : "")}>
        <div className="statcard-top">
          <span className="statcard-label">{label}</span>
          {icon && <span className="statcard-icon">{icon}</span>}
        </div>
        <div className="statcard-value mono">{value}{unit && <span className="statcard-unit">{unit}</span>}</div>
      </div>
    );
  }

  function Tabs({ items, value, onChange }){
    return (
      <div className="tabs" role="tablist">
        {items.map(it => (
          <button key={it.id} role="tab" aria-selected={value === it.id}
            className={"tab" + (value === it.id ? " on" : "")}
            onClick={() => onChange(it.id)}>{it.label}</button>
        ))}
      </div>
    );
  }

  function Panel({ icon, title, desc, children, bodyClass, badge }){
    return (
      <div className="panel">
        <div className="panel-h"><Icon name={icon} size={16} color="var(--brand)" /><h3>{title}</h3>{badge}{desc && <span className="desc">{desc}</span>}</div>
        <div className={"panel-body " + (bodyClass || "")}>{children}</div>
      </div>
    );
  }

  const PROV = { real:{c:"var(--brand)", t:"live"}, synthetic:{c:"var(--violet-500)", t:"synthetic"}, stub:{c:"var(--command-600)", t:"pending"} };

  // Small per-panel pill: accountability exactly where a field is used.
  function ProvPill({ status, label }){
    const s = PROV[status] || PROV.stub;
    return <span className="pill" style={{ borderColor:s.c, color:s.c }}><span className="dot" style={{ background:s.c }} />{label || s.t}</span>;
  }

  // Full provenance strip (Overview only) driven by the dataset's own metadata.
  function Provenance({ provenance }){
    const normalized = normalizeProvenance(provenance);
    if(!Object.keys(normalized).length) return null;
    return (
      <div className="prov"><span className="lbl">Data provenance:</span>
        {Object.entries(normalized).sort((a,b) => d3.ascending(a[1].status, b[1].status)).map(([field, p]) => {
          const s = PROV[p.status] || PROV.stub;
          return <span className="pill" key={field} title={field + " is " + s.t + " (source: " + p.source_id + ")"} style={{ borderColor:s.c, color:s.c }}><span className="dot" style={{ background:s.c }} />{field} · {p.source_id} · {s.t}</span>;
        })}
      </div>
    );
  }

  // ref + effect: draws are idempotent (each starts with d3.select(el).html("")).
  function D3Panel({ draw, ctx, style }){
    const ref = React.useRef(null);
    React.useEffect(() => { if(ref.current && ctx.records.length) draw(ref.current, ctx); });
    return <div ref={ref} style={style} />;
  }

  // Contain a crashing view so the shell (nav, county chip) survives.
  class ErrorBoundary extends React.Component {
    constructor(p){ super(p); this.state = { err: null }; }
    static getDerivedStateFromError(err){ return { err }; }
    componentDidUpdate(prev){ if(prev.resetKey !== this.props.resetKey && this.state.err) this.setState({ err: null }); }
    render(){
      if(this.state.err) return <div className="empty">This view hit an error: {String(this.state.err.message || this.state.err)}. Try another view or reload.</div>;
      return this.props.children;
    }
  }

  A.ui = { StatCard, Tabs, Panel, ProvPill, Provenance, D3Panel, ErrorBoundary, normalizeProvenance };
})(window.Atlas);
