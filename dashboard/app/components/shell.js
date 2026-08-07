// App chrome: top bar (brand + numbered journey nav + county chip), breadcrumb
// row with the baseline toggle, and the searchable county combobox.
(function(A){
  const Icon = A.Icon;
  const { navigate, useRoute } = A.router;
  const { fmt0 } = A.format;

  // Searchable county combobox, ported from signal.html.
  function CountyCombobox({ records, selectedId, onSelect, autoFocus }){
    const [open, setOpen] = React.useState(!!autoFocus);
    const [query, setQuery] = React.useState("");
    const [active, setActive] = React.useState(0);
    const wrapRef = React.useRef(null);
    const listRef = React.useRef(null);

    const selected = records.find(r => r.id === selectedId);
    const selectedLabel = selected ? `${selected.name} — ${selected.region}` : "";

    const sorted = records.slice().sort((a,b) => d3.ascending(a.name, b.name));
    const q = query.trim().toLowerCase();
    const opts = q ? sorted.filter(r => (`${r.name} ${r.region}`).toLowerCase().includes(q)) : sorted;

    React.useEffect(() => {
      if(!open) return;
      const onDown = e => { if(wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false); };
      document.addEventListener("mousedown", onDown);
      return () => document.removeEventListener("mousedown", onDown);
    }, [open]);

    React.useEffect(() => {
      if(!open || !listRef.current) return;
      const el = listRef.current.children[active];
      if(el) el.scrollIntoView({ block: "nearest" });
    }, [active, open]);

    const openList = () => { setQuery(""); setActive(0); setOpen(true); };
    const pick = r => { if(r) onSelect(r.id); setOpen(false); setQuery(""); };

    const onKeyDown = e => {
      if(e.key === "ArrowDown"){ e.preventDefault(); if(!open){ openList(); return; } setActive(a => Math.min(a + 1, opts.length - 1)); }
      else if(e.key === "ArrowUp"){ e.preventDefault(); setActive(a => Math.max(a - 1, 0)); }
      else if(e.key === "Enter"){ e.preventDefault(); if(open) pick(opts[active]); }
      else if(e.key === "Escape"){ e.preventDefault(); setOpen(false); setQuery(""); e.target.blur(); }
    };

    return (
      <div className="county-combo" ref={wrapRef} style={{ minWidth: 230 }}>
        <input className="county-select" placeholder="Search a county…" aria-label="Search county"
          role="combobox" aria-expanded={open}
          value={open ? query : selectedLabel}
          autoFocus={autoFocus}
          onFocus={openList}
          onClick={() => { if(!open) openList(); }}
          onChange={e => { setQuery(e.target.value); setActive(0); if(!open) setOpen(true); }}
          onKeyDown={onKeyDown} />
        {open && (
          <div className="county-menu" ref={listRef} role="listbox">
            {opts.length ? opts.map((r, i) => (
              <div key={r.id} role="option" aria-selected={r.id === selectedId}
                className={"county-opt" + (i === active ? " active" : "")}
                onMouseEnter={() => setActive(i)}
                onMouseDown={e => { e.preventDefault(); pick(r); }}>
                {r.name} <span className="region">— {r.region}</span>
              </div>
            )) : <div className="county-empty">No counties match “{query}”.</div>}
          </div>
        )}
      </div>
    );
  }

  const TIER_DOT = { High: "var(--danger-500)", Medium: "var(--command-600)", Low: "var(--slate-400)" };
  function chipTier(c){
    const r = c.modelRisk;
    if(r == null) return null;
    return r >= 0.5 ? "High" : r >= 0.25 ? "Medium" : "Low";
  }

  // The global county chip: shows the current county everywhere; opens the
  // combobox in a popover. Selecting re-scopes the current route in place.
  function CountyChip({ records, fips }){
    const [open, setOpen] = React.useState(false);
    const wrapRef = React.useRef(null);
    const route = useRoute();
    const c = records.find(r => r.id === fips);

    React.useEffect(() => {
      if(!open) return;
      const onDown = e => { if(wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false); };
      document.addEventListener("mousedown", onDown);
      return () => document.removeEventListener("mousedown", onDown);
    }, [open]);

    const onSelect = id => {
      setOpen(false);
      A.store.rememberFips(id);
      const v = route.view;
      // County-scoped routes carry the fips in the URL; every other view
      // (Funding Matches, Explore, ...) re-scopes in place via the store.
      if(v === "county" || v === "worklist" || v === "trends") navigate("/" + v + "/" + id);
    };

    return (
      <div className="chip-wrap" ref={wrapRef}>
        <button className={"county-chip" + (c ? "" : " empty")} onClick={() => setOpen(o => !o)}
          aria-haspopup="listbox" aria-expanded={open}
          title="Your selected county follows you across every view">
          {c ? (
            <React.Fragment>
              <span className="dot" style={{ background: TIER_DOT[chipTier(c)] || "var(--slate-400)" }} />
              <span className="chip-name">{c.name}</span>
              <span className="chip-meta mono">{fmt0(c.needIndex)}</span>
            </React.Fragment>
          ) : (
            <React.Fragment><Icon name="search" size={13} /><span>Choose a county</span></React.Fragment>
          )}
          <Icon name="chevron-down" size={13} />
        </button>
        {open && (
          <div className="chip-pop">
            <CountyCombobox records={records} selectedId={fips} onSelect={onSelect} autoFocus />
            <button className="chip-map-link" onClick={() => { setOpen(false); navigate("/overview"); }}>
              <Icon name="map" size={13} /> View on the statewide map
            </button>
          </div>
        )}
      </div>
    );
  }

  // Numbered journey items first, supporting destinations after the divider.
  const NAV = [
    { view: "overview", n: "01", label: "Overview" },
    { view: "county",   n: "02", label: "County" },
    { view: "worklist", n: "03", label: "Worklist" },
    { divider: true },
    { view: "forest",  label: "Needs Forest" },
    { view: "trends",  label: "Trends" },
    { view: "explore", label: "Explore" },
    { view: "methods", label: "Methods" },
    { view: "funding", label: "Funding Matches" },
  ];

  function TopBar({ records, fips, authOn, onSignOut }){
    const route = useRoute();
    const go = view => {
      if(view === "county" || view === "worklist"){
        const id = fips || A.store.defaultFips();
        if(!id) return;
        navigate("/" + view + "/" + id);
      } else {
        navigate("/" + view);
      }
    };
    return (
      <header className="topnav">
        <a className="wordmark" href="#/overview">
          <span className="mark">T</span>
          <span className="wm-text"><b>Triad Signal</b><small>Clinic Needs Atlas</small></span>
        </a>
        <nav className="topnav-items" aria-label="Main">
          {NAV.map((n, i) => n.divider
            ? <span key={i} className="topnav-div" aria-hidden="true" />
            : (
              <button key={n.view} className={"topnav-item" + (route.view === n.view ? " on" : "")}
                aria-current={route.view === n.view ? "page" : undefined}
                onClick={() => go(n.view)}>
                {n.n && <span className="nn mono">{n.n}</span>}{n.label}
              </button>
            ))}
        </nav>
        <div className="topnav-right">
          <CountyChip records={records} fips={fips} />
          {authOn && <button className="signout" onClick={onSignOut}>Sign out</button>}
        </div>
      </header>
    );
  }

  // Breadcrumb doubles as funnel progress; hosts the baseline toggle where
  // baselines are meaningful (county, worklist, explore).
  function CrumbBar({ crumbs, baseline, onBaseline, right }){
    return (
      <div className="crumbbar">
        <nav className="crumbs" aria-label="Breadcrumb">
          {crumbs.map((cr, i) => (
            <React.Fragment key={i}>
              {i > 0 && <span className="crumb-sep" aria-hidden="true">/</span>}
              {cr.href
                ? <a className="crumb-link" href={cr.href}>{cr.label}</a>
                : <span className="crumb-here">{cr.label}</span>}
            </React.Fragment>
          ))}
        </nav>
        <div className="crumb-right">
          {right}
          {onBaseline && (
            <div className="seg" title="Compare against all of Virginia, or against regional peers only.">
              <button className={baseline === "va" ? "on" : ""} onClick={() => onBaseline("va")}>All Virginia</button>
              <button className={baseline === "region" ? "on" : ""} onClick={() => onBaseline("region")}>Region peers</button>
            </div>
          )}
        </div>
      </div>
    );
  }

  A.shell = { TopBar, CrumbBar, CountyCombobox };
})(window.Atlas);
