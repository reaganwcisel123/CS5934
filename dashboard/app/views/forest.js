// Needs Forest — the dogwood cartogram view; the drawing itself lives in bloom.js.
(function(A){
  const { fetchGeo } = A.api;
  const { ProvPill } = A.ui;
  const AX = A.bloom.AX_STROKE;

  // bloom.js owns and clears the vizRef mount; it only reads (via sideRoot
  // querySelectors) from the JSX sidebar wrapped by mainRef.
  function BloomStage({ records, mainRef }){
    const ref = React.useRef(null);
    const apiRef = React.useRef(null);
    const [geo, setGeo] = React.useState(null);
    const [geoErr, setGeoErr] = React.useState(null);

    React.useEffect(() => { fetchGeo().then(setGeo).catch(e => setGeoErr(e.message)); }, []);

    React.useEffect(() => {
      if(!(geo && ref.current && mainRef.current)) return;
      apiRef.current = A.bloom.mountBloom(ref.current, records, geo, { sideRoot: mainRef.current });
      return () => { apiRef.current && apiRef.current.destroy(); apiRef.current = null; };
    }, [geo, records]);

    if(geoErr) return <div className="empty">Could not load data/va-counties.geojson ({geoErr}).</div>;
    if(!geo) return <div className="empty">Loading the bloom…</div>;
    return <div ref={ref} className="bloom-mount" />;
  }

  function ForestView({ records, provenance }){
    const mainRef = React.useRef(null);
    const outcomesProv = provenance && provenance.outcomes;
    const sdohProv = provenance && provenance.sdoh;

    return (
      <div className="content bloom-view">
        <div className="page-head">
          <h1>A Commonwealth in Bloom</h1>
          <p>Every Virginia county drawn through the state flower — a cartogram of dogwoods, each petal
            and bud circle carrying a measure of community need. Click any part of the legend flower at
            right to flatten the bloom into a county heatmap of that measure.</p>
          <div className="bloom-provrow">
            {outcomesProv && <ProvPill status={outcomesProv.status} label={"Petal color · CDC PLACES · " + outcomesProv.status} />}
            {sdohProv && <ProvPill status={sdohProv.status} label={"Petal length & buds · Census ACS · " + (sdohProv.status === "real" ? "real" : "pending API key")} />}
          </div>
        </div>

        <div className="bloom-main" ref={mainRef}>
          <div className="bloom-vizcol">
            <BloomStage records={records} mainRef={mainRef} />
          </div>

          <aside className="bloom-side">
            <div>
              <h3>Choose a lens</h3>
              <p className="bloom-sidenote">Each petal packs two measures: how long it is shows the
                <b> need</b> (Census ACS), and its color shows a related <b>health outcome</b> (CDC
                PLACES). Click a petal's outer tip for its color measure, or its inner base for its
                length axis.</p>
              <div className="bloom-selector-mount" />
              <div className="bloom-hovernote">&nbsp;</div>
              <div className="bloom-ramp-row" style={{ visibility: "hidden" }}>
                <span>lower</span><span className="bloom-ramp" /><span>heavier burden</span>
              </div>
            </div>
            <div>
              <h3>Reading the bloom</h3>
              <ul className="bloom-axes-key">
                <li><span className="dir">Top</span><i className="bloom-swatch" style={{ background: AX.N }} />Economic deprivation<span className="sub">poverty rate (bud 1) — colored by Hypertension</span></li>
                <li><span className="dir">Right</span><i className="bloom-swatch" style={{ background: AX.E }} />Uninsured<span className="sub">uninsured share (bud 2) — colored by Diabetes</span></li>
                <li><span className="dir">Bottom</span><i className="bloom-swatch" style={{ background: AX.S }} />Demographic demand<span className="sub">average of age 65+ (3) and disability (4) — colored by Depression</span></li>
                <li><span className="dir">Left</span><i className="bloom-swatch" style={{ background: AX.W }} />Access barriers<span className="sub">average of no vehicle (5) and low broadband (6) — colored by Smoking</span></li>
              </ul>
              <p className="bloom-sidenote">Longer petal = deeper need. Darker fill = worse on its color
                measure. A petal outlined in <b>red</b> is at or above the state's worst-quartile
                threshold for that measure — a stark cue, not just a darker shade.</p>
            </div>
            <div>
              <h3>Reading the bud</h3>
              <ul className="bloom-bud-key">
                <li><span className="bloom-num">1</span>Poverty rate</li>
                <li><span className="bloom-num">2</span>Uninsured</li>
                <li><span className="bloom-num">3</span>Age 65 and over</li>
                <li><span className="bloom-num">4</span>Disability</li>
                <li><span className="bloom-num">5</span>No vehicle</li>
                <li><span className="bloom-num">6</span>Broadband <span className="inv">(fills when low)</span></li>
                <li><span className="bloom-num">7</span>Hypertension</li>
                <li><span className="bloom-num">8</span>Depression</li>
              </ul>
              <div className="bloom-fillnote" data-lens="breadth">
                <span><i className="bloom-dotF" />worst quartile statewide</span>
                <span><i className="bloom-dotU" />better than worst quartile</span>
              </div>
            </div>
            <div>
              <h3>Beyond the 4 pillars</h3>
              <p className="bloom-sidenote">A county can be dire on a measure this glyph doesn't
                draw at all — obesity, a shortage-area score, hospitalization risk, and more. A{" "}
                <b>⚠</b> next to a county's name on hover means its single most critical factor is
                one of those hidden measures; click the county for the quantitative breakdown
                (its value, the dire threshold, and its statewide percentile).</p>
            </div>
          </aside>
        </div>

        <p className="bloom-footnote">Glyph: <em>Cornus florida</em> — four notched bracts around a head of small florets.
          Cartogram positions relax counties apart just enough to bloom; click a lens twice to return.</p>
      </div>
    );
  }

  A.views = A.views || {};
  A.views.ForestView = ForestView;
})(window.Atlas);
