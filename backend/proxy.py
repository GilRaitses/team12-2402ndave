#!/usr/bin/env python3
"""
Minimal GraphQL proxy for local dashboard development.
Never expose CA_CLIENT_SECRET to the browser.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib import request as urlrequest

ROOT = Path(__file__).resolve().parents[1]


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
    tok_path = ROOT / "data" / ".token"
    if not tok_path.exists():
        subprocess.check_call([sys.executable, str(ROOT / "scripts" / "auth.py")])
    tok = json.loads(tok_path.read_text())
    return tok["accessToken"]


class Handler(BaseHTTPRequestHandler):
    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors()
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/graphql":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        api = os.environ["CA_API_URL"]
        req = urlrequest.Request(
            api,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {bearer()}",
            },
            method="POST",
        )
        with urlrequest.urlopen(req, timeout=60) as resp:
            payload = resp.read()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[proxy] {self.address_string()} - {fmt % args}")


def main() -> None:
    load_dotenv()
    port = int(os.environ.get("PROXY_PORT", "8787"))
    print(f"CriticalAsset proxy on http://127.0.0.1:{port}/graphql")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
