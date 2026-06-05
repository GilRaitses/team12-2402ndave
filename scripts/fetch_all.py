#!/usr/bin/env python3
"""Hydrate local data/ from CriticalAsset staging API."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from queries import ASSETS, INTROSPECTION, LOCATIONS, LOCATIONS_TREE, WORK_ORDERS  # noqa: E402

DATA = ROOT / "data"
API_DOCS = ROOT / "docs" / "api"


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


def get_token() -> str:
    tok_path = DATA / ".token"
    if tok_path.exists():
        tok = json.loads(tok_path.read_text())
        if tok.get("accessToken"):
            return tok["accessToken"]
    rc = subprocess.run([sys.executable, str(ROOT / "scripts" / "auth.py")], capture_output=True, text=True)
    if rc.returncode != 0:
        raise RuntimeError(rc.stderr or rc.stdout)
    tok = json.loads(tok_path.read_text())
    return tok["accessToken"]


def gql(query: str, variables: dict | None = None, token: str | None = None) -> dict:
    url = os.environ["CA_API_URL"]
    body: dict = {"query": query}
    if variables:
        body["variables"] = variables
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {path.relative_to(ROOT)} ({path.stat().st_size} bytes)")


def fetch_authenticated() -> None:
    token = get_token()
    wo = gql(WORK_ORDERS, {"limit": 100, "offset": 0}, token)
    write_json(DATA / "workorders.json", wo)

    assets = gql(ASSETS, {"limit": 100, "offset": 0}, token)
    write_json(DATA / "assets.json", assets)

    locs = gql(LOCATIONS, token=token)
    write_json(DATA / "locations.json", locs)

    tree = gql(LOCATIONS_TREE, token=token)
    write_json(DATA / "locations_tree.json", tree)


def fetch_schema_snapshot() -> None:
    # Introspection works without auth on staging
    snap = gql(INTROSPECTION)
    write_json(API_DOCS / "schema_snapshot.json", snap)


def main() -> int:
    load_dotenv()
    if not os.environ.get("CA_API_URL"):
        print("Missing CA_API_URL in .env", file=sys.stderr)
        return 1
    DATA.mkdir(parents=True, exist_ok=True)
    API_DOCS.mkdir(parents=True, exist_ok=True)

    fetch_schema_snapshot()

    try:
        fetch_authenticated()
    except Exception as exc:
        print(f"Authenticated fetch failed: {exc}", file=sys.stderr)
        print("Schema snapshot saved. Fix credentials then re-run.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
