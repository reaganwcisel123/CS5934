// Funding Matches is isolated from the Atlas's other views and uses one shared
// county x lookback x filters result set for cards, metrics, and detail state.
(function(A){
  const { Panel, StatCard } = A.ui;
  const { CountyCombobox } = A.shell;
  const { fetchGrantFundingMatches } = A.api;
  const State = A.fundingState;
  const EMPTY_FILTERS = { agency:"", tier:"", deadline:"", eligibility:"", category:"" };

  const textOr = (value, fallback = "Not provided") => value == null || value === "" ? fallback : value;
  const money = value => value == null ? "Not provided" : new Intl.NumberFormat("en-US", { style:"currency", currency:"USD", maximumFractionDigits:0 }).format(value);
  const dateLabel = value => {
    if(!value) return "Not provided";
    const parsed = new Date(value + "T12:00:00Z");
    return Number.isNaN(parsed.getTime()) ? value : new Intl.DateTimeFormat("en-US", { month:"short", day:"numeric", year:"numeric", timeZone:"UTC" }).format(parsed);
  };
  const awardRange = opportunity => opportunity.awardFloor != null && opportunity.awardCeiling != null
    ? `${money(opportunity.awardFloor)} to ${money(opportunity.awardCeiling)}`
    : opportunity.awardFloor != null ? `From ${money(opportunity.awardFloor)}`
    : opportunity.awardCeiling != null ? `Up to ${money(opportunity.awardCeiling)}` : "Not provided";
  const scoreLabel = score => `${Math.round((score || 0) * 100)}%`;

  function MetricGrid({ values }){
    return <div className="stat-grid" aria-label="Funding-match summary metrics">
      <StatCard label="Available opportunities" value={String(values.availableCount)} accent="command" />
      <StatCard label="County recommendations" value={String(values.recommendationCount)} />
      <StatCard label="Strong relevance" value={String(values.strongCount)} accent="command" />
      <StatCard label="Nearest deadline" value={dateLabel(values.nearestDeadline)} />
    </div>;
  }

  function FundingCard({ row, selected, onSelect }){
    const { match, opportunity } = row;
    return <article className={"fm-card" + (selected ? " selected" : "")}>
      <button className="fm-card-main" onClick={onSelect} aria-expanded={selected} aria-label={`Show details for ${opportunity.title}`}>
        <div className="fm-card-top"><span className="fm-card-title">{textOr(opportunity.title)}</span><span className="fm-score mono">{scoreLabel(match.matchScore)}</span></div>
        <div className="fm-agency">{textOr(opportunity.agency)} · {textOr(opportunity.opportunityNumber)}</div>
        <div className="fm-badges">
          <span className={"fm-badge" + (match.matchTier === "Strong relevance" ? " strong" : "")}>{textOr(match.matchTier)}</span>
          <span className={"fm-badge" + (match.eligibilityStatus === "Needs verification" ? " verify" : "")}>{textOr(match.eligibilityStatus, "Needs verification")}</span>
          <span className="fm-badge">Deadline: {opportunity.closingDate ? dateLabel(opportunity.closingDate) : textOr(match.deadlineStatus)}</span>
          <span className="fm-badge">Award: {awardRange(opportunity)}</span>
        </div>
        <ul className="fm-reasons">{(match.fitReasons || []).slice(0, 3).map((reason, index) => <li key={index}>{reason}</li>)}</ul>
      </button>
      <a className="fm-source" href={opportunity.officialUrl} target="_blank" rel="noopener noreferrer">View official record <span aria-hidden="true">open</span></a>
    </article>;
  }

  function FundingDetail({ row }){
    if(!row) return <Panel icon="layers" title="Opportunity details"><p className="hint">Select a recommendation to review its deadline, eligibility screen, score breakdown, and application-readiness prompts.</p></Panel>;
    const { opportunity, match } = row;
    const items = [
      ["Opportunity number", opportunity.opportunityNumber], ["Agency", opportunity.agency], ["Status", opportunity.status], ["Posted", dateLabel(opportunity.postingDate)],
      ["Deadline", opportunity.closingDate ? dateLabel(opportunity.closingDate) : match.deadlineStatus], ["Award range", awardRange(opportunity)],
      ["Cost sharing", opportunity.costSharingRequired === true ? "Listed as required" : opportunity.costSharingRequired === false ? "Not listed as required" : "Not provided"],
      ["Applicant types", (opportunity.applicantTypes || []).join(", ")], ["Categories", (opportunity.fundingCategories || []).join(", ")],
      ["Eligibility screen", textOr(match.eligibilityStatus, "Needs verification")],
    ];
    return <Panel icon="layers" title="Opportunity details" desc={scoreLabel(match.matchScore) + " match score"} bodyClass="fm-detail">
      <h4>{textOr(opportunity.title)}</h4><p className="fm-detail-copy">{textOr(opportunity.synopsis, "No short synopsis was provided in the indexed record.")}</p>
      <div className="fm-detail-grid">{items.map(([label, value]) => <div className="fm-detail-item" key={label}><span>{label}</span><b>{textOr(value)}</b></div>)}</div>
      <h4 style={{ marginTop:16 }}>Match-score breakdown</h4><ul className="fm-breakdown"><li>Gemini relevance: {scoreLabel(match.geminiScore)}</li><li>Structured compatibility: {scoreLabel(match.eligibilityScore)}</li><li>Deadline usability: {scoreLabel(match.deadlineScore)}</li></ul>
      <p className="fm-warning"><b>Eligibility screen:</b> {textOr(match.eligibilityScreenReason, "Needs verification against the official opportunity record.")}</p>
      <h4 style={{ marginTop:16 }}>Application-readiness prompts</h4><ul className="fm-checklist">{(match.readinessChecklist || []).map((item, index) => <li key={index}>{item}</li>)}</ul>
      <a className="fm-source" href={opportunity.officialUrl} target="_blank" rel="noopener noreferrer">Open official Grants.gov record <span aria-hidden="true">open</span></a>
    </Panel>;
  }

  function FundingMatchesView({ records, initialFips }){
    const [artifact, setArtifact] = React.useState(null);
    const [error, setError] = React.useState("");
    const [selectedFips, setSelectedFips] = React.useState(initialFips);
    const [lookbackDays, setLookbackDays] = React.useState(30);
    const [selectedId, setSelectedId] = React.useState(null);
    const [sort, setSort] = React.useState("score");
    const [filters, setFilters] = React.useState(EMPTY_FILTERS);
    const [visibleCount, setVisibleCount] = React.useState(10);

    React.useEffect(() => {
      let active = true;
      fetchGrantFundingMatches().then(data => {
        if(!data || !data.metadata || !data.opportunities || !data.profiles || !data.matchesByCounty) throw new Error("The grant artifact schema is incomplete.");
        if(active) { setArtifact(data); setError(""); }
      }).catch(() => { if(active) setError("Funding Matches is not available yet. Run the grant recommendation pipeline to generate the optional artifact."); });
      return () => { active = false; };
    }, []);
    React.useEffect(() => {
      if(initialFips && initialFips !== selectedFips) {
        setSelectedFips(initialFips); setSelectedId(null); setFilters(EMPTY_FILTERS); setVisibleCount(10);
      }
    }, [initialFips]);

    if(error) return <div className="content funding-matches"><div className="empty">{error}</div></div>;
    if(!artifact) return <div className="content funding-matches"><div className="empty">Loading current funding opportunities...</div></div>;
    const profile = artifact.profiles[selectedFips];
    if(!profile) return <div className="content funding-matches"><div className="empty">No county-informed planning profile is available for this locality.</div></div>;

    const today = State.dayKey(new Date());
    const available = State.availableOpportunities(artifact, lookbackDays, today);
    const countyWindowRows = State.countyRows(artifact, selectedFips, lookbackDays, today);
    const options = {
      agencies: [...new Set(countyWindowRows.map(row => row.opportunity.agency).filter(Boolean))].sort(),
      categories: [...new Set(countyWindowRows.flatMap(row => row.opportunity.fundingCategories || []))].sort(),
    };
    const rows = State.sortedRows(State.filteredRows(countyWindowRows, filters), sort);
    const selected = rows.find(row => row.match.opportunityId === selectedId) || rows[0] || null;
    const values = State.metrics(available, rows);
    const resetScopedState = () => { setSelectedId(null); setFilters(EMPTY_FILTERS); setVisibleCount(10); };
    const setFilter = (key, value) => { setFilters(current => ({ ...current, [key]: value })); setSelectedId(null); setVisibleCount(10); };
    const metadata = artifact.metadata || {};
    const artifactHealth = State.artifactHealth(artifact, today);
    const refreshReason = artifactHealth.legacy ? "This snapshot uses a retired ranking model." : "This snapshot is more than two days old.";

    return <div className="content funding-matches" data-county-fips={selectedFips} data-lookback-days={lookbackDays}>
      <div className="page-head"><h1>Rural Clinic Funding Opportunities</h1><p>Funding Matches ranks current official grant opportunities against a county-informed rural clinic planning profile.</p></div>
      <div className="fm-intro"><div><b>Planning support, not an award prediction.</b><p>Eligibility must be independently verified, opportunity details can change, and no patient information is used.</p></div><span className="pill" style={{ borderColor:"var(--brand)", color:"var(--brand)" }}>Grants.gov public source</span></div>
      {artifactHealth.needsRefresh && <div className="fm-refresh-warning" role="status"><b>Recommendations need refresh.</b><span>{refreshReason} Results may be incomplete until a current Gemini-ranked snapshot is published.</span></div>}
      <Panel icon="map" title="County-informed clinic planning profile" desc="Public county indicators; not a confirmed clinic strategy">
        <div className="fm-context"><div><CountyCombobox records={records} selectedId={selectedFips} onSelect={id => { setSelectedFips(id); resetScopedState(); }} /><div className="fm-meta"><span>Locality<b>{textOr(profile.countyName)}</b></span><span>Rurality<b>{profile.rurality == null ? "Not provided" : Number(profile.rurality) >= .5 ? "More rural" : "Less rural"}</b></span><span>HPSA score<b>{textOr(profile.hpsaScore)}</b></span></div></div><div><h4>Activated planning priorities</h4><div className="fm-tags">{(profile.profileTags || []).length ? profile.profileTags.slice(0, 8).map(tag => <span className="fm-tag" key={tag.tag} title={tag.explanation}>{tag.label}</span>) : <span className="hint">No planning tags are available from the current county fields.</span>}</div><p className="fm-context-copy">{textOr(profile.profileText)}</p></div></div>
      </Panel>
      <MetricGrid values={values} />
      <Panel icon="list-checks" title="Ranked opportunity matches" desc={`${values.recommendationCount} county matches in this window - retrieved ${textOr(metadata.sourceRetrievedAt)}`}>
        <div className="fm-controls">
          <label className="fm-control-stack"><span>Opportunity posted within</span><select className="fm-control" value={lookbackDays} onChange={e => { setLookbackDays(Number(e.target.value)); resetScopedState(); }} aria-label="Opportunity posted within">{State.LOOKBACK_OPTIONS.map(item => <option value={item.value} key={item.value}>{item.label}</option>)}</select></label>
          <select className="fm-control" value={sort} onChange={e => { setSort(e.target.value); setSelectedId(null); setVisibleCount(10); }} aria-label="Sort opportunities"><option value="score">Sort: match score</option><option value="deadline">Sort: closing date</option><option value="award">Sort: award ceiling</option></select>
          <select className="fm-control" value={filters.agency} onChange={e => setFilter("agency", e.target.value)} aria-label="Filter by agency"><option value="">All agencies</option>{options.agencies.map(item => <option key={item}>{item}</option>)}</select>
          <select className="fm-control" value={filters.tier} onChange={e => setFilter("tier", e.target.value)} aria-label="Filter by match tier"><option value="">All relevance tiers</option><option>Strong relevance</option><option>Moderate relevance</option><option>Limited relevance</option></select>
          <select className="fm-control" value={filters.deadline} onChange={e => setFilter("deadline", e.target.value)} aria-label="Filter by deadline window"><option value="">All deadlines</option><option value="30">Due within 30 days</option><option value="60">Due within 60 days</option><option value="90">Due within 90 days</option></select>
          <select className="fm-control" value={filters.eligibility} onChange={e => setFilter("eligibility", e.target.value)} aria-label="Filter by eligibility screen"><option value="">All eligibility screens</option><option>Likely compatible</option><option>Needs verification</option><option>Likely incompatible</option></select>
          <select className="fm-control" value={filters.category} onChange={e => setFilter("category", e.target.value)} aria-label="Filter by funding category"><option value="">All funding categories</option>{options.categories.map(item => <option key={item}>{item}</option>)}</select>
        </div>
        <div className="fm-results"><div className="fm-list">{rows.length ? <React.Fragment>{rows.slice(0, visibleCount).map(row => <FundingCard key={row.match.opportunityId} row={row} selected={selected && row.match.opportunityId === selected.match.opportunityId} onSelect={() => setSelectedId(row.match.opportunityId)} />)}{visibleCount < rows.length && <button className="fm-show-more" onClick={() => setVisibleCount(count => count + 10)}>Show more ({rows.length - visibleCount} remaining)</button>}</React.Fragment> : <div className="empty">No current match is available for this county, lookback window, and filters. Try a broader window or fewer filters.</div>}</div><FundingDetail row={selected} /></div>
      </Panel>
      <details className="fm-method"><summary>How Funding Matches works</summary><p>The Atlas retains a rolling corpus of posted, still-open relevant opportunities for up to one year. Gemini scores each county and grant against a fixed rubric in batches, then the selected county, lookback window, filters, and sorting determine every displayed metric and recommendation. The relevance score is not an award probability and eligibility remains a verification task.</p></details>
      <p className="fm-source-note"><b>Source:</b> <a href="https://www.grants.gov/api/api-guide" target="_blank" rel="noopener noreferrer">Grants.gov public API</a>. Data retrieved: {textOr(metadata.sourceRetrievedAt)}. Opportunity information can be amended or closed by the publisher after retrieval.</p>
    </div>;
  }

  A.views = A.views || {};
  A.views.FundingMatchesView = FundingMatchesView;
})(window.Atlas);
