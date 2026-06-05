# O0 step log — Team 12 City Hacks Challenge 1

## 2026-06-05 — O0 cast and repo bootstrap

- Read brief: https://thecityhacksthestate.com/challenge1
- Read API manual: https://thecityhacksthestate.com/api-docs
- Verified staging API reachable; introspection works without auth.
- Token exchange with printed M2M credentials: **FAILED** (`Invalid client_id or client_secret`).
- Saved `docs/api/schema_snapshot.json` (651 KB) via unauthenticated introspection.
- Created local repo `/Users/gilraitses/team12-2402ndave`.
- Published GitHub: https://github.com/GilRaitses/team12-2402ndave
- Enabled GitHub Pages: https://gilraitses.github.io/team12-2402ndave/
- Cast lanes O1–O4; handoff written.
- Local `.env` created (gitignored) with team credentials for worker hydration.

### Next

1. Redeem activation codes at day-of desk OR log into Developer Console and verify app exists / rotate secret.
2. `python3 scripts/auth.py` → success
3. `python3 scripts/fetch_all.py` → populate `data/*.json`
4. `./scripts/sync_pages.sh && git add docs/data docs/dashboard && git commit && git push`
