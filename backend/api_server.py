#!/usr/bin/env python3
"""Demo API server: static dashboard + live CriticalAsset + OpenAI structuring."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import parse, request as urlrequest
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from ai_structure import structure_signal  # noqa: E402
from enrich_public import filter_for_category, main as enrich_main  # noqa: E402
from queries import WORK_ORDERS  # noqa: E402

DATA = ROOT / "data"
CLOSURE_LOG = DATA / "closure_log.json"


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


def bearer() -> str:
    tok_path = DATA / ".token"
    if not tok_path.exists():
        subprocess.check_call([sys.executable, str(ROOT / "scripts" / "auth.py")], cwd=ROOT)
    return json.loads(tok_path.read_text())["accessToken"]


def ca_gql(query: str, variables: dict | None = None) -> dict:
    api = os.environ["CA_API_URL"]
    body: dict = {"query": query}
    if variables:
        body["variables"] = variables
    req = urlrequest.Request(
        api,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {bearer()}"},
        method="POST",
    )
    with urlrequest.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode())


def normalize_work_orders(raw: dict) -> dict:
    nodes = raw.get("data", {}).get("workOrders", {}).get("nodes", [])
    for wo in nodes:
        title = wo.get("title") or ""
        wo["_source"] = "hackathon_test" if title.startswith("Student Signal:") else "portfolio"
        assets = wo.get("workOrderAssets") or []
        wo["asset"] = assets[0]["asset"] if assets else None
        wo["assignees"] = []
    return raw


def user_id() -> str:
    tok = bearer()
    payload = tok.split(".")[1] + "=="
    return json.loads(base64.urlsafe_b64decode(payload))["userId"]


def load_json(path: Path) -> dict | list:
    return json.loads(path.read_text()) if path.exists() else {}


def append_closure(entry: dict) -> None:
    rows = load_json(CLOSURE_LOG) if CLOSURE_LOG.exists() else []
    if not isinstance(rows, list):
        rows = []
    rows.append(entry)
    CLOSURE_LOG.write_text(json.dumps(rows, indent=2))


class Handler(BaseHTTPRequestHandler):
    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode())

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/health":
            self._json(200, {"ok": True, "mode": "live", "time": int(time.time())})
            return
        if path == "/api/live/workorders":
            try:
                raw = ca_gql(WORK_ORDERS, {"limit": 100, "offset": 0})
                raw = normalize_work_orders(raw)
                self._json(200, {"fetchedAt": time.time(), **raw})
            except Exception as exc:
                cached = load_json(DATA / "workorders.json")
                self._json(200, {"fetchedAt": time.time(), "cached": True, "error": str(exc), **cached})
            return
        if path.startswith("/api/public/enrich"):
            qs = parse.parse_qs(urlparse(self.path).query)
            category = (qs.get("category") or ["general"])[0]
            pub = load_json(DATA / "public" / "nyc_open_data.json")
            hits = pub.get("enriched_hits") or pub.get("building_specific_hits") or []
            self._json(200, {"category": category, "hits": filter_for_category(hits, category)[:8]})
            return
        self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        body = self._read_json()

        if path == "/api/structure":
            signal = body.get("signal", "")
            wo_path = DATA / "workorders.json"
            work_orders = []
            if body.get("live"):
                try:
                    raw = ca_gql(WORK_ORDERS, {"limit": 100, "offset": 0})
                    work_orders = normalize_work_orders(raw).get("data", {}).get("workOrders", {}).get("nodes", [])
                except Exception:
                    pass
            if not work_orders and wo_path.exists():
                work_orders = load_json(wo_path).get("data", {}).get("workOrders", {}).get("nodes", [])
            pub = load_json(DATA / "public" / "nyc_open_data.json")
            rules = load_json(DATA / "compliance_rules.json").get("rules", [])
            structured = structure_signal(
                signal,
                work_orders,
                pub,
                rules,
                body.get("photoNote", ""),
                body.get("workOrderId"),
                use_llm=body.get("useLlm", True),
            )
            if body.get("workOrderId") and not structured.get("linkedWorkOrder"):
                w = next((x for x in work_orders if x["id"] == body["workOrderId"]), None)
                if w:
                    structured["linkedWorkOrder"] = {"id": w["id"], "title": w["title"]}
                    structured["linkConfidence"] = "Verified"
            orig = next((w for w in work_orders if structured.get("linkedWorkOrder") and w["id"] == structured["linkedWorkOrder"]["id"]), None)
            structured["originalDescription"] = (orig or {}).get("description", "")
            self._json(200, structured)
            return

        if path == "/api/record":
            structured = body.get("structured") or body
            try:
                result = self._record_to_ca(structured, update_only=body.get("updateOnly", False))
                append_closure({"at": int(time.time()), "action": result["action"], "workOrderId": result["workOrder"]["id"], "structured": structured})
                self._json(200, {"ok": True, **result})
            except Exception as exc:
                self._json(500, {"ok": False, "error": str(exc)})
            return

        if path == "/api/closure":
            wid = body.get("workOrderId")
            status = body.get("status", "still")
            structured = body.get("structured") or {}
            note = f"\n\n[Student closure verification: {status} @ {int(time.time())}]"
            desc = (structured.get("cleanedDescription") or "") + note
            try:
                raw = ca_gql(
                    "mutation U($input: UpdateWorkOrderInput!) { updateWorkOrder(input: $input) { id title description } }",
                    {"input": {"id": wid, "description": desc}},
                )
                wo = raw["data"]["updateWorkOrder"]
                append_closure({"at": int(time.time()), "action": "closure", "status": status, "workOrderId": wid})
                self._json(200, {"ok": True, "workOrder": wo})
            except Exception as exc:
                self._json(500, {"ok": False, "error": str(exc)})
            return

        if path == "/graphql":
            length = int(self.headers.get("Content-Length", 0))
            payload = self.rfile.read(length)
            req = urlrequest.Request(
                os.environ["CA_API_URL"],
                data=payload,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {bearer()}"},
                method="POST",
            )
            with urlrequest.urlopen(req, timeout=60) as resp:
                out = resp.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors()
            self.end_headers()
            self.wfile.write(out)
            return

        self.send_response(404)
        self.end_headers()

    def _record_to_ca(self, structured: dict, update_only: bool = False) -> dict:
        nodes = []
        wo_file = DATA / "workorders.json"
        if wo_file.exists():
            nodes = load_json(wo_file).get("data", {}).get("workOrders", {}).get("nodes", [])
        loc_id = nodes[0]["locationId"] if nodes else None
        if not loc_id:
            raise RuntimeError("No locationId")

        linked = structured.get("linkedWorkOrder")
        if linked and (update_only or structured.get("linkConfidence") == "Verified"):
            wid = linked["id"]
            desc = structured.get("cleanedDescription", "")
            raw = ca_gql(
                "mutation U($input: UpdateWorkOrderInput!) { updateWorkOrder(input: $input) { id title description severity workOrderStage { name } } }",
                {"input": {"id": wid, "description": desc}},
            )
            return {"action": "updateWorkOrder", "workOrder": raw["data"]["updateWorkOrder"]}

        cat = structured.get("issueType", "general")
        if cat not in {"hvac", "electrical", "plumbing", "fire_and_life_safety", "general"}:
            cat = "general"
        raw = ca_gql(
            "mutation C($input: CreateWorkOrderInput!) { createWorkOrder(input: $input) { id title description severity workOrderStage { name } } }",
            {
                "input": {
                    "title": f"Student Signal: {(structured.get('issueLabel') or 'Issue')[:50]}",
                    "description": structured.get("cleanedDescription", ""),
                    "severity": structured.get("severity", "medium"),
                    "locationId": loc_id,
                    "workOrderType": "corrective_maintenance",
                    "workOrderServiceCategory": cat,
                    "executionPriority": structured.get("severity", "medium"),
                    "workOrderAssignments": [{"userIds": [user_id()], "assignmentType": "responsible"}],
                }
            },
        )
        return {"action": "createWorkOrder", "workOrder": raw["data"]["createWorkOrder"]}

    def _serve_static(self, path: str) -> None:
        if path in ("/", ""):
            path = "/dashboard/index.html"
        if path == "/submission.html":
            rel = ROOT / "docs" / "submission.html"
        elif path.startswith("/dashboard/"):
            rel = ROOT / path.lstrip("/")
        elif path.startswith("/data/"):
            rel = ROOT / path.lstrip("/")
        elif path.startswith("/docs/"):
            rel = ROOT / path.lstrip("/")
        else:
            rel = ROOT / path.lstrip("/")

        if not rel.exists() or not rel.is_file():
            self.send_response(404)
            self.end_headers()
            return
        ctype, _ = mimetypes.guess_type(str(rel))
        body = rel.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[api] {self.address_string()} - {fmt % args}")


def main() -> None:
    load_dotenv()
    port = int(os.environ.get("API_PORT", os.environ.get("PROXY_PORT", "8787")))
    print(f"Team 12 demo server: http://127.0.0.1:{port}/dashboard/")
    print(f"  Workflow: http://127.0.0.1:{port}/dashboard/workflow.html")
    print(f"  Submission: http://127.0.0.1:{port}/submission.html")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
