// Minimal hash router; the URL is the source of truth for navigation state.
// Query params ride inside the hash: #/county/51730?baseline=region
(function(A){
  function parse(){
    const raw = location.hash.replace(/^#\/?/, "");
    const [pathPart, queryPart] = raw.split("?");
    const segs = pathPart.split("/").filter(Boolean);
    const query = {};
    new URLSearchParams(queryPart || "").forEach((v, k) => { query[k] = v; });
    return { segs, query, view: segs[0] || "", path: "/" + segs.join("/") };
  }

  let current = parse();
  const listeners = new Set();
  window.addEventListener("hashchange", () => {
    current = parse();
    listeners.forEach(fn => fn());
  });

  const subscribe = fn => (listeners.add(fn), () => listeners.delete(fn));
  const get = () => current;

  function serialize(path, query){
    const q = new URLSearchParams();
    Object.entries(query || {}).forEach(([k, v]) => { if(v != null && v !== "") q.set(k, v); });
    const qs = q.toString();
    return "#" + (path.startsWith("/") ? path : "/" + path) + (qs ? "?" + qs : "");
  }

  // navigate("/county/51730", {query:{baseline:"region"}, replace:true, keep:["baseline"]})
  // `keep` copies the named params from the current route unless overridden.
  function navigate(path, opts){
    const { query = {}, replace = false, keep = ["baseline"] } = opts || {};
    const merged = {};
    keep.forEach(k => { if(current.query[k] != null) merged[k] = current.query[k]; });
    Object.assign(merged, query);
    const hash = serialize(path, merged);
    if(hash === location.hash) return;
    if(replace){
      history.replaceState(null, "", hash);
      current = parse();
      listeners.forEach(fn => fn());
    } else {
      location.hash = hash; // fires hashchange
    }
  }

  const useRoute = () => React.useSyncExternalStore(subscribe, get);

  A.router = { get, navigate, subscribe, useRoute };
})(window.Atlas);
