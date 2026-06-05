# Team 12 — 240 2nd Avenue

**The City Hacks The State** · Challenge 01: pull work orders, build the dashboard.

| Item | Value |
|------|-------|
| Building | 240 2nd Avenue |
| Hub | 12 |
| API (staging) | `https://2402ndave.stg.criticalasset.com/api` |
| Console | `https://2402ndave.stg.criticalasset.com/` |
| Brief | [Challenge 01](https://thecityhacksthestate.com/challenge1) |

## Quick start

```bash
cp .env.example .env
# Edit .env with Client ID + Secret from credential sheet (never commit)

python3 scripts/auth.py          # M2M token, or human session fallback
python3 scripts/fetch_all.py     # hydrate data/*.json
./scripts/sync_pages.sh          # copy to docs/ for GitHub Pages

# Local dashboard (open dashboard/index.html or serve docs/)
python3 -m http.server 8080 --directory .
# → http://localhost:8080/dashboard/

# Live proxy (optional)
python3 backend/proxy.py         # http://127.0.0.1:8787/graphql
```

## Work lanes (O0 cast)

| Lane | Owner | Scope |
|------|-------|-------|
| O1 Auth & proxy | A1 | `scripts/auth.py`, `backend/proxy.py` |
| O2 Data hydration | B1 | `scripts/fetch_all.py`, `data/` |
| O3 Dashboard | C1 | `dashboard/`, `docs/` (GitHub Pages) |
| O4 Bonus | D1 | joins, map, student signal |

Full lane spec: [`.cca/catalogue/O0/.../lanes/LANES.md`](.cca/catalogue/O0/20260605_cityhacks-challenge1/lanes/LANES.md)

## GitHub Pages

Pages serves from `/docs`. After hydrating data:

```bash
./scripts/sync_pages.sh
```

Then enable **Settings → Pages → Source: main / docs**.

## Security

- Do **not** put `CA_CLIENT_SECRET` in frontend code or git.
- Do **not** call CriticalAsset directly from the browser (CORS + secret leak).
- Redemption codes are single-use; keep off-repo.

## O0 orchestration

Casting manifest: `.cca/catalogue/O0/20260605_cityhacks-challenge1/manifest.yml`  
Handoff: `.cca/catalogue/O0/20260605_cityhacks-challenge1/orchestrator/HANDOFF.md`
