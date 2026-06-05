#!/usr/bin/env python3
"""Hydrate building-specific NYC Open Data for 240 2nd Avenue."""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "public" / "nyc_open_data.json"

BUILDING = "240 2nd Avenue"
ADDRESS = "240 2nd Ave, New York, NY 10003"
LAT, LON = 40.7326568, -73.9844033
RADIUS_M = 250


def fetch_dataset(base: str, params: dict) -> list:
    url = base + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read())
    return data if isinstance(data, list) else []


def _safe_fetch(base: str, params: dict) -> list:
    try:
        return fetch_dataset(base, params)
    except Exception as exc:
        print(f"Warning: {base} failed: {exc}", file=__import__("sys").stderr)
        return []


def geosearch_bbl() -> str | None:
    q = urllib.parse.quote(f"{ADDRESS}")
    url = f"https://geosearch.planninglabs.nyc/v2/search?text={q}&size=1"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            hits = json.loads(resp.read()).get("features", [])
        if hits:
            return hits[0]["properties"].get("addendum", {}).get("pad", {}).get("bbl")
    except Exception:
        pass
    return None


def operational_meaning(category: str, row: dict, source: str) -> str:
    ctype = (row.get("complaint_type") or row.get("violationtype") or row.get("novdescription") or "").lower()
    addr = row.get("incident_address") or row.get("house_number", "") + " " + (row.get("street_name") or "")
    if source == "311_geo":
        if category == "plumbing" and any(x in ctype for x in ["plumb", "water", "sewer", "leak"]):
            return f"Within {RADIUS_M}m of 240 2nd Ave: {row.get('complaint_type')} at {addr} supports habitability/plumbing concern for operator triage."
        if category == "hvac" and any(x in ctype for x in ["heat", "hvac", "vent", "hot"]):
            return f"Nearby heat/HVAC 311 at {addr} — check if same zone/BMS as reported student comfort issue."
        return f"Area 311 ({row.get('complaint_type')}) near building — contextual, verify relevance to 240 2nd Ave."
    if source == "311_address":
        return f"311 record at building address: {row.get('complaint_type')} — direct public evidence for this site."
    if source == "hpd":
        return f"HPD violation ({row.get('class', row.get('violationclass', ''))}): {row.get('novdescription', 'habitability')} — review before closing related work order."
    if source == "dob":
        return f"DOB/ECB record: {row.get('violation_type', row.get('description', 'violation'))} — may affect compliance path for facilities."
    return "Public record near 240 2nd Avenue — operator should verify operational relevance."


def annotate(rows: list, source: str, category: str | None = None) -> list:
    out = []
    for row in rows:
        cat = category or _guess_category(row)
        out.append({
            **{k: v for k, v in row.items() if k != "location"},
            "source": source,
            "operational_meaning": operational_meaning(cat, row, source),
            "relevance": "building_specific" if source in ("311_address", "311_geo") else "area_context",
        })
    return out


def _guess_category(row: dict) -> str:
    text = json.dumps(row).lower()
    if any(x in text for x in ["plumb", "water", "sewer", "leak", "sanitary"]):
        return "plumbing"
    if any(x in text for x in ["heat", "hvac", "vent", "hot water"]):
        return "hvac"
    if any(x in text for x in ["electric", "wiring"]):
        return "electrical"
    return "general"


def filter_for_category(hits: list, category: str) -> list:
    if category == "plumbing":
        return [h for h in hits if any(x in (h.get("operational_meaning", "") + json.dumps(h)).lower() for x in ["plumb", "water", "sewer", "leak", "sanitary", "habitability"])]
    if category == "hvac":
        return [h for h in hits if any(x in (h.get("operational_meaning", "") + json.dumps(h)).lower() for x in ["heat", "hvac", "vent", "comfort", "hot"])]
    return hits


def main() -> int:
    bbl = geosearch_bbl()

    geo_311 = fetch_dataset(
        "https://data.cityofnewyork.us/resource/erm2-nwe9.json",
        {
            "$limit": 20,
            "$order": "created_date DESC",
            "$where": f"within_circle(location, {LAT}, {LON}, {RADIUS_M})",
        },
    )

    addr_311 = fetch_dataset(
        "https://data.cityofnewyork.us/resource/erm2-nwe9.json",
        {
            "$limit": 15,
            "$order": "created_date DESC",
            "$where": "upper(incident_address) like '%240%' AND upper(incident_address) like '%2%' AND upper(incident_address) like '%AVE%'",
        },
    )

    hpd = _safe_fetch(
        "https://data.cityofnewyork.us/resource/wvxf-dwi5.json",
        {"$limit": 15, "$order": "novissueddate DESC", "$where": "boro='MANHATTAN'"},
    )

    dob = _safe_fetch(
        "https://data.cityofnewyork.us/resource/3h2n-5cm9.json",
        {"$limit": 10, "$order": "issue_date DESC", "$where": "boro='MANHATTAN'"},
    )

    all_hits = (
        annotate(geo_311, "311_geo")
        + annotate(addr_311, "311_address")
        + annotate(hpd, "hpd")
        + annotate(dob, "dob")
    )

    building_specific = [h for h in all_hits if h.get("relevance") == "building_specific" or h.get("source") == "311_address"]

    payload = {
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "building": BUILDING,
        "address": ADDRESS,
        "coordinates": [LAT, LON],
        "bbl": bbl,
        "radiusMeters": RADIUS_M,
        "sources": {
            "311_geospatial": geo_311,
            "311_address_match": addr_311,
            "hpd_violations": hpd,
            "dob_ecb_violations": dob,
        },
        "enriched_hits": all_hits,
        "building_specific_hits": building_specific,
        "summary": {
            "311_geo_count": len(geo_311),
            "311_address_count": len(addr_311),
            "hpd_count": len(hpd),
            "dob_count": len(dob),
            "building_specific_count": len(building_specific),
            "total_enriched": len(all_hits),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
