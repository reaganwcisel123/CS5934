(function(root, factory){
  const state = factory();
  if(typeof module !== "undefined" && module.exports) module.exports = state;
  else { root.Atlas = root.Atlas || {}; root.Atlas.fundingState = state; }
})(typeof window !== "undefined" ? window : globalThis, function(){
  const LOOKBACK_OPTIONS = [
    { value:7, label:"Last 7 days" }, { value:14, label:"Last 14 days" },
    { value:30, label:"Last 30 days" }, { value:90, label:"Last 3 months" },
    { value:180, label:"Last 6 months" }, { value:365, label:"Last 12 months" },
  ];

  const dayKey = value => value instanceof Date ? value.toISOString().slice(0, 10) : String(value || "").slice(0, 10);
  const addDays = (value, days) => {
    const result = new Date(dayKey(value) + "T00:00:00Z");
    result.setUTCDate(result.getUTCDate() + days);
    return dayKey(result);
  };
  const isOpenInWindow = (opportunity, lookbackDays, today) => {
    const posting = dayKey(opportunity.postingDate);
    const closing = dayKey(opportunity.closingDate);
    const cutoff = addDays(today, -Number(lookbackDays));
    return opportunity.status === "posted" && !!posting && posting >= cutoff && posting <= dayKey(today) && (!closing || closing >= dayKey(today));
  };
  const availableOpportunities = (artifact, lookbackDays, today) => Object.values(artifact.opportunities || {})
    .filter(opportunity => isOpenInWindow(opportunity, lookbackDays, today));
  const countyRows = (artifact, countyFips, lookbackDays, today) => (artifact.matchesByCounty?.[countyFips] || [])
    .map(match => ({ match, opportunity: artifact.opportunities?.[match.opportunityId] }))
    .filter(row => row.opportunity && isOpenInWindow(row.opportunity, lookbackDays, today));
  const filteredRows = (rows, filters) => rows.filter(({ match, opportunity }) => {
    const deadlineOk = !filters.deadline || (match.daysRemaining != null && match.daysRemaining >= 0 && match.daysRemaining <= Number(filters.deadline));
    return (!filters.agency || opportunity.agency === filters.agency)
      && (!filters.tier || match.matchTier === filters.tier)
      && deadlineOk
      && (!filters.eligibility || match.eligibilityStatus === filters.eligibility)
      && (!filters.category || (opportunity.fundingCategories || []).includes(filters.category));
  });
  const sortedRows = (rows, sort) => rows.slice().sort((a, b) => sort === "deadline"
    ? (a.match.daysRemaining == null ? Infinity : a.match.daysRemaining) - (b.match.daysRemaining == null ? Infinity : b.match.daysRemaining)
    : sort === "award" ? (b.opportunity.awardCeiling || -1) - (a.opportunity.awardCeiling || -1)
    : b.match.matchScore - a.match.matchScore || String(a.match.opportunityId).localeCompare(String(b.match.opportunityId)));
  const metrics = (available, rows) => {
    const upcoming = rows.filter(row => row.opportunity.closingDate && row.match.daysRemaining != null && row.match.daysRemaining >= 0)
      .sort((a, b) => a.match.daysRemaining - b.match.daysRemaining)[0];
    return {
      availableCount: available.length,
      recommendationCount: rows.length,
      strongCount: rows.filter(row => row.match.matchTier === "Strong relevance").length,
      nearestDeadline: upcoming?.opportunity.closingDate || null,
    };
  };
  return { LOOKBACK_OPTIONS, dayKey, isOpenInWindow, availableOpportunities, countyRows, filteredRows, sortedRows, metrics };
});
