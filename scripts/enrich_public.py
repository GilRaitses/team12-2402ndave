#!/usr/bin/env python3
"""Hydrate NYC Open Data context for 240 2nd Avenue (zip 10003 / East Village)."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "public" / "nyc_open_data.json"
ZIPS = ("10003", "10009", "10010")


def fetch_dataset(base: str, params: dict) -> list:
    url = base + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read())


def main() -> int:
    zip_clause = " OR ".join(f"incident_zip='{z}'" for z in ZIPS)
    sources = {
        "311_service_requests": fetch_dataset(
            "https://data.cityofnewyork.us/resource/erm2-nwe9.json",
            {
                "$limit": 25,
                "$order": "created_date DESC",
                "$where": zip_clause,
            },
        ),
        "hpd_violations": fetch_dataset(
            "https://data.cityofnewyork.us/resource/wvxf-dwi5.json",
            {
                "$limit": 15,
                "$order": "novissueddate DESC",
                "$where": "boro='MANHATTAN'",
            },
        ),
        "dob_ecb_violations": fetch_dataset(
            "https://data.cityofnewyork.us/resource/3h2n-5cm9.json",
            {
                "$limit": 15,
                "$order": "issue_date DESC",
                "$where": "boro='MANHATTAN'",
            },
        ),
    }
    payload = {
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "building": "240 2nd Avenue",
        "address": "240 2nd Ave, New York, NY 10003",
        "coordinates": [40.7326568, -73.9844033],
        "zipCodes": list(ZIPS),
        "sources": sources,
        "summary": {
            "311_count": len(sources["311_service_requests"]),
            "hpd_count": len(sources["hpd_violations"]),
            "dob_count": len(sources["dob_ecb_violations"]),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
