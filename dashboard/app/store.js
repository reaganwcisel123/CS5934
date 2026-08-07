// Shared app state: fetched data + the last selected county. Navigation state
// (view, fips, baseline) lives in the URL, not here — see router.js.
(function(A){
  const { fetchAtlas, getToken } = A.api;
  const { REGIONS, aggregateOf } = A.domain;

  let state = {
    records: [], provenance: null, err: null,
    token: getToken(),
    lastFips: (() => { try { return localStorage.getItem("atlas_last_fips") || null; } catch(e){ return null; } })(),
    aggVA: null, aggRegion: {},
  };
  const subs = new Set();
  const get = () => state;
  const set = patch => { state = { ...state, ...patch }; subs.forEach(fn => fn()); };
  const subscribe = fn => (subs.add(fn), () => subs.delete(fn));
  // React 18 UMD ships useSyncExternalStore — tear-free reads, no extra deps.
  const useStore = () => React.useSyncExternalStore(subscribe, get);

  function load(){
    fetchAtlas()
      .then(d => {
        const records = d.records || [];
        const aggVA = records.length ? aggregateOf(records) : null;
        const aggRegion = {};
        if(records.length) REGIONS.forEach(r => aggRegion[r] = aggregateOf(records.filter(c => c.region === r)));
        set({ records, provenance: d.provenance, aggVA, aggRegion, err: null });
      })
      .catch(e => set({ err: "Could not load the atlas data — run `uv run python src/build_dataset.py`. (" + e.message + ")" }));
  }

  // The county every county-scoped view falls back to when the URL has none:
  // last visited, else the highest-need county (the most actionable default).
  function rememberFips(fips){
    if(!fips || fips === state.lastFips) return;
    try { localStorage.setItem("atlas_last_fips", fips); } catch(e){}
    set({ lastFips: fips });
  }
  function defaultFips(){
    if(state.lastFips && state.records.some(c => c.id === state.lastFips)) return state.lastFips;
    const top = state.records.reduce((a, b) => ((b.needIndex ?? 0) > (a.needIndex ?? 0) ? b : a), state.records[0]);
    return top && top.id;
  }

  const byId = id => state.records.find(c => c.id === id);
  // Baseline aggregate for a county under the given mode ("va" | "region").
  // Null when the aggregate doesn't exist (e.g. a region outside REGIONS).
  function baselineFor(c, baselineMode){
    const agg = baselineMode === "region" ? state.aggRegion[c.region] : state.aggVA;
    if(!agg) return null;
    return baselineMode === "region"
      ? Object.assign({}, agg, { label: c.region + " peers", short: c.region })
      : Object.assign({}, agg, { label: "all Virginia", short: "Virginia" });
  }

  A.store = { get, set, subscribe, useStore, load, rememberFips, defaultFips, byId, baselineFor };
})(window.Atlas);
