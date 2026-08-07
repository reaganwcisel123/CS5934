// Domain vocabulary shared by every view: SDoH domains, outcomes, UDS measures,
// tier interventions, regions, and baseline aggregation.
(function(A){
  const DOMAINS = [
    { key:"economic",    short:"Economic",    label:"Economic stability",  source:"Census ACS" },
    { key:"education",   short:"Education",   label:"Education access",    source:"Census ACS" },
    { key:"food",        short:"Food/Housing",label:"Neighborhood & food", source:"USDA" },
    { key:"environment", short:"Environment", label:"Environmental burden",source:"EPA EJSCREEN" },
    { key:"access",      short:"Care access", label:"Healthcare access",   source:"HRSA HPSA" },
  ];
  const OUTCOMES = [
    { key:"diabetes", short:"Diabetes" }, { key:"obesity", short:"Obesity" },
    { key:"mhlth", short:"Mental distress" }, { key:"bphigh", short:"High BP" },
  ];
  const MEASURES = [
    { key:"htn_control",     label:"Hypertension controlled",         source:"HRSA UDS", better:"high" },
    { key:"dm_poor",         label:"Diabetes uncontrolled (HbA1c>9%)",source:"HRSA UDS", better:"low" },
    { key:"depr_screen",     label:"Depression screened & follow-up", source:"HRSA UDS", better:"high" },
    { key:"cervical_screen", label:"Cervical cancer screening",       source:"HRSA UDS", better:"high" },
    { key:"child_immun",     label:"Childhood immunization",          source:"HRSA UDS", better:"high" },
  ];
  const TIER_INTERVENTIONS = {
    High: [
      "Nurse outreach call within 48 hours to confirm medications, transport, and food access.",
      "Arrange NEMT transport plus a telehealth follow-up to close the immediate care gap.",
      "Warm hand-off to a benefits navigator for 340B medication-cost assistance.",
    ],
    Medium: [
      "Add to the two-week care-coordinator callback list for a check-in.",
      "Offer SNAP enrollment and an on-site food-pharmacy or mobile-market referral.",
      "Send a plain-language care plan and confirm the next visit is booked.",
    ],
    Low: [
      "Keep on the standard recall schedule for annual screening and refills.",
      "Share health-literacy materials and self-management resources.",
    ],
  };
  // Fall back to Low so a tier lookup never returns undefined.
  const interventionsForTier = t => TIER_INTERVENTIONS[t] || TIER_INTERVENTIONS.Low;

  const REGIONS = ["Northern","Central","Valley","Southwest","Tidewater"];

  function aggregateOf(list){
    const mean = f => d3.mean(list, f);
    return {
      dom: Object.fromEntries(DOMAINS.map(D => [D.key, mean(c => c.dom[D.key])])),
      outcomes: Object.fromEntries(OUTCOMES.map(O => [O.key, mean(c => c.outcomes[O.key])])),
      measures: Object.fromEntries(MEASURES.map(m => [m.key, mean(c => c.measures[m.key])])),
      needIndex: mean(c => c.needIndex), hpsaScore: mean(c => c.hpsaScore),
      patients: d3.median(list, c => c.patients), n: list.length,
    };
  }

  A.domain = { DOMAINS, OUTCOMES, MEASURES, interventionsForTier, REGIONS, aggregateOf };
})(window.Atlas);
