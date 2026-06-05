#!/usr/bin/env python3
"""Record a structured student signal to CriticalAsset (create or update work order)."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from ai_structure import structure_signal  # noqa: E402
from auth import exchange, load_dotenv  # noqa: E402

LOG = ROOT / "data" / "closure_log.json"


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
        return json.loads(resp.read())


def user_id_from_token(token: str) -> str:
    payload = token.split(".")[1] + "=="
    return json.loads(base64.urlsafe_b64decode(payload))["userId"]


def load_json(path: Path) -> dict | list:
    return json.loads(path.read_text())


def append_log(entry: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    rows = load_json(LOG) if LOG.exists() else []
    rows.append(entry)
    LOG.write_text(json.dumps(rows, indent=2))


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("signal", nargs="?", help="Raw student signal text")
    parser.add_argument("--file", help="JSON file with structured signal or rawSignal field")
    parser.add_argument("--update-id", help="Update existing work order instead of create")
    parser.add_argument("--closure", choices=["fixed", "still", "worse"], help="Closure verification")
    args = parser.parse_args()

    if args.file:
        payload = load_json(Path(args.file))
        structured = payload if "cleanedDescription" in payload else structure_signal(payload.get("rawSignal", ""))
    elif args.signal:
        wo_path = ROOT / "data" / "workorders.json"
        pub_path = ROOT / "data" / "public" / "nyc_open_data.json"
        comp_path = ROOT / "data" / "compliance_rules.json"
        work_orders = []
        if wo_path.exists():
            work_orders = load_json(wo_path).get("data", {}).get("workOrders", {}).get("nodes", [])
        public_data = load_json(pub_path) if pub_path.exists() else {}
        rules = load_json(comp_path).get("rules", []) if comp_path.exists() else []
        structured = structure_signal(args.signal, work_orders, public_data, rules)
    else:
        parser.print_help()
        return 1

    token = exchange()["accessToken"]
    uid = user_id_from_token(token)
    loc = structured.get("linkedWorkOrder") and None
    wo_path = ROOT / "data" / "workorders.json"
    if wo_path.exists():
        nodes = load_json(wo_path).get("data", {}).get("workOrders", {}).get("nodes", [])
        loc_id = nodes[0]["locationId"] if nodes else None
    else:
        loc_id = None

    if not loc_id:
        print("No locationId available", file=sys.stderr)
        return 1

    if args.update_id or structured.get("linkedWorkOrder"):
        wid = args.update_id or structured["linkedWorkOrder"]["id"]
        desc = structured["cleanedDescription"]
        if args.closure:
            desc += f"\n\n[Student closure verification: {args.closure} @ {int(time.time())}]"
        result = gql(
            "mutation U($input: UpdateWorkOrderInput!) { updateWorkOrder(input: $input) { id title description } }",
            {"input": {"id": wid, "description": desc}},
            token,
        )
        action = "updateWorkOrder"
    else:
        result = gql(
            "mutation C($input: CreateWorkOrderInput!) { createWorkOrder(input: $input) { id title description severity } }",
            {
                "input": {
                    "title": f"Student Signal: {structured['issueLabel'][:50]}",
                    "description": structured["cleanedDescription"],
                    "severity": structured["severity"],
                    "locationId": loc_id,
                    "workOrderType": "corrective_maintenance",
                    "workOrderServiceCategory": structured["issueType"] if structured["issueType"] in {
                        "hvac", "electrical", "plumbing", "fire_and_life_safety", "general"
                    } else "general",
                    "executionPriority": structured["severity"],
                    "workOrderAssignments": [{"userIds": [uid], "assignmentType": "responsible"}],
                }
            },
            token,
        )
        action = "createWorkOrder"

    if result.get("errors"):
        print(json.dumps(result["errors"], indent=2), file=sys.stderr)
        return 1

    wo = result["data"][action]
    append_log({"at": int(time.time()), "action": action, "workOrderId": wo["id"], "structured": structured, "closure": args.closure})
    print(json.dumps({"ok": True, "action": action, "workOrder": wo, "structured": structured}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
