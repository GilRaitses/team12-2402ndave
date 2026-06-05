#!/usr/bin/env python3
"""Structure messy field observations into operational issue records."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone


def classify_issue(text: str) -> tuple[str, str, str]:
    lower = text.lower()
    if re.search(r"bathroom|restroom|toilet|drain|sewer|plumb|sink|flood|leak|water", lower):
        return "plumbing", "Plumbing / sanitary / drainage", "high"
    if re.search(r"hot|cold|heat|hvac|air|temperature|steam|vent", lower):
        return "hvac", "HVAC / comfort / ventilation", "medium"
    if re.search(r"electric|panel|power|breaker|outlet|spark", lower):
        return "electrical", "Electrical distribution / safety", "high"
    if re.search(r"fire|alarm|sprinkler|egress|extinguisher|smoke", lower):
        return "fire_and_life_safety", "Fire / life safety", "critical"
    if re.search(r"elevator|lift|ada|wheelchair", lower):
        return "general", "Elevator / accessibility", "high"
    return "general", "General facility issue", "medium"


def parse_location(text: str) -> tuple[str, str]:
    lower = text.lower()
    floor = None
    m = re.search(r"(\d+)(?:st|nd|rd|th)[-\s]floor|floor\s*(\d+)", lower)
    if m:
        floor = m.group(1) or m.group(2)
    room = None
    if "bathroom" in lower or "restroom" in lower:
        room = "bathroom"
    if "gym" in lower:
        room = (room or "") + " near gym"
    if "classroom" in lower or "room" in lower:
        rm = re.search(r"room\s*(\d+)", lower)
        if rm:
            room = f"room {rm.group(1)}"
    parts = ["240 2nd Avenue"]
    if floor:
        parts.append(f"Floor {floor}")
    if room:
        parts.append(room.strip())
    loc = " · ".join(parts)
    conf = "Inferred" if floor or room else "Likely"
    return loc, conf


def parse_timing(text: str) -> dict:
    lower = text.lower()
    still = not re.search(r"fixed|resolved|better|stopped", lower)
    duration = "unknown"
    if re.search(r"two weeks|2 weeks", lower):
        duration = "2+ weeks"
    elif re.search(r"since monday|since yesterday|days", lower):
        duration = "multi-day"
    elif re.search(r"today|just now|this morning", lower):
        duration = "same day"
    return {"stillHappening": still, "duration": duration, "confidence": "Likely" if duration != "unknown" else "Missing"}


def match_work_order(text: str, work_orders: list) -> tuple[dict | None, str]:
    lower = text.lower()
    best, score = None, 0
    for wo in work_orders:
        blob = f"{wo.get('title','')} {wo.get('description','')} {wo.get('workOrderServiceCategory','')}".lower()
        s = 0
        cat, _, _ = classify_issue(text)
        if wo.get("workOrderServiceCategory") == cat:
            s += 3
        for kw in re.findall(r"[a-z]{4,}", lower):
            if kw in blob:
                s += 1
        if s > score:
            score, best = s, wo
    if best and score >= 3:
        return best, "Inferred"
    return None, "Missing"


def enrich_public(issue_type: str, public_data: dict) -> list[dict]:
    hits = []
    sources = public_data.get("sources", {})
    for row in sources.get("311_service_requests", [])[:25]:
        ctype = (row.get("complaint_type") or "").lower()
        if issue_type == "plumbing" and any(x in ctype for x in ["plumb", "water", "sewer", "leak"]):
            hits.append({"source": "NYC 311", "type": row.get("complaint_type"), "status": row.get("status"), "address": row.get("incident_address"), "meaning": "Nearby 311 pattern supports plumbing/habitability concern"})
        if issue_type == "hvac" and any(x in ctype for x in ["heat", "hvac", "vent"]):
            hits.append({"source": "NYC 311", "type": row.get("complaint_type"), "status": row.get("status"), "address": row.get("incident_address"), "meaning": "Area heat/HVAC complaints suggest systemic comfort risk — verify BMS and zone"})
    for row in sources.get("hpd_violations", [])[:10]:
        cls = (row.get("class") or row.get("violationclass") or "").lower()
        if issue_type == "plumbing" and "c" in cls:
            hits.append({"source": "HPD violation", "type": row.get("novdescription", "Class C"), "meaning": "Manhattan HPD Class C violations include conditions that may affect habitability"})
    return hits[:5]


def compliance_context(text: str, rules: list) -> dict:
    lower = text.lower()
    for rule in rules:
        if any(kw in lower for kw in rule["match"]):
            return {
                "ruleId": rule["id"],
                "obligations": rule["obligations"],
                "escalateIf": rule["escalateIf"],
                "inspection": rule["inspection"],
                "agency": rule["agency"],
                "confidence": "Likely",
            }
    return {"ruleId": None, "obligations": ["General facilities SOP review"], "confidence": "Missing"}


def structure_signal(
    text: str,
    work_orders: list | None = None,
    public_data: dict | None = None,
    compliance_rules: list | None = None,
    photo_note: str = "",
) -> dict:
    work_orders = work_orders or []
    cat, issue_label, default_sev = classify_issue(text)
    location, loc_conf = parse_location(text)
    timing = parse_timing(text)
    linked, link_conf = match_work_order(text, work_orders)

    evidence = []
    if photo_note:
        evidence.append({"type": "note", "value": photo_note, "confidence": "Verified"})
    else:
        evidence.append({"type": "photo", "value": "Not provided", "confidence": "Missing"})

    public_hits = enrich_public(cat, public_data or {})
    comp = compliance_context(text, compliance_rules or [])

    missing = []
    if loc_conf != "Verified":
        missing.append("Exact room/asset tag")
    if evidence[0]["confidence"] == "Missing":
        missing.append("Photo or vendor verification")
    if not linked:
        missing.append("Linked existing work order")

    severity = default_sev
    if timing["duration"] == "2+ weeks" and cat == "plumbing":
        severity = "high"
    if re.search(r"electrical|fire|elevator", text.lower()):
        severity = "critical" if "fire" in text.lower() else "high"

    cleaned = (
        f"{location}: {issue_label}. Student reports: \"{text}\". "
        f"Duration: {timing['duration']}. Still happening: {timing['stillHappening']}. "
        f"Recommended: {comp.get('inspection', 'Facilities inspection')}."
    )

    escalate = any(
        trig in text.lower() for trig in ["electrical", "fire", "elevator", "sewage", "flood", "weeks"]
    )

    return {
        "structuredAt": datetime.now(timezone.utc).isoformat(),
        "rawSignal": text,
        "issueType": cat,
        "issueLabel": issue_label,
        "location": location,
        "locationConfidence": loc_conf,
        "severity": severity,
        "urgency": "same_day" if severity in ("critical", "high") and timing["stillHappening"] else "scheduled",
        "affectedUsers": "Students and staff" if re.search(r"student|class|teacher", text.lower()) else "Building occupants",
        "timing": timing,
        "evidence": evidence,
        "linkedWorkOrder": {"id": linked["id"], "title": linked["title"]} if linked else None,
        "linkConfidence": link_conf,
        "rootCauseCategories": [issue_label, "Possible deferred maintenance" if timing["duration"] == "2+ weeks" else "Unknown pending inspection"],
        "missingInformation": missing,
        "followUpQuestions": [
            "Is water still present / spreading?",
            "Which fixture(s) affected?",
            "Is there a known shutoff location?",
            "Has this been reported before?",
        ],
        "publicEnrichment": public_hits,
        "compliance": comp,
        "escalate": escalate,
        "cleanedDescription": cleaned,
        "recommendedAction": (
            f"Inspect {issue_label.lower()}; link to asset; dispatch {comp.get('agency', 'facilities')}; "
            f"{'ESCALATE — safety/recurrence/compliance trigger' if escalate else 'schedule within normal SLA'}"
        ),
        "assignmentGroup": {"hvac": "HVAC vendor", "plumbing": "Plumbing vendor", "electrical": "Electrical / BMS", "fire_and_life_safety": "Life safety officer"}.get(cat, "Facilities operations"),
        "studentStatusMessage": "We received your signal and linked it to facilities. An inspection is recommended.",
        "closureVerificationQuestion": "Did the issue actually get fixed? (Yes / Still happening / Worse)",
        "confidenceLabels": {
            "location": loc_conf,
            "issue": "Likely",
            "link": link_conf,
            "publicData": "Verified" if public_hits else "Missing",
            "compliance": comp.get("confidence", "Likely"),
        },
    }


def main() -> int:
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "The third-floor bathroom has been closed for two weeks. There is water near the sink."
    )
    print(json.dumps(structure_signal(text), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
