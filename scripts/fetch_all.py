#!/usr/bin/env python3
"""Hydrate local data/ from CriticalAsset staging API."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from queries import ASSETS, INTROSPECTION, LOCATIONS, LOCATIONS_TREE, WORK_ORDERS  # noqa: E402

DATA = ROOT / "data"
API_DOCS = ROOT / "docs" / "api"
META = ROOT / "data" / "meta.json"


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
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        raise RuntimeError(f"HTTP {exc.code}: {detail[:500]}") from exc


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {path.relative_to(ROOT)} ({path.stat().st_size} bytes)")


def normalize_work_orders(raw: dict) -> dict:
    nodes = raw.get("data", {}).get("workOrders", {}).get("nodes", [])
    for wo in nodes:
        assets = wo.get("workOrderAssets") or []
        wo["asset"] = assets[0]["asset"] if assets else None
        assignments = wo.get("workOrderAssignments") or []
        assignees = []
        for a in assignments:
            assignees.extend(a.get("users") or [])
        wo["assignees"] = assignees
    return raw


def fetch_authenticated() -> None:
    token = get_token()
    tok_meta = json.loads((DATA / ".token").read_text())
    write_json(
        META,
        {
            "fetchedAt": __import__("datetime").datetime.now().isoformat(),
            "authMode": tok_meta.get("authMode", "unknown"),
            "building": "240 2nd Avenue",
            "team": 12,
        },
    )

    wo = gql(WORK_ORDERS, {"limit": 100, "offset": 0}, token)
    if wo.get("errors"):
        raise RuntimeError(json.dumps(wo["errors"]))
    wo = normalize_work_orders(wo)
    write_json(DATA / "workorders.json", wo)

    assets = gql(ASSETS, {"limit": 100, "offset": 0}, token)
    if assets.get("errors"):
        raise RuntimeError(json.dumps(assets["errors"]))
    write_json(DATA / "assets.json", assets)

    locs = gql(LOCATIONS, token=token)
    if locs.get("errors"):
        raise RuntimeError(json.dumps(locs["errors"]))
    write_json(DATA / "locations.json", locs)

    tree = gql(LOCATIONS_TREE, token=token)
    if tree.get("errors"):
        raise RuntimeError(json.dumps(tree["errors"]))
    write_json(DATA / "locations_tree.json", tree)


def fetch_schema_snapshot() -> None:
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

    enrich = subprocess.run([sys.executable, str(ROOT / "scripts" / "enrich_public.py")], capture_output=True, text=True)
    if enrich.returncode == 0:
        print(enrich.stdout.strip())
    else:
        print(f"Public data enrich warning: {enrich.stderr}", file=sys.stderr)

    print("Hydration complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
