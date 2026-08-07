# Explore view (parked)

The Explore tab was pulled from the app navigation but kept here in case we
bring it back. Nothing in the live app loads these files.

What's in this folder:

- `explore.js` is the view itself: four tabs (need vs. population scatter,
  deviation heatmap, quality gaps, and the glyph "Needs forest" demo).
- `scatter.js`, `heatmap.js`, and `gapchart.js` are the d3 charts the first
  three tabs draw. Only Explore used them.
- `glyphmap.js` holds the `A.forest` glyph helpers for the demo forest tab.
  This is the old clinic-needs-forest prototype, not the bloom Needs Forest
  view that is still live.

The CSS was left in `app/app.css` because most of the classes are shared with
Trends and Overview. The few Explore-only rules (`.needrow`, `.density`,
`.cliniclist`, `.heat-scroll`, `.region-legend`) are harmless while unused.

## To restore

1. Move `explore.js` back to `app/views/` and the four chart files back to
   `app/charts/`.
2. Re-add the script tags in `app.html`: the charts between `choropleth.js`
   and `bloom.js`, the view between `trends.js` and `methods.js`.
3. In `app/main.js`: add `"explore"` to `VIEWS`, restore the `crumbsFor` case,
   add `route.view === "explore"` back to `showBaseline`, and restore the
   `ExploreView` render branch (it takes `records`, `fips`, `baselineMode`,
   `provenance`, and `query`).
4. In `app/components/shell.js`: add `{ view: "explore", label: "Explore" }`
   back to `NAV`.
5. Add `"explore.js"` back to the view list in
   `tests/test_funding_dashboard.py`.
