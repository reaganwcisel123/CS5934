// Funding Matches is deliberately self-contained: it reads the optional grant
// artifact and cannot make an absent artifact affect any existing Atlas view.
(function(A){
  const { Panel, StatCard } = A.ui;
  const { CountyCombobox } = A.shell;
  const { fetchGrantFundingMatches } = A.api;

  const textOr = (value, fallback = "Not provided") => value == null || value === "" ? fallback : value;
  const money = value => value == null ? "Not provided" : new Intl.NumberFormat("en-US", { style:"currency", currency:"USD", maximumFractionDigits:0 }).format(value);
  const dateLabel = value => {
    if(!value) return "Not provided";
    const parsed = new Date(value + "T12:00:00Z");
    return Number.isNaN(parsed.getTime()) ? value : new Intl.DateTimeFormat("en-US", { month:"short", day:"numeric", year:"numeric", timeZone:"UTC" }).format(parsed);
  };
  const awardRange = opportunity => opportunity.awardFloor != null && opportunity.awardCeiling != null
    ? `${money(opportunity.awardFloor)} – ${money(opportunity.awardCeiling)}`
    : opportunity.awardFloor != null ? `From ${money(opportunity.awardFloor)}`
    : opportunity.awardCeiling != null ? `Up to ${money(opportunity.awardCeiling)}`
    : "Not provided";
  const scoreLabel = score => `${Math.round((score || 0) * 100)}%`;

  function MetricGrid({ artifact, countyRows }){
    const metadata = artifact.metadata || {};
    const strong = countyRows.filter(row => row.match.matchTier === "Strong relevance").length;
    const upcoming = countyRows.filter(row => row.opportunity.closingDate && row.match.daysRemaining != null && row.match.daysRemaining >= 0)
      .sort((a,b) => a.match.daysRemaining - b.match.daysRemaining)[0];
    return (
      <div className="stat-grid" aria-label="Funding-match summary metrics">
        <StatCard label="Opportunities indexed" value={String(metadata.opportunityCount || 0)} accent="command" />
        <StatCard label="County recommendations" value={String(countyRows.length)} />
        <StatCard label="Strong relevance" value={String(strong)} accent="command" />
        <StatCard label="Nearest deadline" value={upcoming ? dateLabel(upcoming.opportunity.closingDate) : "Not provided"} />
      </div>
    );
  }

  function FundingCard({ row, selected, onSelect }){
    const { match, opportunity } = row;
    return (
      <article className={"fm-card" + (selected ? " selected" : "")}>
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
        <a className="fm-source" href={opportunity.officialUrl} target="_blank" rel="noopener noreferrer">View official record <span aria-hidden="true">↗</span></a>
      </article>
    );
  }

  function FundingDetail({ row }){
    if(!row) return <Panel icon="layers" title="Opportunity details"><p className="hint">Select a recommendation to review its deadline, eligibility screen, score breakdown, and application-readiness prompts.</p></Panel>;
    const { opportunity, match } = row;
    const items = [
      ["Opportunity number", opportunity.opportunityNumber], ["Agency", opportunity.agency], ["Status", opportunity.status], ["Deadline", opportunity.closingDate ? dateLabel(opportunity.closingDate) : match.deadlineStatus],
      ["Award range", awardRange(opportunity)], ["Cost sharing", opportunity.costSharingRequired === true ? "Listed as required" : opportunity.costSharingRequired === false ? "Not listed as required" : "Not provided"],
      ["Applicant types", (opportunity.applicantTypes || []).join(", ")], ["Categories", (opportunity.fundingCategories || []).join(", ")],
      ["Funding instrument", (opportunity.fundingInstruments || []).join(", ")], ["Eligibility screen", textOr(match.eligibilityStatus, "Needs verification")],
    ];
    return (
      <Panel icon="layers" title="Opportunity details" desc={scoreLabel(match.matchScore) + " match score"} bodyClass="fm-detail">
        <h4>{textOr(opportunity.title)}</h4>
        <p className="fm-detail-copy">{textOr(opportunity.synopsis, "No short synopsis was provided in the indexed record.")}</p>
        <div className="fm-detail-grid">{items.map(([label, value]) => <div className="fm-detail-item" key={label}><span>{label}</span><b>{textOr(value)}</b></div>)}</div>
        <h4 style={{ marginTop:16 }}>Match-score breakdown</h4>
        <ul className="fm-breakdown">
          <li>Gemini relevance: {scoreLabel(match.geminiScore)}</li>
          <li>Structured compatibility: {scoreLabel(match.eligibilityScore)}</li><li>Deadline usability: {scoreLabel(match.deadlineScore)}</li>
        </ul>
        <p className="fm-warning"><b>Eligibility screen:</b> {textOr(match.eligibilityScreenReason, "Needs verification against the official opportunity record.")}</p>
        <h4 style={{ marginTop:16 }}>Application-readiness prompts</h4>
        <ul className="fm-checklist">{(match.readinessChecklist || []).map((item, index) => <li key={index}>{item}</li>)}</ul>
        <a className="fm-source" href={opportunity.officialUrl} target="_blank" rel="noopener noreferrer">Open official Grants.gov record <span aria-hidden="true">↗</span></a>
      </Panel>
    );
  }

  function FundingMatchesView({ records, initialFips }){
    const [artifact, setArtifact] = React.useState(null);
    const [error, setError] = React.useState("");
    const [selectedFips, setSelectedFips] = React.useState(initialFips);
    const [selectedId, setSelectedId] = React.useState(null);
    const [sort, setSort] = React.useState("score");
    const [filters, setFilters] = React.useState({ agency:"", tier:"", deadline:"", eligibility:"", category:"" });

    React.useEffect(() => {
      let active = true;
      fetchGrantFundingMatches().then(data => {
        if(!data || !data.metadata || !data.opportunities || !data.profiles || !data.matchesByCounty) throw new Error("The grant artifact schema is incomplete.");
        if(active) { setArtifact(data); setError(""); }
      }).catch(() => { if(active) setError("Funding Matches is not available yet. Run the grant recommendation pipeline to generate the optional artifact."); });
      return () => { active = false; };
    }, []);
    React.useEffect(() => {
      if(initialFips && initialFips !== selectedFips){
        setSelectedFips(initialFips); setSelectedId(null);
        setFilters({ agency:"", tier:"", deadline:"", eligibility:"", category:"" });
      }
    }, [initialFips]);

    if(error) return <div className="content funding-matches"><div className="empty">{error}</div></div>;
    if(!artifact) return <div className="content funding-matches"><div className="empty">Loading current funding opportunities…</div></div>;
    const profile = artifact.profiles[selectedFips];
    if(!profile) return <div className="content funding-matches"><div className="empty">No county-informed planning profile is available for this locality.</div></div>;
    const rawRows = (artifact.matchesByCounty[selectedFips] || []).map(match => ({ match, opportunity: artifact.opportunities[match.opportunityId] })).filter(row => !!row.opportunity);
    const options = {
      agencies: [...new Set(rawRows.map(row => row.opportunity.agency).filter(Boolean))].sort(),
      categories: [...new Set(rawRows.flatMap(row => row.opportunity.fundingCategories || []))].sort(),
    };
    const rows = rawRows.filter(row => {
      const { match, opportunity } = row;
      const deadlineOk = !filters.deadline || (match.daysRemaining != null && match.daysRemaining >= 0 && match.daysRemaining <= Number(filters.deadline));
      return (!filters.agency || opportunity.agency === filters.agency) && (!filters.tier || match.matchTier === filters.tier)
        && deadlineOk && (!filters.eligibility || match.eligibilityStatus === filters.eligibility)
        && (!filters.category || (opportunity.fundingCategories || []).includes(filters.category));
    }).sort((a,b) => sort === "deadline"
      ? (a.match.daysRemaining == null ? Infinity : a.match.daysRemaining) - (b.match.daysRemaining == null ? Infinity : b.match.daysRemaining)
      : sort === "award" ? (b.opportunity.awardCeiling || -1) - (a.opportunity.awardCeiling || -1)
      : b.match.matchScore - a.match.matchScore);
    const selected = rows.find(row => row.match.opportunityId === selectedId) || rows[0] || null;
    const setFilter = (key, value) => setFilters(current => ({ ...current, [key]: value }));
    const metadata = artifact.metadata || {};
    return (
      <div className="content funding-matches" data-county-fips={selectedFips}>
        <div className="page-head"><h1>Rural Clinic Funding Opportunities</h1><p>Funding Matches ranks current official grant opportunities against a county-informed rural clinic planning profile.</p></div>
        <div className="fm-intro"><div><b>Planning support, not an award prediction.</b><p>Eligibility must be independently verified, opportunity details can change, and no patient information is used.</p></div><span className="pill" style={{ borderColor:"var(--brand)", color:"var(--brand)" }}>Grants.gov · public source</span></div>
        <Panel icon="map" title="County-informed clinic planning profile" desc="Public county indicators; not a confirmed clinic strategy">
          <div className="fm-context"><div><CountyCombobox records={records} selectedId={selectedFips} onSelect={id => { setSelectedFips(id); setSelectedId(null); }} /><div className="fm-meta"><span>Locality<b>{textOr(profile.countyName)}</b></span><span>Rurality<b>{profile.rurality == null ? "Not provided" : Number(profile.rurality) >= .5 ? "More rural" : "Less rural"}</b></span><span>HPSA score<b>{textOr(profile.hpsaScore)}</b></span></div></div><div><h4>Activated planning priorities</h4><div className="fm-tags">{(profile.profileTags || []).length ? profile.profileTags.slice(0, 8).map(tag => <span className="fm-tag" key={tag.tag} title={tag.explanation}>{tag.label}</span>) : <span className="hint">No planning tags are available from the current county fields.</span>}</div><p className="fm-context-copy">{textOr(profile.profileText)}</p></div></div>
        </Panel>
        <MetricGrid artifact={artifact} countyRows={rawRows} />
        <Panel icon="list-checks" title="Ranked opportunity matches" desc={`${metadata.modelVersion || "Model version not provided"} · retrieved ${textOr(metadata.sourceRetrievedAt)}`}>
          <div className="fm-controls">
            <select className="fm-control" value={sort} onChange={e => setSort(e.target.value)} aria-label="Sort opportunities"><option value="score">Sort: match score</option><option value="deadline">Sort: closing date</option><option value="award">Sort: award ceiling</option></select>
            <select className="fm-control" value={filters.agency} onChange={e => setFilter("agency", e.target.value)} aria-label="Filter by agency"><option value="">All agencies</option>{options.agencies.map(item => <option key={item}>{item}</option>)}</select>
            <select className="fm-control" value={filters.tier} onChange={e => setFilter("tier", e.target.value)} aria-label="Filter by match tier"><option value="">All relevance tiers</option><option>Strong relevance</option><option>Moderate relevance</option><option>Limited relevance</option></select>
            <select className="fm-control" value={filters.deadline} onChange={e => setFilter("deadline", e.target.value)} aria-label="Filter by deadline window"><option value="">All deadlines</option><option value="30">Due within 30 days</option><option value="60">Due within 60 days</option><option value="90">Due within 90 days</option></select>
            <select className="fm-control" value={filters.eligibility} onChange={e => setFilter("eligibility", e.target.value)} aria-label="Filter by eligibility screen"><option value="">All eligibility screens</option><option>Likely compatible</option><option>Needs verification</option></select>
            <select className="fm-control" value={filters.category} onChange={e => setFilter("category", e.target.value)} aria-label="Filter by funding category"><option value="">All funding categories</option>{options.categories.map(item => <option key={item}>{item}</option>)}</select>
          </div>
          <div className="fm-results"><div className="fm-list">{rows.length ? rows.slice(0, 10).map(row => <FundingCard key={row.match.opportunityId} row={row} selected={selected && row.match.opportunityId === selected.match.opportunityId} onSelect={() => setSelectedId(row.match.opportunityId)} />) : <div className="empty">No current match is available for these filters. Try a broader deadline, agency, or eligibility screen.</div>}</div><FundingDetail row={selected} /></div>
        </Panel>
        <details className="fm-method"><summary>How Funding Matches works</summary><p>The Atlas converts public county indicators into a controlled planning profile. Deterministic public rules select a small active candidate set, then Gemini ranks those candidates using structured output that the server validates against known Grants.gov records. The relevance score is not an award probability and eligibility remains a verification task.</p></details>
        <p className="fm-source-note"><b>Source:</b> <a href="https://www.grants.gov/api/api-guide" target="_blank" rel="noopener noreferrer">Grants.gov public API</a>. Data retrieved: {textOr(metadata.sourceRetrievedAt)}. Opportunity information can be amended or closed by the publisher after retrieval.</p>
      </div>
    );
  }

  A.views = A.views || {};
  A.views.FundingMatchesView = FundingMatchesView;
})(window.Atlas);
