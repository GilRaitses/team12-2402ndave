#!/usr/bin/env python3
"""Record a structured student signal back to CriticalAsset (requires workorders.write)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from auth import exchange, load_dotenv  # noqa: E402


def gql(query: str, variables: dict, token: str) -> dict:
    url = os.environ["CA_API_URL"]
    body = {"query": query, "variables": variables}
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    load_dotenv()
    if len(sys.argv) < 2:
        print("Usage: submit_signal.py '<student signal text>' [work_order_id]", file=sys.stderr)
        return 1
    text = sys.argv[1]
    wo_id = sys.argv[2] if len(sys.argv) > 2 else None

    token = exchange()["accessToken"]
    mutation = """
    mutation CreateWorkOrder($input: CreateWorkOrderInput!) {
      createWorkOrder(input: $input) { id title description severity }
    }
    """
    inp = {
        "title": f"Student Signal: {text[:60]}",
        "description": text,
        "severity": "medium",
    }
    if wo_id:
        inp["parentId"] = wo_id

    try:
        result = gql(mutation, {"input": inp}, token)
    except Exception as exc:
        print(f"Submit failed (may need workorders.write scope): {exc}", file=sys.stderr)
        print(json.dumps({"dryRun": True, "input": inp}, indent=2))
        return 1

    if result.get("errors"):
        print(json.dumps(result["errors"], indent=2), file=sys.stderr)
        return 1
    print(json.dumps(result["data"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
