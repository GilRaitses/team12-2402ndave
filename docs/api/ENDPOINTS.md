# CriticalAsset endpoints — Team 12 staging

## Base URLs

| Surface | URL |
|---------|-----|
| GraphQL API | `https://2402ndave.stg.criticalasset.com/api` |
| Human console | `https://2402ndave.stg.criticalasset.com/` |
| Hackathon API guide | https://thecityhacksthestate.com/api-docs |

## Authentication

Single GraphQL mutation (no separate OAuth URL on staging):

```graphql
mutation ApplicationToken($input: ApplicationClientCredentialsInput!) {
  applicationClientCredentialsToken(input: $input) {
    accessToken refreshToken tokenType expiresIn scope
  }
}
```

Scopes (dot notation): `workorders.read`, `assets.read`, `locations.read`

## Primary queries

| Query | Args | Lane |
|-------|------|------|
| `workOrders` | `filter`, `limit`, `offset` | O2 |
| `assets` | `filter`, `limit`, `offset` | O2 |
| `locations` | — | O2 |
| `locationsTree` | — | O2 / O4 |
| `locationMapDetail` | `locationId` | O4 bonus |

## Local artifacts

| File | Source |
|------|--------|
| `data/workorders.json` | `workOrders(limit:100)` |
| `data/assets.json` | `assets(limit:100)` |
| `data/locations.json` | `locations` |
| `data/locations_tree.json` | `locationsTree` |
| `docs/api/schema_snapshot.json` | introspection (no auth) |

## Proxy (dev)

`python backend/proxy.py` → `POST http://127.0.0.1:8787/graphql`
