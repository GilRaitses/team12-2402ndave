# O0 → Workers: Team 12 casting handoff

**Building:** 240 2nd Avenue · **Hub:** 12 · **Date:** 2026-06-05

## Mission (one paragraph)

Connect to the Team 12 CriticalAsset staging workspace, pull live work orders (plus assets and locations for joins), and ship a dashboard a building operator could use Monday morning. The Day-Of brief adds the Student Signal loop: capture lived experience, structure it with confidence labels, attach public evidence, and write back to CriticalAsset. O0 owns cross-lane sequencing, secret hygiene, and GitHub Pages deployment; lane workers execute within their manifests.

## Three decisions already made

1. **Auth model:** OAuth2 Client Credentials via GraphQL mutation `applicationClientCredentialsToken` on the same `/api` endpoint — no separate token URL on staging.
2. **Data path:** Browser never touches CriticalAsset. Either `backend/proxy.py` (live) or pre-hydrated `data/*.json` (GitHub Pages static).
3. **Lane split:** O1 auth/proxy · O2 hydration · O3 dashboard · O4 bonus (map, student signal, asset joins).

## Next three steps

1. **O1:** Place Client ID/Secret in local `.env` (from credential sheet). Run `python scripts/auth.py` until token exchange succeeds. If still 401, redeem codes at day-of desk or rotate secret in Developer Console.
2. **O2:** Run `python scripts/fetch_all.py` to populate `data/workorders.json`, `data/assets.json`, `data/locations.json`, and `docs/api/schema_snapshot.json`.
3. **O3:** Open `dashboard/index.html` locally (or enable GitHub Pages on `docs/`). Verify counter row, status table, filters, and detail panel against hydrated data.

## Risk / ambiguity

**Credentials rejected (2026-06-05):** Staging API returns `Invalid client_id or client_secret` for the printed M2M pair. Console URL returns HTTP 200; GraphQL introspection works unauthenticated. Blocker until volunteer activates app or codes are redeemed.

## Lane activation order

```
O1 (auth) → O2 (data) → O3 (dashboard) → O4 (bonus, parallel after O2)
```

## Judging weights (Challenge 01)

| Criterion | Pts |
|-----------|-----|
| Clarity of signal → action | 30 |
| Working CriticalAsset data pull | 25 |
| Dashboard usability | 20 |
| Bonus: joins, map, student signal | 15 |
| Demo / storytelling | 10 |

## Escalation to O0

- Any secret exposure, scope change, or CORS origin registration
- GitHub Pages deploy or repo permission changes
- CriticalAsset write mutations (student signal record-back)
- Cross-lane schema changes
