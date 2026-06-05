# O0 step log — Team 12 City Hacks Challenge 1

## 2026-06-05 — COMPLETE

### Auth (O1)
- M2M credentials: still invalid on staging.
- Human session login via GraphQL `login` mutation: **SUCCESS**.
- Token cached in `data/.token` (gitignored); `scripts/auth.py` tries M2M then human fallback.

### Data hydration (O2)
- `workorders.json` — 3 live work orders
- `assets.json` — 100 assets
- `locations.json` — site record
- `locations_tree.json` — full building/floor tree (58 KB)
- `meta.json` — fetch timestamp, auth mode

### Dashboard (O3)
- Counter row, filters (status, priority, category), table, detail panel
- Asset joins via `workOrderAssets`
- GitHub Pages bundle in `docs/`

### Bonus (O4)
- Service category grouping
- Building open-WO stats + floor count from location tree
- Student signal structurer with confidence labels
- `scripts/submit_signal.py` for write-back (dry-run if scope missing)

### Submission
- `docs/submission.html` — demo links, judging map, 3-minute script

### Publish
- Repo: https://github.com/GilRaitses/team12-2402ndave
- Pages: https://gilraitses.github.io/team12-2402ndave/
