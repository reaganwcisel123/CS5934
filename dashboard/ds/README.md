# Vendored design system (tokens)

Self-contained subset of the Triad Health Engine Design System that
`../app.html` loads at runtime: the token stylesheet manifest (`styles.css`)
and the token layer (`tokens/*.css`: colors, dataviz, typography, spacing,
radius, shadows, motion, fonts, base).

The palette was rethemed to the navy/gold "CareIntelligence" system: royal
`#3257b8` as the brand, navy `#0b1226` for dark chrome, gold `#cfac49` for
accents. Violet is retained solely as the "synthetic data" provenance accent.
Chart colors live in `tokens/dataviz.css`, resolved once by `../app/theme.js`
(D3's interpolated scales need concrete hex).

The compiled React component bundle (`_ds_bundle.js`) was removed. The few
components the app used (StatCard, Tabs, Icon) are reimplemented locally in
`../app/components/`, which also dropped the unpinned `lucide@latest` CDN
dependency. This directory no longer tracks the upstream kit's bundle; only
the tokens are vendored.
