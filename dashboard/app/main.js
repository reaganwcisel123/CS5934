// App entry: auth gate -> data load -> shell (top bar + breadcrumb) -> routed view.
(function(A){
  const { useRoute, navigate } = A.router;
  const { useStore, load, rememberFips, defaultFips, byId, baselineFor } = A.store;
  const { API_BASE, AUTH_ON, setToken, postEvent } = A.api;
  const { TopBar, CrumbBar } = A.shell;
  const { ErrorBoundary } = A.ui;
  const { fmt0 } = A.format;

  const VIEWS = new Set(["overview", "forest", "county", "worklist", "trends", "explore", "methods", "funding"]);

  function crumbsFor(route, c, countyCount){
    const va = { label: `Virginia (${countyCount})`, href: "#/overview" };
    switch(route.view){
      case "county":
        return c ? [va, { label: `${c.name} · ${fmt0(c.needIndex)}/100` }] : [va];
      case "worklist": {
        const n = c ? (c.patientsList || []).filter(p => p.risk != null).length : 0;
        return c ? [va, { label: c.name, href: "#/county/" + c.id }, { label: `Worklist (${n} to review)` }] : [va];
      }
      case "forest":  return [va, { label: "Needs Forest" }];
      case "trends":  return [va, { label: route.query.mode === "chronic" ? "Trends · Chronic history" : "Trends · Early warning" }];
      case "explore": return [va, { label: "Explore" }];
      case "methods": return [va, { label: "Methods & data" }];
      case "funding": return [va, { label: "Funding Matches" }];
      default:        return [va];
    }
  }

  function chatContextFor(route, c, records){
    const top = records.length ? records.reduce((a, b) => ((b.needIndex ?? 0) > (a.needIndex ?? 0) ? b : a), records[0]) : null;
    switch(route.view){
      case "overview": return { sub: "Virginia", starters: [top ? `Why is ${top.name} ranked first?` : "Which county has the most need?", "What goes into the unmet-need index?"] };
      case "forest":   return { sub: "the needs forest", starters: ["What does petal length mean?", "Which county has the biggest bloom?"] };
      case "trends":   return { sub: "the forecast", starters: ["What does 'allocated, not observed' mean?", "Which condition is most above normal right now?"] };
      case "worklist": return { sub: c ? c.name : "the worklist", starters: ["Why are these patients ranked first?", "What does a provider do with an override?"] };
      case "methods":  return { sub: "the methods", starters: ["What does 'pending' mean on a badge?", "How are the forecast intervals built?"] };
      case "funding":  return { sub: "funding matches", starters: ["How are funding matches ranked?", "What should a clinic verify before applying?"] };
      default:         return { sub: c ? c.name : "Virginia", starters: ["Why is this county high-need?", "What is driving the top need domain?"] };
    }
  }

  function App(){
    const route = useRoute();
    const state = useStore();
    const { records, provenance, err, token } = state;

    // Load data once we're allowed to (auth gate first in auth mode).
    React.useEffect(() => {
      if(AUTH_ON && !token) return;
      load();
    }, [token]);

    // Default route.
    React.useEffect(() => {
      if(!VIEWS.has(route.view)) navigate("/overview", { replace: true });
    }, [route.view]);

    // Resolve the county for county-scoped routes; keep the context sticky.
    const urlFips = route.segs[1] || null;
    const needsFips = route.view === "county" || route.view === "worklist";
    const c = byId(urlFips) || null;

    React.useEffect(() => {
      if(!records.length) return;
      if(needsFips && !c){
        const fallback = defaultFips();
        if(fallback) navigate("/" + route.view + "/" + fallback, { replace: true });
        return;
      }
      if(c) rememberFips(c.id);
    }, [records, route.view, urlFips]);

    // Usage-event audit trail: log county views (authenticated mode only).
    React.useEffect(() => {
      if(route.view === "county" && c) postEvent("county_view", c.id);
    }, [route.view, c && c.id]);

    // Each view is its own page: reset scroll on navigation.
    React.useEffect(() => { window.scrollTo(0, 0); }, [route.view, urlFips, route.query.tab, route.query.mode]);

    if(AUTH_ON && !token){
      return <A.Login onAuth={t => { setToken(t); A.store.set({ token: t }); }} />;
    }
    if(err) return <div className="empty">{err}</div>;
    if(!records.length) return <div className="empty">Loading…</div>;
    if(needsFips && !c) return <div className="empty">Loading…</div>;

    const baselineMode = route.query.baseline === "region" ? "region" : "va";
    const setBaseline = m => navigate(route.path, { query: { ...route.query, baseline: m === "va" ? "" : m }, replace: true });
    const baseline = c ? baselineFor(c, baselineMode) : null;
    const showBaseline = route.view === "county" || route.view === "explore";

    // The county context shown in the chip: the URL's county, else the last one.
    const chipFips = (c && c.id) || (byId(state.lastFips) && state.lastFips) || null;
    const chipC = byId(chipFips);

    let view = null;
    if(route.view === "overview") view = <A.views.OverviewView records={records} provenance={provenance} />;
    else if(route.view === "forest") view = <A.views.ForestView records={records} provenance={provenance} />;
    else if(route.view === "county") view = <A.views.CountyView c={c} baseline={baseline} provenance={provenance} />;
    else if(route.view === "worklist") view = <A.views.WorklistView c={c} records={records} />;
    else if(route.view === "trends") view = <A.views.TrendsView c={byId(urlFips) || chipC || null} mode={route.query.mode === "chronic" ? "chronic" : "forecast"} />;
    else if(route.view === "explore") view = <A.views.ExploreView records={records} fips={chipFips || defaultFips()} baselineMode={baselineMode}
      provenance={provenance} query={route.query} />;
    else if(route.view === "methods") view = <A.views.MethodsView provenance={provenance} />;
    else if(route.view === "funding") view = <A.views.FundingMatchesView records={records} initialFips={chipFips || defaultFips()} />;

    const signOut = () => { setToken(""); A.store.set({ token: "" }); };
    const chatCtx = chatContextFor(route, chipC, records);

    return (
      <React.Fragment>
        <TopBar records={records} fips={chipFips} authOn={AUTH_ON} onSignOut={signOut} />
        <CrumbBar crumbs={crumbsFor(route, c || chipC, records.length)}
          baseline={showBaseline ? baselineMode : null}
          onBaseline={showBaseline ? setBaseline : null} />
        <main className="main">
          <ErrorBoundary resetKey={route.path}>{view}</ErrorBoundary>
        </main>
        {API_BASE && <A.ChatWidget countyId={chipFips} countyName={chipC ? chipC.name : "Virginia"} context={chatCtx} />}
      </React.Fragment>
    );
  }

  ReactDOM.createRoot(document.getElementById("root")).render(<App />);
})(window.Atlas);
