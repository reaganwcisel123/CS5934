// Trends, two modes: "Forecast" = the NNDSS early-warning board (ported from
// clinic-needs-atlas-early-warning.html); "Chronic history" = the chronic explorer.
(function(A){
  const Icon = A.Icon;
  const { Panel } = A.ui;
  const { API_BASE, authHeaders, fetchGeo } = A.api;
  const { showTT, moveTT, hideTT } = A.tooltip;
  const { navigate } = A.router;

  const fmt = n => n == null ? "—" : (n >= 100 ? Math.round(n).toLocaleString() : n.toFixed(1));

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

  /* ---------------- Forecast mode (early warning, US-048/055/056) --------- */

  /* A forecast anchored to an old week is not current intelligence; say so. */
  function StaleChip({ weeks }){
    if(!weeks) return null;
    return <span className="chip stale">{weeks}w stale</span>;
  }

  // Interval bar: width encodes uncertainty, so a wide band reads as uncertain.
  function IntervalBar({ lower, point, upper, max }){
    if(point == null || !max) return null;
    const pct = v => Math.max(0, Math.min(100, (v / max) * 100));
    const lo = pct(lower ?? point), hi = pct(upper ?? point);
    return (
      <div className="fc-bar" title={`80% interval: ${fmt(lower)} to ${fmt(upper)}`}>
        <div className="band" style={{ left: lo + "%", width: Math.max(1, hi - lo) + "%" }} />
        <div className="pt" style={{ left: pct(point) + "%" }} />
      </div>
    );
  }

  function ConditionRow({ row, max }){
    if(row.status !== "ok"){
      return (
        <div className="fc-row">
          <div className="row-top">
            <span className="row-name">{row.condition}</span>
            <span className="chip none">no forecast</span>
          </div>
          {/* Never rendered as a low number: unknown and quiet are different. */}
          <div className="row-sub unknown">Not enough reporting history to forecast this condition.</div>
        </div>
      );
    }
    return (
      <div className="fc-row">
        <div className="row-top">
          <span className="row-name">{row.condition}</span>
          <StaleChip weeks={row.weeks_stale} />
          <span className="row-val mono">{fmt(row.point)}</span>
        </div>
        <IntervalBar lower={row.lower} point={row.point} upper={row.upper} max={max} />
        <div className="row-sub mono">
          {fmt(row.lower)} – {fmt(row.upper)} expected statewide over the next {row.horizon_weeks} weeks
          {row.as_of_week ? ` · from week ${row.as_of_week}/${row.as_of_year}` : ""}
        </div>
      </div>
    );
  }

  function Sparkline({ points }){
    const values = points.map(p => p.cases).filter(v => v != null);
    if(!values.length) return null;
    const max = Math.max(...values, 1);
    return (
      <div className="spark" title="Reported cases per week, most recent 16 weeks">
        {points.map((p, i) => (
          <i key={i}
             className={p.cases == null ? "gap" : (i === points.length - 1 ? "last" : "")}
             style={{ height: p.cases == null ? "100%" : Math.max(2, (p.cases / max) * 26) + "px" }}
             title={p.cases == null ? `W${p.week}: not reported` : `W${p.week}: ${p.cases}`} />
        ))}
      </div>
    );
  }

  function Corroboration({ threat }){
    const states = threat.neighbor_states || [];
    if(!states.length){
      return <span className="corro solo">Virginia only — not yet seen regionally</span>;
    }
    return (
      <span className="corro">
        Also rising in {states.length === 1 ? states[0] : `${states.length} neighbouring states`}
        {states.length > 1 ? `: ${states.join(", ")}` : ""}
      </span>
    );
  }

  function SupplyTable({ warning }){
    const items = warning.supplies ?? [];
    if(!items.length) return <div className="row-sub unknown">No supply mapping for this condition.</div>;
    return (
      <table className="fc-table">
        <thead><tr><th>Item</th><th style={{ textAlign: "right" }}>Units to hold</th></tr></thead>
        <tbody>
          {items.map(it => (
            <tr key={it.item}>
              <td>{it.item}{it.note ? <div className="muted" style={{ fontSize: 11 }}>{it.note}</div> : null}</td>
              <td className="qty mono">{it.quantity_low ?? "—"} – {it.quantity_high ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  function ThreatCard({ threat, rank, county }){
    const c = threat.county || county;
    return (
      <div className={`threat-card rank-${rank}`}>
        <div className="card-h">
          <span className="name">{threat.condition}</span>
          <span className="mult">{threat.ratio}&times;</span>
        </div>
        <div className="card-sub mono">
          {fmt(threat.recent_weekly_mean)} cases/week now vs {fmt(threat.seasonal_baseline)} normal for{" "}
          {threat.weeks_compared} &middot; {threat.baseline_years}-year seasonal average
        </div>
        <div style={{ marginTop: 7 }}><Corroboration threat={threat} /></div>

        <Sparkline points={threat.recent_series || []} />

        {threat.blurb && <p className="card-blurb">{threat.blurb}</p>}

        {c && c.supplies && c.supplies.length > 0 && (
          <details className="more">
            <summary>
              What to hold in this county
              {c.expected_cases != null && ` (~${c.expected_cases < 1 ? "under 1" : fmt(c.expected_cases)} cases expected over ${c.horizon_weeks} weeks)`}
            </summary>
            <SupplyTable warning={c} />
            <div className="card-sub" style={{ marginTop: 6 }}>
              <span className="chip alloc">allocated, not observed</span>{" "}
              county share of the statewide rate, carried forward {c.horizon_weeks} weeks
            </div>
          </details>
        )}
      </div>
    );
  }

  function ThreatBoard({ state, countyState }){
    if(state.loading) return <div className="row-sub muted">Assessing current threats…</div>;
    if(state.error)   return <div className="err">Could not load threats: {state.error}</div>;

    const threats = state.data?.threats ?? [];
    if(!threats.length) return <div className="row-sub unknown">No conditions are running above their seasonal norm.</div>;

    // Prefer the county-specific payload when a county is selected.
    const byCondition = {};
    (countyState?.data?.threats ?? []).forEach(t => { byCondition[t.condition] = t.county; });

    const review = state.data?.clinical_review;
    const top = threats[0];

    return (
      <React.Fragment>
        <p className="lede">
          <b>{threats.length} conditions</b> are running above their seasonal norm in Virginia.{" "}
          <b>{top.condition}</b> is the furthest out at <b>{top.ratio}&times;</b> its usual level for
          this time of year
          {top.neighbors_rising > 0 && <span> and is rising in {top.neighbors_rising} neighbouring {top.neighbors_rising === 1 ? "state" : "states"}</span>}.
        </p>

        {review && review.clinical_review !== "approved" && (
          <div className="review">
            <span>&#9998;</span>
            <div><b>Stocking guidance is pending clinical review.</b> {review.note}</div>
          </div>
        )}

        <div className="threat-cards">
          {threats.map((t, i) => (
            <ThreatCard key={t.condition} threat={t} rank={i + 1} county={byCondition[t.condition]} />
          ))}
        </div>
      </React.Fragment>
    );
  }

  function StatePanel({ state }){
    if(state.loading) return <div className="panel-body muted">Loading forecasts…</div>;
    if(state.error)   return <div className="err">Could not load forecasts: {state.error}</div>;

    const rows = state.data?.forecasts ?? [];
    const ok = rows.filter(r => r.status === "ok");
    const max = Math.max(1, ...ok.map(r => r.upper ?? r.point ?? 0));
    const sorted = [...ok].sort((a,b) => (b.point ?? 0) - (a.point ?? 0))
      .concat(rows.filter(r => r.status !== "ok"));

    return (
      <div className="panel-body">
        {sorted.map(r => <ConditionRow key={r.condition} row={r} max={max} />)}
      </div>
    );
  }

  // County outlook — driven by the global county context, not its own picker.
  function CountyPanel({ c }){
    const fips = c && c.id;
    const url = API_BASE && fips ? `${API_BASE}/forecast/counties/${fips}` : null;
    const state = useJson(url);
    const warnings = (state.data?.warnings ?? []).slice(0, 4);

    return (
      <div className="panel">
        <div className="panel-h"><h3>County outlook{c ? ` — ${c.name}` : ""}</h3></div>
        <div className="panel-body">
          {!fips && <div className="row-sub muted">Choose a county (top right) to see its allocated share and what to hold.</div>}
          {fips && state.loading && <div className="row-sub muted">Loading…</div>}
          {fips && state.error && <div className="err" style={{ padding: "12px 0" }}>Could not load this county: {state.error}</div>}

          {warnings.map(w => (
            <div className="fc-row" key={w.condition}>
              <div className="row-top">
                <span className="row-name">{w.condition}</span>
                <span className="row-val mono">{fmt(w.point)}</span>
              </div>
              <div className="row-sub mono">
                {fmt(w.lower)} – {fmt(w.upper)} cases · <span className="chip alloc">allocated, not observed</span>
              </div>
              <div style={{ marginTop: 8 }}><SupplyTable warning={w} /></div>
            </div>
          ))}

          {fips && !state.loading && !state.error && !warnings.length &&
            <div className="row-sub unknown">No active warnings for this county.</div>}
        </div>
      </div>
    );
  }

  function ForecastMode({ c }){
    const state = useJson(API_BASE ? `${API_BASE}/forecast` : null);
    const threats = useJson(API_BASE ? `${API_BASE}/threats?top_n=5` : null);
    const countyThreats = useJson(API_BASE && c ? `${API_BASE}/threats/counties/${c.id}?top_n=5` : null);
    const horizon = state.data?.horizon_weeks;
    const asOf = threats.data?.threats?.[0];

    if(!API_BASE) return (
      <div className="disclosure">
        <span>&#9432;</span>
        <div>No live forecast without an API. Append <span className="mono">?api=http://localhost:8010/api</span> to
        this URL, or set <span className="mono">window.CLINIC_ATLAS_API</span> in <span className="mono">config.js</span>.</div>
      </div>
    );

    return (
      <React.Fragment>
        <p className="trends-sub">
          Which notifiable diseases most threaten Virginia clinics right now, and what to hold before demand arrives.
          {asOf && <span className="mono"> Through week {asOf.as_of_week}/{asOf.as_of_year}.</span>}
        </p>

        <ThreatBoard state={threats} countyState={countyThreats} />

        <div className="disclosure">
          <span>&#9888;</span>
          <div>
            <b>County figures are allocated, not measured.</b> CDC NNDSS reports at the state
            level only. County numbers here are Virginia&rsquo;s statewide figure split by county
            population share, so they show relative expected load — not observed local cases.
            Quantities are a planning aid, not a procurement instruction or a clinical protocol.
          </div>
        </div>

        <details className="more">
          <summary>All tracked conditions — {horizon || 4}-week forecast with 80% intervals</summary>
          <div className="ew-grid" style={{ marginTop: 10 }}>
            <div className="panel">
              <div className="panel-h">
                <h3>Statewide forecast</h3>
                <span className="desc">{horizon ? `${horizon}-week lead time · 80% interval` : "80% interval"}</span>
              </div>
              <StatePanel state={state} />
            </div>
            <CountyPanel c={c} />
          </div>
        </details>

        <p className="row-sub muted" style={{ marginTop: 16, maxWidth: 820 }}>
          This informs a stocking decision; it does not make one. A care team is expected to
          review and override these figures. See <a href="#/methods">the model card</a> for how the ranking and the
          forecast are evaluated, and where each is weakest.
        </p>
      </React.Fragment>
    );
  }

  /* ---------------- Chronic history mode (teammate-built explorer) --------- */

  const MIN_YEAR = 2016;
  const CURRENT_YEAR = new Date().getFullYear();
  const CONDITIONS = [
    "All Chronic Conditions", "Alzheimer's Disease", "Arthritis", "Asthma",
    "Cardiovascular Disease", "Chronic Kidney Disease", "Chronic Obstructive Pulmonary Disease",
    "Dementia (Non-Alzheimer's)", "Diabetes", "High Blood Cholesterol", "Hypertension",
    "Ischemic Heart Disease", "Stroke",
  ];

  function normalizeCountyName(value){
    return String(value || "").trim().toLowerCase()
      .replace(/\b(county|city)\b/g, "").replace(/[^a-z0-9]+/g, " ").trim();
  }

  function normalizeConditionRows(rawData){
    const rows = Array.isArray(rawData?.rows) ? rawData.rows : Array.isArray(rawData) ? rawData : [];
    return rows
      .map(row => ({
        year: Number(row.year ?? row.Year ?? row.year_num),
        county: String(row.county ?? row.county_name ?? row.location ?? "").trim(),
        countyFips: row.county_fips ?? row.fips ?? row.countyFips ?? null,
        condition: String(row.condition ?? row.disease ?? row.metric ?? row.measure ?? "").trim(),
        cases: Number(row.cases ?? row.case_count ?? row.count ?? row.value ?? 0),
        rate: Number(row.rate ?? row.prevalence ?? row.value ?? 0),
      }))
      .filter(row => Number.isFinite(row.year) && row.county && row.condition);
  }

  function toggleConditionSelection(selectedConditions, condition, allConditions){
    if(condition === "All Chronic Conditions"){
      if(selectedConditions.length === allConditions.length) return [];
      return [...allConditions];
    }
    let newSelected = selectedConditions.filter(item => item !== condition);
    if(selectedConditions.includes(condition)){
      newSelected = newSelected.filter(item => item !== "All Chronic Conditions");
      return newSelected;
    }
    newSelected = [...selectedConditions, condition];
    const individual = allConditions.filter(item => item !== "All Chronic Conditions");
    if(individual.every(item => newSelected.includes(item))) newSelected.push("All Chronic Conditions");
    return newSelected;
  }

  function buildCountyConditionLookup(rows, { startYear, endYear, conditions }){
    const includesAll = (conditions || []).includes("All Chronic Conditions");
    const active = includesAll ? null : (conditions || []).filter(c => c !== "All Chronic Conditions");
    const grouped = {};
    const values = [];
    rows
      .filter(row => row.year >= startYear && row.year <= endYear && (!active || active.includes(row.condition)))
      .forEach(row => {
        const key = row.countyFips ? `fips:${row.countyFips}` : `name:${normalizeCountyName(row.county)}`;
        if(!grouped[key]) grouped[key] = { county: row.county, countyFips: row.countyFips, values: [] };
        grouped[key].values.push(row);
      });
    Object.values(grouped).forEach(entry => {
      const value = d3.mean(entry.values, item => item.rate ?? item.cases ?? 0);
      entry.value = Number.isFinite(value) ? value : null;
      if(entry.value !== null) values.push(entry.value);
    });
    return { lookup: grouped, maxValue: values.length ? d3.max(values) : 0 };
  }

  // Committed geojson features carry county_fips (not fips) — adapt here.
  function getCountyConditionValue(feature, dataSummary){
    if(!dataSummary || !feature?.properties) return null;
    const props = feature.properties;
    const fips = props.county_fips || props.fips;
    const fipsKey = fips ? `fips:${fips}` : null;
    const nameKey = props.name ? `name:${normalizeCountyName(props.name)}` : null;
    if(fipsKey && dataSummary.lookup[fipsKey]) return dataSummary.lookup[fipsKey].value;
    if(nameKey && dataSummary.lookup[nameKey]) return dataSummary.lookup[nameKey].value;
    if(props.name){
      const fallbackKey = Object.keys(dataSummary.lookup).find(key => key.startsWith("name:") && key.replace("name:", "") === normalizeCountyName(props.name));
      if(fallbackKey) return dataSummary.lookup[fallbackKey].value;
    }
    return null;
  }

  function getCountyFillColor(feature, dataSummary, ramp){
    if(!dataSummary) return "var(--surface-sunken)";
    const value = getCountyConditionValue(feature, dataSummary);
    if(value == null || !Number.isFinite(value)) return "var(--surface-sunken)";
    const ratio = dataSummary.maxValue > 0 ? Math.max(0.15, Math.min(1, value / dataSummary.maxValue)) : 0.15;
    return ramp(ratio);
  }

  function ChronicLegend({ startYear, endYear, onStartYear, onEndYear, conditions, onConditions }){
    const toggle = condition => onConditions(toggleConditionSelection(conditions, condition, CONDITIONS));
    const handleStart = value => {
      const s = Number(value);
      onStartYear(s); if(s > endYear) onEndYear(s);
    };
    const handleEnd = value => {
      const e2 = Number(value);
      onEndYear(e2); if(e2 < startYear) onStartYear(e2);
    };
    return (
      <div>
        <div className="leg-sect">
          <h4>Date range filter</h4>
          <div className="year-filter">
            <div className="year-head"><span>Start year</span><strong>{startYear}</strong></div>
            <input type="range" min={MIN_YEAR} max={CURRENT_YEAR} value={startYear} onChange={e => handleStart(e.target.value)} />
            <div className="year-head"><span>End year</span><strong>{endYear}</strong></div>
            <input type="range" min={MIN_YEAR} max={CURRENT_YEAR} value={endYear} onChange={e => handleEnd(e.target.value)} />
            <div className="year-hint">Filters county-level records between the selected start and end years.</div>
          </div>
        </div>
        <div className="leg-sect">
          <h4>Chronic conditions</h4>
          {CONDITIONS.map(condition => (
            <label key={condition} className="leg-row" style={{ cursor: "pointer" }}>
              <input type="checkbox" checked={conditions.includes(condition)} onChange={() => toggle(condition)} />
              <span>{condition}</span>
            </label>
          ))}
          <div className="leg-note">Select one or more conditions to display on the map.</div>
        </div>
      </div>
    );
  }

  function ChronicSelected({ feature, onClear, rows, startYear, endYear, conditions }){
    if(!feature) return (
      <div className="panel-body">
        <p className="hint">Hover a county to preview it, or click one to pin its details here.</p>
      </div>
    );
    const p = feature.properties;
    const fips = p.county_fips || p.fips;
    const matches = rows.filter(row => {
      const sameCounty =
        (fips && String(row.countyFips) === String(fips)) ||
        normalizeCountyName(row.county) === normalizeCountyName(p.name);
      const matchesYear = Number.isFinite(row.year) && row.year >= startYear && row.year <= endYear;
      const includesAll = conditions.includes("All Chronic Conditions");
      const matchesCondition = includesAll || conditions.includes(row.condition);
      return sameCounty && matchesYear && matchesCondition;
    });
    return (
      <div className="panel-body">
        <div className="kv">
          <div><div className="k">County</div><div className="v">{p.name}</div></div>
          <div><div className="k">FIPS</div><div className="v mono">{fips}</div></div>
          <div><div className="k">Matches</div><div className="v">{matches.length}</div></div>
        </div>
        <p className="hint" style={{ marginTop: 10 }}>
          Showing mock condition data from <strong>{startYear}</strong> through <strong>{endYear}</strong> for <span className="mono">{fips}</span>.
        </p>
        {matches.length > 0 ? (
          <div className="hint chronic-cards">
            {matches.slice(0, 8).map((row, index) => (
              <div key={`${row.condition}-${row.year}-${index}`} className="chronic-card">
                <div><strong>{row.condition}</strong></div>
                <div>Year: {row.year}</div>
                <div>Hospitalization count: {row.cases}</div>
                <div>age-adjusted rate per 100,000: {row.rate}</div>
              </div>
            ))}
          </div>
        ) : (
          <p className="hint" style={{ marginTop: 10 }}>No mock condition rows matched the selected year range and condition filters for this county.</p>
        )}
        <button className="backbtn" style={{ marginTop: 8 }} onClick={onClear}>Clear selection</button>
      </div>
    );
  }

  function ChronicMode(){
    const [geo, setGeo] = React.useState(null);
    const [conditionData, setConditionData] = React.useState(null);
    const [err, setErr] = React.useState(null);
    const [selected, setSelected] = React.useState(null);
    const [startYear, setStartYear] = React.useState(MIN_YEAR);
    const [endYear, setEndYear] = React.useState(CURRENT_YEAR);
    const [conditions, setConditions] = React.useState(["All Chronic Conditions"]);
    const mapRef = React.useRef(null);
    const apiRef = React.useRef(null);

    React.useEffect(() => {
      fetchGeo().then(setGeo).catch(e => setErr("Could not load county geometry (" + e.message + ")."));
      fetch("data/mock_chronic_conditions.json")
        .then(r => { if(!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
        .then(setConditionData)
        .catch(() => setConditionData(null));
    }, []);

    const rows = React.useMemo(() => normalizeConditionRows(conditionData), [conditionData]);
    const summary = React.useMemo(() => buildCountyConditionLookup(rows, { startYear, endYear, conditions }), [rows, startYear, endYear, conditions]);

    const optsOf = () => ({
      ariaLabel: "Choropleth of Virginia counties by chronic-condition rate.",
      fill: f => getCountyFillColor(f, summary, d3.interpolateReds),
      tip: f => {
        const value = getCountyConditionValue(f, summary);
        const valueText = value == null ? "No matching condition data" : `${value.toFixed(1)} age-adjusted rate`;
        return `<b>${f.properties.name}</b><br><span class="src">${valueText} · FIPS ${f.properties.county_fips || f.properties.fips}</span>`;
      },
      onClick: f => setSelected(f),
    });

    // build once; repaint on filter changes (zoom survives)
    React.useEffect(() => {
      if(geo && mapRef.current && !apiRef.current)
        apiRef.current = A.charts.buildChoropleth(mapRef.current, geo, { ...optsOf(), zoomable: true });
    }, [geo]);
    React.useEffect(() => { if(apiRef.current) apiRef.current.update(optsOf()); }, [summary]);

    if(err) return <div className="empty">{err}</div>;

    return (
      <React.Fragment>
        <p className="trends-sub">Explore county-level prevalence of chronic diseases across Virginia. Filter by year
          and condition to identify geographic trends. <span className="chronic-mock">Mock data — 33 of 133 counties.</span></p>
        <div className="chronic-grid">
          <section className="panel">
            <div className="panel-h">
              <h3>Virginia counties</h3>
              <span className="desc">{geo ? `${geo.features.length} counties` : "loading…"}</span>
              <button className="toolbtn" style={{ marginLeft: 10 }} onClick={() => apiRef.current && apiRef.current.reset()}>Reset view</button>
            </div>
            <div className="panel-body" style={{ padding: 8 }}>
              {!geo && <div className="empty">Loading Virginia counties…</div>}
              <div ref={mapRef} className="mapholder" style={{ display: geo ? "block" : "none" }} />
            </div>
          </section>
          <aside className="side-col">
            <div className="panel">
              <div className="panel-h"><h3>Legend</h3><span className="desc">year + conditions</span></div>
              <div className="panel-body" style={{ paddingTop: 4 }}>
                <ChronicLegend startYear={startYear} endYear={endYear} onStartYear={setStartYear} onEndYear={setEndYear}
                  conditions={conditions} onConditions={setConditions} />
              </div>
            </div>
          </aside>
        </div>
        <div className="details-row">
          <div className="panel">
            <div className="panel-h"><h3>{selected ? "Selected county" : "County preview"}</h3></div>
            <ChronicSelected feature={selected} onClear={() => setSelected(null)} rows={rows}
              startYear={startYear} endYear={endYear} conditions={conditions} />
          </div>
        </div>
      </React.Fragment>
    );
  }

  /* ---------------- The view ---------------------------------------------- */

  function TrendsView({ c, mode }){
    const setMode = m => navigate("/trends" + (c ? "/" + c.id : ""), { query: { mode: m }, replace: true });
    return (
      <div className="content trends-forecast">
        <div className="page-head trends-head">
          <div>
            <h1>{mode === "chronic" ? "Chronic disease history" : "Early warning"}</h1>
          </div>
          <div className="seg" role="tablist" aria-label="Trends mode">
            <button role="tab" aria-selected={mode !== "chronic"} className={mode !== "chronic" ? "on" : ""} onClick={() => setMode("forecast")}>Forecast</button>
            <button role="tab" aria-selected={mode === "chronic"} className={mode === "chronic" ? "on" : ""} onClick={() => setMode("chronic")}>Chronic history</button>
          </div>
        </div>
        {mode === "chronic" ? <ChronicMode /> : <ForecastMode c={c} />}
      </div>
    );
  }

  A.views = A.views || {};
  A.views.TrendsView = TrendsView;
})(window.Atlas);
