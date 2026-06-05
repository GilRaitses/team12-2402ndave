#!/usr/bin/env python3
"""Exchange CriticalAsset credentials for a bearer token (M2M or human login fallback)."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from queries import HUMAN_LOGIN, REFRESH_MUTATION, TOKEN_MUTATION  # noqa: E402

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
    expires = tok.get("expiresIn", 3600)
    return time.time() < saved + expires - skew


def exchange_m2m() -> dict:
    url = os.environ["CA_API_URL"]
    result = gql(
        url,
        TOKEN_MUTATION,
        {
            "input": {
                "clientId": os.environ["CA_CLIENT_ID"],
                "clientSecret": os.environ["CA_CLIENT_SECRET"],
                "scope": os.environ.get("CA_SCOPES", "workorders.read assets.read locations.read"),
            }
        },
    )
    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"], indent=2))
    return result["data"]["applicationClientCredentialsToken"]


def exchange_human() -> dict:
    url = os.environ["CA_API_URL"]
    email = os.environ["CA_CONSOLE_EMAIL"]
    password = os.environ["CA_CONSOLE_PASSWORD"]
    subdomain = os.environ.get("CA_SUBDOMAIN", "2402ndave")
    result = gql(
        url,
        HUMAN_LOGIN,
        {"input": {"email": email, "password": password, "subdomain": subdomain}},
    )
    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"], indent=2))
    auth = result["data"]["login"]
    return {
        "accessToken": auth["accessToken"],
        "refreshToken": auth.get("refreshToken"),
        "tokenType": "Bearer",
        "expiresIn": 3600,
        "scope": "session",
        "authMode": "human",
    }


def exchange() -> dict:
    cached = load_token()
    if cached and token_valid(cached) and cached.get("refreshToken") and cached.get("authMode") != "human":
        try:
            result = gql(os.environ["CA_API_URL"], REFRESH_MUTATION, {"refreshToken": cached["refreshToken"]})
            refreshed = result.get("data", {}).get("applicationRefreshToken")
            if refreshed:
                save_token(refreshed)
                return refreshed
        except Exception:
            pass

    try:
        token = exchange_m2m()
        token["authMode"] = "m2m"
        save_token(token)
        return token
    except Exception:
        pass

    token = exchange_human()
    save_token(token)
    return token


def main() -> int:
    load_dotenv()
    for key in ("CA_API_URL",):
        if not os.environ.get(key):
            print(f"Missing {key}. Copy .env.example → .env", file=sys.stderr)
            return 1
    if not os.environ.get("CA_CLIENT_ID") and not os.environ.get("CA_CONSOLE_EMAIL"):
        print("Need CA_CLIENT_ID or CA_CONSOLE_EMAIL in .env", file=sys.stderr)
        return 1
    try:
        token = exchange()
    except Exception as exc:
        print(f"Token exchange failed: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {k: token[k] for k in ("accessToken", "tokenType", "expiresIn", "scope", "authMode") if k in token},
            indent=2,
        )
    )
    print(f"\nToken cached at {TOKEN_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
