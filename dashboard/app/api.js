// Single owner of API configuration, the auth token, and every data fetch.
// Views never read localStorage or build Authorization headers themselves.
(function(A){
  const API_BASE = window.CLINIC_ATLAS_API || null;
  const AUTH_ON = !!(window.CLINIC_ATLAS_AUTH && API_BASE);

  const getToken = () => { try { return localStorage.getItem("atlas_token") || ""; } catch(e){ return ""; } };
  const setToken = t => { try { t ? localStorage.setItem("atlas_token", t) : localStorage.removeItem("atlas_token"); } catch(e){} };
  const authHeaders = () => { const t = getToken(); return t ? { Authorization: "Bearer " + t } : {}; };

  async function getJson(url, opts){
    const res = await fetch(url, opts);
    if(!res.ok) throw new Error("HTTP " + res.status);
    return res.json();
  }

  const fetchAtlas = () => {
  const url = API_BASE
    ? API_BASE + "/counties"
    : "data/clinic_atlas.json?v=" + Date.now();

  return getJson(url, {
    headers: authHeaders(),
    cache: "no-store",
  });
};

  // Funding Matches is an optional static artifact. Its absence must never
  // affect the Atlas data load or any pre-existing view.
  const fetchGrantFundingMatches = () => getJson("data/grant_funding_matches.json");

  // County geometry, fetched once and cached for every map in the app.
  // A failed fetch clears the cache so the next mount can retry.
  let geoPromise = null;
  const fetchGeo = () => {
    geoPromise ||= getJson("data/va-counties.geojson").catch(err => { geoPromise = null; throw err; });
    return geoPromise;
  };

  // NNDSS forecast endpoint (API-only; callers handle the no-API case).
  const fetchCountyForecast = fips => getJson(API_BASE + "/forecast/counties/" + fips, { headers: authHeaders() });

  // Usage-event audit trail (US-022). Fire-and-forget; only in authenticated mode.
  function postEvent(event_type, county_fips, payload){
    if(!(AUTH_ON && getToken())) return;
    fetch(API_BASE + "/events", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ event_type, county_fips, ...(payload || {}) }),
    }).catch(() => {});
  }

  function chat(question, county_fips){
    return fetch(API_BASE + "/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ question, county_fips }),
    });
  }

  A.api = { API_BASE, AUTH_ON, getToken, setToken, authHeaders, fetchAtlas, fetchGrantFundingMatches, fetchGeo, fetchCountyForecast, postEvent, chat };
})(window.Atlas);
