#!/usr/bin/env python3
"""Structure messy field observations into operational issue records."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def classify_issue(text: str) -> tuple[str, str, str]:
    lower = text.lower()
    if re.search(r"bathroom|restroom|toilet|drain|sewer|plumb|sink|flood|leak|water", lower):
        return "plumbing", "Plumbing / sanitary / drainage", "high"
    if re.search(r"hot|cold|heat|hvac|air|temperature|steam|vent", lower):
        return "hvac", "HVAC / comfort / ventilation", "medium"
    if re.search(r"electric|panel|power|breaker|outlet|spark", lower):
        return "electrical", "Electrical / safety", "high"
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
            room = f"room {rm[1]}"
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
    cat, _, _ = classify_issue(text)
    for wo in work_orders:
        blob = f"{wo.get('title','')} {wo.get('description','')} {wo.get('workOrderServiceCategory','')}".lower()
        s = 3 if wo.get("workOrderServiceCategory") == cat else 0
        for kw in re.findall(r"[a-z]{4,}", lower):
            if kw in blob:
                s += 1
        if s > score:
            score, best = s, wo
    if best and score >= 3:
        return best, "Inferred"
    return None, "Missing"


def enrich_public(issue_type: str, public_data: dict) -> list[dict]:
    hits = public_data.get("enriched_hits") or public_data.get("building_specific_hits") or []
    if not hits:
        sources = public_data.get("sources", {})
        for key in ("311_geospatial", "311_address_match", "311_service_requests"):
            for row in sources.get(key, [])[:15]:
                hits.append({**row, "source": key, "operational_meaning": row.get("operational_meaning", "Area public record")})

    filtered = []
    for h in hits:
        meaning = (h.get("operational_meaning") or "").lower()
        blob = json.dumps(h).lower()
        if issue_type == "plumbing" and any(x in meaning + blob for x in ["plumb", "water", "sewer", "leak", "sanitary", "habitability"]):
            filtered.append({
                "source": h.get("source", "NYC Open Data"),
                "detail": h.get("complaint_type") or h.get("novdescription") or h.get("violation_type"),
                "address": h.get("incident_address") or h.get("house_number"),
                "status": h.get("status"),
                "meaning": h.get("operational_meaning"),
            })
        elif issue_type == "hvac" and any(x in meaning + blob for x in ["heat", "hvac", "vent", "hot", "comfort"]):
            filtered.append({
                "source": h.get("source", "NYC Open Data"),
                "detail": h.get("complaint_type") or h.get("novdescription"),
                "address": h.get("incident_address"),
                "status": h.get("status"),
                "meaning": h.get("operational_meaning"),
            })
        elif issue_type == "general" and h.get("relevance") == "building_specific":
            filtered.append({
                "source": h.get("source"),
                "detail": h.get("complaint_type") or h.get("novdescription"),
                "meaning": h.get("operational_meaning"),
            })
    return filtered[:5]


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


def structure_signal_rules(
    text: str,
    work_orders: list | None = None,
    public_data: dict | None = None,
    compliance_rules: list | None = None,
    photo_note: str = "",
    work_order_id: str | None = None,
) -> dict:
    work_orders = work_orders or []
    cat, issue_label, default_sev = classify_issue(text)
    location, loc_conf = parse_location(text)
    timing = parse_timing(text)
    linked, link_conf = match_work_order(text, work_orders)

    if work_order_id:
        linked = next((w for w in work_orders if w.get("id") == work_order_id), linked)
        if linked:
            link_conf = "Verified"

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

    escalate = any(trig in text.lower() for trig in ["electrical", "fire", "elevator", "sewage", "flood", "weeks"])

    return _finalize(
        text, cat, issue_label, location, loc_conf, severity, timing, evidence,
        linked, link_conf, missing, public_hits, comp, escalate, cleaned,
        aiEngine="fallback_rules",
    )


def structure_signal_llm(
    text: str,
    work_orders: list | None = None,
    public_data: dict | None = None,
    compliance_rules: list | None = None,
    photo_note: str = "",
    work_order_id: str | None = None,
) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("sk-your"):
        return structure_signal_rules(text, work_orders, public_data, compliance_rules, photo_note, work_order_id)

    work_orders = work_orders or []
    cat, _, _ = classify_issue(text)
    public_hits = enrich_public(cat, public_data or {})
    wo_summary = [{"id": w["id"], "title": w["title"], "category": w.get("workOrderServiceCategory"), "description": (w.get("description") or "")[:200]} for w in work_orders[:10]]

    prompt = f"""You structure student facility observations for building operators at 240 2nd Avenue NYC.
Return ONLY valid JSON with these keys:
issueType, issueLabel, location, locationConfidence, severity (low|medium|high|critical),
urgency (same_day|scheduled), affectedUsers, duration, stillHappening (bool),
linkedWorkOrderId (or null), linkConfidence, missingInformation (array), followUpQuestions (array),
cleanedDescription, recommendedAction, assignmentGroup, escalate (bool),
confidenceLabels (object with location, issue, link, publicData, compliance each Verified|Likely|Inferred|Missing),
studentStatusMessage, closureVerificationQuestion.

