-- Sprint demo login (Phase 3 auth): a single dummy account so the gated site
-- can be signed into for the demo. Replace with real accounts before any use.
-- email: demo@clinicatlas.dev   password: triad-demo-2026
insert into app_user (email, password_hash, role, org)
values ('demo@clinicatlas.dev', '$2b$12$jAVIDPXYte2aOJVx7ncIAuBr1AF9sMAXuEuVydxwS260EdGExDpLW', 'viewer', 'Demo')
on conflict (email) do nothing;
