// Shared VA choropleth factory over data/va-counties.geojson (properties:
// county_fips/name/region). Returns an imperative api: build once, update on change.
(function(A){
  const { showTT, moveTT, hideTT } = A.tooltip;

  // opts: { fill(f), tip(f) -> html, onClick(f), onHover(f), zoomable, selectedFips }
  function buildChoropleth(host, geo, opts){
    const { zoomable = false } = opts || {};
    const W = 880, H = 430;
    const svg = d3.select(host).html("").append("svg").attr("viewBox", `0 0 ${W} ${H}`)
      .attr("role", "img").attr("aria-label", opts.ariaLabel || "Map of Virginia counties.");
    const projection = d3.geoConicConformal().parallels([37.5, 39.5]).rotate([79, 0]).fitExtent([[16, 16], [W - 16, H - 16]], geo);
    const path = d3.geoPath(projection);

    const gZoom = svg.append("g");
    let current = opts;
    const counties = gZoom.append("g").selectAll("path").data(geo.features).join("path")
      .attr("d", path)
      .attr("stroke", "var(--slate-300)").attr("stroke-width", 0.8)
      .attr("vector-effect", "non-scaling-stroke")
      .style("cursor", current.onClick ? "pointer" : "default")
      .on("mouseover", function(e, d){
        if(current.tip) showTT(current.tip(d), e);
        if(current.onHover) current.onHover(d);
        d3.select(this).attr("stroke", "var(--slate-900)").raise();
      })
      .on("mousemove", moveTT)
      .on("mouseout", function(){
        hideTT();
        if(current.onHover) current.onHover(null);
        d3.select(this).attr("stroke", "var(--slate-300)");
      })
      .on("click", (e, d) => current.onClick && current.onClick(d));

    let zoom = null;
    if(zoomable){
      zoom = d3.zoom().scaleExtent([1, 10]).on("zoom", ev => {
        gZoom.attr("transform", ev.transform);
      });
      svg.call(zoom).on("dblclick.zoom", null);
    }

    function paint(){
      counties
        .style("cursor", current.onClick ? "pointer" : "default")
        .attr("fill", d => current.fill ? current.fill(d) : "var(--surface-sunken)")
        .attr("stroke-width", d => current.selectedFips && (d.properties.county_fips === current.selectedFips) ? 1.8 : 0.8)
        .attr("stroke", d => current.selectedFips && (d.properties.county_fips === current.selectedFips) ? "var(--slate-900)" : "var(--slate-300)");
      if(current.selectedFips){
        counties.filter(d => d.properties.county_fips === current.selectedFips).raise();
      }
    }
    paint();

    return {
      update(nextOpts){ current = { ...current, ...nextOpts }; paint(); },
      reset(){ if(zoom) svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity); },
      projection, path, svg,
    };
  }

  A.charts = A.charts || {};
  A.charts.buildChoropleth = buildChoropleth;
})(window.Atlas);
