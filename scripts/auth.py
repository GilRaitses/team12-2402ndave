#!/usr/bin/env python3
"""Exchange CriticalAsset client credentials for a bearer token."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from queries import REFRESH_MUTATION, TOKEN_MUTATION  # noqa: E402

TOKEN_PATH = ROOT / "data" / ".token"


def load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())


def gql(url: str, query: str, variables: dict | None = None, token: str | None = None) -> dict:
    body: dict = {"query": query}
    if variables:
        body["variables"] = variables
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def save_token(payload: dict) -> None:
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload["saved_at"] = int(time.time())
    TOKEN_PATH.write_text(json.dumps(payload, indent=2))


def load_token() -> dict | None:
    if not TOKEN_PATH.exists():
        return None
    return json.loads(TOKEN_PATH.read_text())


def token_valid(tok: dict, skew: int = 60) -> bool:
    if not tok or "accessToken" not in tok:
        return False
    saved = tok.get("saved_at", 0)
    expires = tok.get("expiresIn", 0)
    return time.time() < saved + expires - skew


def exchange() -> dict:
    url = os.environ["CA_API_URL"]
    client_id = os.environ["CA_CLIENT_ID"]
    client_secret = os.environ["CA_CLIENT_SECRET"]
    scope = os.environ.get("CA_SCOPES", "workorders.read assets.read locations.read")

    cached = load_token()
    if cached and token_valid(cached) and cached.get("refreshToken"):
        try:
            result = gql(url, REFRESH_MUTATION, {"refreshToken": cached["refreshToken"]})
            refreshed = result.get("data", {}).get("applicationRefreshToken")
            if refreshed:
                save_token(refreshed)
                return refreshed
        except Exception:
            pass

    result = gql(
        url,
        TOKEN_MUTATION,
        {
            "input": {
                "clientId": client_id,
                "clientSecret": client_secret,
                "scope": scope,
            }
        },
    )
    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"], indent=2))
    token = result["data"]["applicationClientCredentialsToken"]
    save_token(token)
    return token


def main() -> int:
    load_dotenv()
    for key in ("CA_API_URL", "CA_CLIENT_ID", "CA_CLIENT_SECRET"):
        if not os.environ.get(key):
            print(f"Missing {key}. Copy .env.example → .env", file=sys.stderr)
            return 1
    try:
        token = exchange()
    except Exception as exc:
        print(f"Token exchange failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({k: token[k] for k in ("accessToken", "tokenType", "expiresIn", "scope")}, indent=2))
    print(f"\nToken cached at {TOKEN_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
