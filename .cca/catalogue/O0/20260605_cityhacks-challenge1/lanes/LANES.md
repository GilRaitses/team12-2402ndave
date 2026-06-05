# Work lanes — Team 12

## O1 · Auth & API proxy (`A1`)

**Objective:** Server-side token exchange, caching, and GraphQL proxy.

| Task | File | Done when |
|------|------|-----------|
| Env template | `.env.example` | Vars documented |
| Token script | `scripts/auth.py` | Prints access token + expiry |
| Proxy server | `backend/proxy.py` | `/health`, `/graphql` routes work |
| Scope audit | `docs/api/SCOPES.md` | Matches granted app scopes |

**Constraints:** No secrets in frontend. Refresh token persisted in `data/.token` (gitignored).

---

## O2 · Data hydration (`B1`)

**Objective:** Pull and cache all Challenge 01 data sources locally.

| Task | File | Done when |
|------|------|-----------|
| Work orders | `data/workorders.json` | `workOrders` query landed |
| Assets | `data/assets.json` | `assets(limit:100)` landed |
| Locations | `data/locations.json` | `locations` + `locationsTree` landed |
| Schema snap | `docs/api/schema_snapshot.json` | Introspection saved |
| Fetch runner | `scripts/fetch_all.py` | One command hydrates all |

**GraphQL queries:** See `scripts/queries.py`.

---

## O3 · Dashboard UI (`C1`)

**Objective:** Operator-facing single screen for GitHub Pages.

| Task | File | Done when |
|------|------|-----------|
| Counter row | `dashboard/js/app.js` | Open / In Progress / Overdue |
| Work order table | `dashboard/index.html` | Title, status, priority, asset, location, due |
| Filters | `dashboard/js/app.js` | Status + priority filters |
| Detail panel | `dashboard/js/app.js` | Row click → full WO + asset |
| Styles | `dashboard/css/style.css` | Readable on projector |

**Deploy:** Copy `dashboard/*` → `docs/` for GitHub Pages, or set Pages source to `/docs`.

---

## O4 · Bonus (`D1`)

**Objective:** Judging bonus points — optional after O2 lands.

| Task | Points area | Notes |
|------|-------------|-------|
| Asset category grouping | joins | `assets.read` enrichment |
| Top-5 buildings by open WOs | map | `locations.read` |
| Student signal submit | student signal | `workorders.write` mutation |
| Confidence labels | Day-Of brief | Verified / Likely / Inferred / Missing |

**File:** `dashboard/js/bonus.js`, `scripts/submit_signal.py`
