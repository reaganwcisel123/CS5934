// Explore — analyst tools: scatter, deviation heatmap, quality gaps, and the
// Needs Forest (demo data). Chart clicks update the global county chip in place.
(function(A){
  const { REGIONS } = A.domain;
  const { fmt0, fmtC } = A.format;
  const { navigate } = A.router;
  const { Panel, Tabs, D3Panel, ProvPill } = A.ui;
  const { REGION_COLOR } = A.theme;
  const { fetchGeo } = A.api;

  const TABS = [
    { id: "scatter", label: "Need vs. population" },
    { id: "heatmap", label: "Deviation heatmap" },
    { id: "quality", label: "Quality gaps" },
    { id: "forest", label: "Needs forest" },
  ];

  /* -------- Needs Forest (dummy data, teammate-built) ---------------------- */

  function GlyphBox({ gr, R, interactive, showRing = true, pad = 14 }){
    const ref = React.useRef(null);
    React.useEffect(() => {
      const S = (R + pad) * 2, host = d3.select(ref.current).html("");
      const svg = host.append("svg").attr("viewBox", `0 0 ${S} ${S}`).attr("width", S).attr("height", S)
        .attr("role", "img").attr("aria-label", `Glyph for ${gr ? gr.name : "sample"}`);
      if(gr) A.forest.drawGlyph(svg.append("g").attr("transform", `translate(${S / 2},${S / 2})`), gr, { R, interactive, showRing });
    });
    return <div ref={ref} />;
  }
  function sampleGlyph(bn, rf){
    const o = { burdenNorm: {}, respPct: {}, placesByAxis: {} };
    A.forest.AXES.forEach(a => { o.burdenNorm[a.key] = bn; o.respPct[a.key] = rf * 100; o.placesByAxis[a.key] = 0; });
    return o;
  }

  function ResponseRamp(){
    const S = 54, R = 24, C = "#0284c7", full = d3.arc().innerRadius(0).outerRadius(R).startAngle(-Math.PI / 4).endAngle(Math.PI / 4)();
    const wedge = half => d3.arc().innerRadius(0).outerRadius(R).startAngle(-half).endAngle(half).cornerRadius(R * 0.13)();
    return (
      <div className="density">
        {[0.25, 0.55, 0.9].map((rf, i) => {
          const half = Math.max(0.05, (Math.PI / 4) * (1 - rf));
          return (
            <div className="cell" key={i}>
              <svg width={S} height={S} viewBox={`0 0 ${S} ${S}`}><g transform={`translate(${S / 2},${S / 2})`}>
                <path d={full} fill={C} fillOpacity="0.1" />
                <path d={wedge(half)} fill={A.forest.lighten(C, 0.62)} stroke={C} strokeWidth="1.4" strokeLinejoin="round" />
              </g></svg>
              <div className="cap">{Math.round(rf * 100)}%</div>
            </div>
          );
        })}
      </div>
    );
  }

  function ForestLegend({ sample }){
    const AXES = A.forest.AXES;
    const examples = [
      { g: sampleGlyph(0.92, 0.15), t: "most in need", d: "big, full quarters" },
      { g: sampleGlyph(0.92, 0.90), t: "responding",   d: "long, thin slivers" },
      { g: sampleGlyph(0.30, 0.5),  t: "low burden",   d: "small" },
    ];
    return (
      <div>
        <div className="leg-sect">
          <h4>Anatomy of a glyph</h4>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            {sample && <GlyphBox gr={sample} R={52} interactive pad={10} />}
            <div className="leg-note" style={{ margin: 0 }}>
              Each glyph is four <b>wedges</b>, one per indicator. A wedge reaches
              <b> outward as far as the PLACES community burden</b>. Its <b>width shrinks as UDS
              response rises</b> — an unmet measure fills its whole quarter; a well-controlled one
              narrows to a thin sliver. The more controlled, the less you see.
            </div>
          </div>
        </div>
        <div className="leg-sect">
          <h4>Quarters (position &amp; color)</h4>
          {AXES.map(ax => (
            <div className="leg-row" key={ax.key}>
              <span className="sw" style={{ background: ax.color }} />
              <span style={{ width: 96 }}>{ax.label} <span style={{ color: "var(--text-muted)" }}>({ax.pos})</span></span>
              <span style={{ color: "var(--text-muted)", fontSize: 11.5 }}>PLACES {ax.places} · UDS {ax.udsShort}</span>
            </div>
          ))}
        </div>
        <div className="leg-sect">
          <h4>Wedge width = UDS response</h4>
          <ResponseRamp />
          <div className="leg-note">A narrower wedge = better response (more controlled). Polarity is
            unified to “responding well”, so diabetes uses control rate (<b>100 − dm_poor</b>).</div>
        </div>
        <div className="leg-sect">
          <h4>Reading the glyphs</h4>
          <div style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
            {examples.map((ex, i) => (
              <div key={i} style={{ textAlign: "center", flex: 1 }}>
                <GlyphBox gr={ex.g} R={40} pad={8} />
                <div style={{ fontSize: 11.5, fontWeight: 600, color: "var(--text-strong)" }}>{ex.t}</div>
                <div style={{ fontSize: 10.5, color: "var(--text-muted)" }}>{ex.d}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  function ForestSide({ data, onSelect }){
    const ranked = data.grantees.slice().sort((a,b) => b.needScore - a.needScore);
    const sample = ranked[Math.floor(ranked.length / 2)];
    const col = d3.scaleLinear().domain([d3.min(data.grantees, g => g.needScore), d3.max(data.grantees, g => g.needScore)])
      .range([A.theme.DIV_NEG, A.theme.DIV_POS]).interpolate(d3.interpolateLab).clamp(true);
    return (
      <React.Fragment>
        <div className="panel">
          <div className="panel-h"><h3>Legend</h3><span className="desc">how to read a glyph</span></div>
          <div className="panel-body" style={{ paddingTop: 4 }}><ForestLegend sample={sample} /></div>
        </div>
        <div className="panel" style={{ marginTop: 16 }}>
          <div className="panel-h"><h3>Most in need</h3><span className="desc">burden × (1 − response)</span></div>
          <div className="panel-body" style={{ paddingTop: 6 }}>
            {ranked.slice(0, 8).map((g, i) => (
              <div className="needrow" key={g.id} onClick={() => onSelect(g.id)}>
                <span className="rank">{i + 1}</span><span className="nm">{g.name}</span>
                <span className="sc" style={{ color: col(g.needScore) }}>{fmt0(g.needScore * 100)}</span>
              </div>
            ))}
          </div>
        </div>
      </React.Fragment>
    );
  }

  function DualBar(props){
    const ref = React.useRef(null);
    React.useEffect(() => { if(props.rows.length) A.forest.drawDualBar(ref.current, props); });
    return <div ref={ref} />;
  }

  function GranteeSide({ g, onBack }){
    const rows = A.forest.AXES.map(ax => ({
      key: ax.key, label: ax.label, color: ax.color,
      top: g.respPct[ax.key], bottom: g.placesByAxis[ax.key], gap: g.respPct[ax.key] - g.placesByAxis[ax.key],
      udsShort: ax.udsShort, placesShort: ax.placesLabel,
    })).sort((a,b) => Math.abs(b.gap) - Math.abs(a.gap));
    return (
      <div className="panel">
        <div className="panel-h"><h3>{g.name}</h3><button className="backbtn" style={{ marginLeft: "auto" }} onClick={onBack}>← Forest</button></div>
        <div className="panel-body">
          <div style={{ display: "flex", justifyContent: "center" }}><GlyphBox gr={g} R={108} interactive pad={18} /></div>
          <div className="kv" style={{ justifyContent: "center", marginTop: 2 }}>
            <div><div className="k">Clinics</div><div className="v mono">{g.clinics.length}</div></div>
            <div><div className="k">Patients</div><div className="v mono">{fmtC(Math.round(g.uds.patient_count))}</div></div>
            <div><div className="k">Counties</div><div className="v mono">{g.counties.length}</div></div>
            <div><div className="k">Regions</div><div className="v">{g.regions.length}</div></div>
          </div>
          <div style={{ fontSize: 11.5, color: "var(--text-muted)", margin: "8px 0 2px" }}>UDS response vs PLACES burden — sorted by |gap|</div>
          <DualBar rows={rows} topLabel="UDS response" botLabel="PLACES burden"
            colorTop={r => r.color} colorBottom={r => r.color} note="hover a bar for values" />
          <div style={{ fontSize: 11.5, color: "var(--text-muted)", margin: "6px 0 2px" }}>Clinics <span className="hint">(highlighted on the map — hover a dot)</span></div>
          <div className="cliniclist">
            {g.clinics.map(c => (
              <div className="c" key={c.id}><span className="dot" /><span className="cn">{c.name}</span><span className="cp mono">{fmtC(c.patients)}</span></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  function ForestMapPanel({ data, mode, selectedId, onSelect }){
    const ref = React.useRef(null), api = React.useRef(null);
    React.useEffect(() => { if(data){ api.current = A.forest.buildForestMap(ref.current, data, onSelect); } }, [data]);
    React.useEffect(() => { if(api.current) api.current.update(mode, selectedId); }, [mode, selectedId, data]);
    return <div ref={ref} className="mapholder" />;
  }

  // Grantee drill-in lives in the URL (?grantee=G7) so back exits it.
  function ForestTab({ granteeId }){
    const [data, setData] = React.useState(null);
    const [err, setErr] = React.useState(null);
    React.useEffect(() => {
      fetchGeo().then(geo => setData(A.forest.buildDummyData(geo)))
        .catch(e => setErr("Could not load data/va-counties.geojson (" + e.message + ")."));
    }, []);
    const select = id => navigate("/explore", { query: { tab: "forest", grantee: id || "" } });
    const mode = granteeId ? "grantee" : "forest";
    const g = data && granteeId ? data.grantees.find(x => x.id === granteeId) : null;

    if(err) return <div className="empty">{err}</div>;
    if(!data) return <div className="empty">Loading forest…</div>;

    return (
      <React.Fragment>
        <p className="trends-sub">Each glyph is a grantee, drawn as four wedges. A wedge reaches
          <b> outward with PLACES community burden</b> and <b> narrows as UDS clinic response rises</b> (controlled
          = a thin sliver). Big, full quarters = most in need. Click a glyph to drill in.
          {" "}<span className="chronic-mock">Demo data — grantees and clinics are simulated.</span></p>
        <div className="ew-grid">
          <section className="panel">
            <div className="panel-h">
              <h3>{mode === "grantee" && g ? g.name : "Virginia — grantee forest"}</h3>
              <span className="desc">{mode === "grantee" && g ? `${g.clinics.length} clinics highlighted · zoomed` : `${data.grantees.length} grantees`}</span>
              {mode === "grantee" && <button className="backbtn" style={{ marginLeft: 10 }} onClick={() => select(null)}>← Back to forest</button>}
            </div>
            <div className="panel-body" style={{ padding: 8 }}>
              <ForestMapPanel data={data} mode={mode} selectedId={granteeId} onSelect={select} />
            </div>
          </section>
          <aside>
            {mode === "grantee" && g
              ? <GranteeSide g={g} onBack={() => select(null)} />
              : <ForestSide data={data} onSelect={select} />}
          </aside>
        </div>
      </React.Fragment>
    );
  }

  /* -------- The view -------------------------------------------------------- */

  function ExploreView({ records, fips, baselineMode, provenance, query }){
    const tab = query.tab || "scatter";
    const setTab = id => navigate("/explore", { query: { tab: id }, replace: true });
    const c = A.store.byId(fips);
    const measuresProv = (provenance && provenance.measures) || { status: "stub" };

    // Chart clicks re-scope the global county context without leaving Explore.
    const ctx = {
      records, selectedId: fips, baselineMode,
      byId: A.store.byId,
      baselineFor: x => A.store.baselineFor(x, baselineMode),
      onSelect: id => A.store.rememberFips(id),
    };

    return (
      <div className="content">
        <div className="page-head">
          <h1>Explore the data</h1>
          <p>Analyst instruments — how any county stacks against its peers. Selecting a county here updates
            your county context{c ? <React.Fragment>: currently <b>{c.name}</b> — <a href={"#/county/" + c.id}>open its profile →</a></React.Fragment> : "."}</p>
        </div>

        <div className="tabwrap"><Tabs items={TABS} value={tab} onChange={setTab} /></div>

        {tab === "scatter" && (
          <Panel icon="scatter-chart" title="Need vs. population" desc="size = HPSA · color = region · click a dot">
            <D3Panel draw={A.charts.drawScatter} ctx={ctx} style={{ maxWidth: 520 }} />
            <div className="region-legend" style={{ maxWidth: 520 }}>{REGIONS.map(rg => <span key={rg}><span className="dot" style={{ background: REGION_COLOR[rg] }} />{rg}</span>)}</div>
          </Panel>
        )}

        {tab === "heatmap" && (
          <Panel icon="grid-3x3" title="Deviation heatmap" desc="every county vs. baseline · red worse, blue better · click a row" bodyClass="heat-scroll">
            <D3Panel draw={A.charts.drawHeatmap} ctx={ctx} />
          </Panel>
        )}

        {tab === "quality" && (
          <Panel icon="target" title="Quality gap from baseline" desc="UDS clinical measures · ◯ baseline, ● this county"
            badge={<ProvPill status={measuresProv.status} label={"UDS · " + (measuresProv.status === "real" ? "live" : "pending")} />}>
            <D3Panel draw={A.charts.drawGap} ctx={ctx} />
          </Panel>
        )}

        {tab === "forest" && <ForestTab granteeId={query.grantee || null} />}
      </div>
    );
  }

  A.views = A.views || {};
  A.views.ExploreView = ExploreView;
})(window.Atlas);
