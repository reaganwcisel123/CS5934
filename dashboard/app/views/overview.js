// Overview (WHERE, default route): statewide choropleth with outcome lenses,
// ranked top-need counties, KPI band, provenance strip, journey strip.
(function(A){
  const Icon = A.Icon;
  const { OUTCOMES } = A.domain;
  const { fmt0, fmt1, fmtC } = A.format;
  const { navigate } = A.router;
  const { Panel, StatCard, Provenance } = A.ui;
  const { fetchGeo } = A.api;
  const { seqNeed } = A.theme;

  const LENSES = [
    { key: "need", label: "Need index", get: c => c.needIndex, max: () => 100, unit: "/100", src: "composite" },
    ...OUTCOMES.map(O => ({
      key: O.key, label: O.short, get: c => c.outcomes[O.key],
      max: records => d3.max(records, c => c.outcomes[O.key]) || 1, unit: "%", src: "CDC PLACES",
    })),
  ];

  // Teaches the flow by being the flow. Collapses after the first county visit.
  function JourneyStrip({ records }){
    const [collapsed, setCollapsed] = React.useState(() => {
      try { return localStorage.getItem("atlas_journey_collapsed") === "1"; } catch(e){ return false; }
    });
    const set = v => { setCollapsed(v); try { localStorage.setItem("atlas_journey_collapsed", v ? "1" : "0"); } catch(e){} };
    const top = records.reduce((a, b) => ((b.needIndex ?? 0) > (a.needIndex ?? 0) ? b : a), records[0]);
    if(collapsed) return (
      <button className="journey-mini" onClick={() => set(false)}>
        <span className="mono">01</span> Where → <span className="mono">02</span> Who & why → <span className="mono">03</span> What next
        <Icon name="chevron-down" size={13} />
      </button>
    );
    const steps = [
      { n: "01", t: "Where", d: "The map below ranks all 133 counties by unmet need.", act: null },
      { n: "02", t: "Who & why", d: "Open a county for its model risk and the drivers behind it.", act: () => navigate("/county/" + top.id) },
      { n: "03", t: "What next", d: "Get the ranked outreach worklist with a next step per patient.", act: () => navigate("/worklist/" + top.id) },
    ];
    return (
      <div className="journey" role="note" aria-label="How this app flows">
        {steps.map((s, i) => (
          <div key={i} className={"journey-step" + (s.act ? " click" : "")} onClick={s.act || undefined}>
            <span className="jn mono">{s.n}</span>
            <div><b>{s.t}</b><p>{s.d}</p></div>
          </div>
        ))}
        <button className="journey-x" onClick={() => set(true)} aria-label="Collapse the guide">✕</button>
      </div>
    );
  }

  function OverviewMap({ records, lens, hoverId, onHover }){
    const ref = React.useRef(null);
    const apiRef = React.useRef(null);
    const [geo, setGeo] = React.useState(null);
    const [geoErr, setGeoErr] = React.useState(null);
    React.useEffect(() => { fetchGeo().then(setGeo).catch(e => setGeoErr(e.message)); }, []);

    const byFips = React.useMemo(() => Object.fromEntries(records.map(c => [c.id, c])), [records]);
    const L = LENSES.find(l => l.key === lens) || LENSES[0];
    const maxV = L.max(records);

    const optsOf = () => ({
      ariaLabel: "Choropleth of Virginia counties by " + L.label + ". Darker means higher.",
      fill: f => {
        const c = byFips[f.properties.county_fips];
        const v = c ? L.get(c) : null;
        return v == null ? "var(--surface-sunken)" : seqNeed(Math.max(0.04, v / maxV));
      },
      tip: f => {
        const c = byFips[f.properties.county_fips];
        if(!c) return `<b>${f.properties.name}</b><br><span class="src">no data</span>`;
        const v = L.get(c);
        return `<b>${c.name}</b> · ${c.region}<br>${L.label}: <b>${v != null ? (L.key === "need" ? fmt0(v) : fmt1(v) + "%") : "—"}</b>` +
          `<br>need ${fmt0(c.needIndex)}/100 · HPSA ${c.hpsaScore}/26<br><span class="src">click to open the county</span>`;
      },
      onClick: f => {
        const c = byFips[f.properties.county_fips];
        if(c){ A.store.rememberFips(c.id); navigate("/county/" + c.id); }
      },
      onHover: f => onHover(f ? f.properties.county_fips : null),
      selectedFips: hoverId,
    });

    React.useEffect(() => {
      if(geo && ref.current && !apiRef.current)
        apiRef.current = A.charts.buildChoropleth(ref.current, geo, optsOf());
    }, [geo]);
    React.useEffect(() => {
      if(apiRef.current) apiRef.current.update(optsOf());
    }, [records, lens, hoverId]);

    if(geoErr) return <div className="empty">Could not load data/va-counties.geojson ({geoErr}).</div>;
    if(!geo) return <div className="empty">Loading the map…</div>;
    return <div ref={ref} className="mapholder" />;
  }

  function OverviewView({ records, provenance }){
    const [lens, setLens] = React.useState("need");
    const [hoverId, setHoverId] = React.useState(null);
    const ranked = records.slice().sort((a, b) => (b.needIndex ?? 0) - (a.needIndex ?? 0));
    const top = ranked[0];
    const median = d3.median(records, c => c.needIndex);
    const shortage = records.filter(c => (c.hpsaScore ?? 0) > 0).length;
    const L = LENSES.find(l => l.key === lens) || LENSES[0];

    return (
      <div className="content">
        <JourneyStrip records={records} />
        <div className="page-head">
          <h1>Where Virginia needs help first</h1>
          <p>Every county in Virginia, ranked by preventable health need — six federal data sources joined into one unmet-need index across all <b>133 counties and independent cities</b>. Darker means more unmet need.</p>
        </div>

        <div className="stat-grid">
          <div className="stat-cell" title="All 133 Virginia counties and independent cities carry a score.">
            <StatCard label="Counties covered" value="133" unit="/133" accent="signal" icon={<Icon name="map" size={18} />} />
          </div>
          <div className="stat-cell" title="The county with the highest unmet-need index right now.">
            <StatCard label={"Highest need · " + (top ? top.name : "—")} value={top ? fmt0(top.needIndex) : "—"} unit="/100" accent="command" icon={<Icon name="alert-triangle" size={18} />} />
          </div>
          <div className="stat-cell" title="Median unmet-need index statewide.">
            <StatCard label="Median need" value={median != null ? fmt0(median) : "—"} unit="/100" accent="signal" icon={<Icon name="gauge" size={18} />} />
          </div>
          <div className="stat-cell" title="Counties carrying a HRSA primary-care shortage designation.">
            <StatCard label="Shortage-area counties" value={String(shortage)} accent="signal" icon={<Icon name="map-pin" size={18} />} />
          </div>
        </div>

        <div className="overview-grid">
          <Panel icon="map" title="Unmet-need across the Commonwealth" desc="click a county to open it">
            <div className="lens-row" role="tablist" aria-label="Map lens">
              {LENSES.map(l => (
                <button key={l.key} role="tab" aria-selected={lens === l.key}
                  className={"lens" + (lens === l.key ? " on" : "")} onClick={() => setLens(l.key)}>{l.label}</button>
              ))}
            </div>
            <OverviewMap records={records} lens={lens} hoverId={hoverId} onHover={setHoverId} />
            <div className="maplegend">
              <span className="mono">low</span><span className="ramp" /><span className="mono">high</span>
              <span className="maplegend-note">{L.label}{L.unit} · {L.src}{lens !== "need" ? " · real data, all 133 counties" : ""}</span>
            </div>
          </Panel>

          <Panel icon="alert-triangle" title="Top need — act here first" desc="click to open the county">
            <ol className="rank-list">
              {ranked.slice(0, 12).map((c, i) => (
                <li key={c.id} className={"rank-row" + (hoverId === c.id ? " hl" : "")}
                  onMouseEnter={() => setHoverId(c.id)} onMouseLeave={() => setHoverId(null)}
                  onClick={() => { A.store.rememberFips(c.id); navigate("/county/" + c.id); }}
                  tabIndex={0} role="button"
                  onKeyDown={e => { if(e.key === "Enter" || e.key === " "){ e.preventDefault(); navigate("/county/" + c.id); } }}>
                  <span className="rank mono">{i + 1}</span>
                  <span className="rk-name">{c.name}<small>{c.region} · HPSA {c.hpsaScore}/26</small></span>
                  <span className="rk-score mono">{fmt0(c.needIndex)}</span>
                </li>
              ))}
            </ol>
            <div className="rank-note">Selecting a county carries it to every view — profile, worklist, trends.</div>
          </Panel>
        </div>

        <div className="legend-row">
          <Provenance provenance={provenance} />
          <a className="methods-link" href="#/methods">About this data →</a>
        </div>
      </div>
    );
  }

  A.views = A.views || {};
  A.views.OverviewView = OverviewView;
})(window.Atlas);