Rules: Never mark Verified without explicit evidence. Photo note: {photo_note or 'none'}.
Work orders: {json.dumps(wo_summary)}
Public evidence: {json.dumps(public_hits[:3])}
Selected work order id: {work_order_id or 'none'}
Student signal: {text}"""

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": "You output only JSON for facilities operations. No legal advice."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }).encode()

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read())
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except Exception as exc:
        result = structure_signal_rules(text, work_orders, public_data, compliance_rules, photo_note, work_order_id)
        result["aiEngine"] = "fallback_rules"
        result["aiError"] = str(exc)[:200]
        return result

    linked = None
    lid = parsed.get("linkedWorkOrderId") or work_order_id
    if lid:
        linked = next((w for w in work_orders if w["id"] == lid), None)

    comp = compliance_context(text, compliance_rules or [])
    return {
        "structuredAt": datetime.now(timezone.utc).isoformat(),
        "rawSignal": text,
        "issueType": parsed.get("issueType", cat),
        "issueLabel": parsed.get("issueLabel", classify_issue(text)[1]),
        "location": parsed.get("location", "240 2nd Avenue"),
        "locationConfidence": parsed.get("locationConfidence", "Inferred"),
        "severity": parsed.get("severity", "medium"),
        "urgency": parsed.get("urgency", "scheduled"),
        "affectedUsers": parsed.get("affectedUsers", "Building occupants"),
        "duration": parsed.get("duration", "unknown"),
        "stillHappening": parsed.get("stillHappening", True),
        "timing": parse_timing(text),
        "evidence": [{"type": "note", "value": photo_note, "confidence": "Verified"}] if photo_note else [{"type": "photo", "value": "Not provided", "confidence": "Missing"}],
        "linkedWorkOrder": {"id": linked["id"], "title": linked["title"]} if linked else None,
        "linkConfidence": parsed.get("linkConfidence", "Missing"),
        "missingInformation": parsed.get("missingInformation", []),
        "followUpQuestions": parsed.get("followUpQuestions", []),
        "publicEnrichment": public_hits,
        "compliance": comp,
        "escalate": parsed.get("escalate", False),
        "cleanedDescription": parsed.get("cleanedDescription", ""),
        "recommendedAction": parsed.get("recommendedAction", ""),
        "assignmentGroup": parsed.get("assignmentGroup", "Facilities operations"),
        "studentStatusMessage": parsed.get("studentStatusMessage", "Signal received."),
        "closureVerificationQuestion": parsed.get("closureVerificationQuestion", "Did this actually get fixed?"),
        "confidenceLabels": parsed.get("confidenceLabels", {}),
        "aiEngine": "openai",
        "aiModel": model,
    }


def structure_signal(
    text: str,
    work_orders: list | None = None,
    public_data: dict | None = None,
    compliance_rules: list | None = None,
    photo_note: str = "",
    work_order_id: str | None = None,
    use_llm: bool = True,
) -> dict:
    if use_llm:
        return structure_signal_llm(text, work_orders, public_data, compliance_rules, photo_note, work_order_id)
    return structure_signal_rules(text, work_orders, public_data, compliance_rules, photo_note, work_order_id)


def _finalize(
    text, cat, issue_label, location, loc_conf, severity, timing, evidence,
    linked, link_conf, missing, public_hits, comp, escalate, cleaned, aiEngine,
) -> dict:
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
        "duration": timing["duration"],
        "stillHappening": timing["stillHappening"],
        "timing": timing,
        "evidence": evidence,
        "linkedWorkOrder": {"id": linked["id"], "title": linked["title"]} if linked else None,
        "linkConfidence": link_conf,
        "rootCauseCategories": [issue_label],
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
            f"Inspect {issue_label.lower()}; dispatch {comp.get('agency', 'facilities')}; "
            f"{'ESCALATE' if escalate else 'schedule within SLA'}"
        ),
        "assignmentGroup": {"hvac": "HVAC vendor", "plumbing": "Plumbing vendor", "electrical": "Electrical / BMS", "fire_and_life_safety": "Life safety officer"}.get(cat, "Facilities operations"),
        "studentStatusMessage": "We received your signal and linked it to facilities.",
        "closureVerificationQuestion": "Did the issue actually get fixed?",
        "confidenceLabels": {
            "location": loc_conf,
            "issue": "Likely",
            "link": link_conf,
            "publicData": "Verified" if public_hits else "Missing",
            "compliance": comp.get("confidence", "Likely"),
        },
        "aiEngine": aiEngine,
    }


def main() -> int:
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "The third-floor bathroom has been closed for two weeks. There is water near the sink."
    )
    print(json.dumps(structure_signal(text), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
