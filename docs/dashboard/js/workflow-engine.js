/** Client-side Student Signal → Evidence → Action → Verification engine (Challenge 02) */

const CONF = ["Verified", "Likely", "Inferred", "Conflicting", "Missing", "Needs inspection"];

function classifyIssue(text) {
  const l = text.toLowerCase();
  if (/bathroom|restroom|drain|sewer|plumb|sink|flood|leak|water/.test(l))
    return { cat: "plumbing", label: "Plumbing / sanitary / drainage", severity: "high" };
  if (/hot|cold|heat|hvac|air|temperature|steam|vent/.test(l))
    return { cat: "hvac", label: "HVAC / comfort / ventilation", severity: "medium" };
  if (/electric|panel|power|breaker|outlet|spark/.test(l))
    return { cat: "electrical", label: "Electrical / safety", severity: "high" };
  if (/fire|alarm|sprinkler|egress|extinguisher|smoke/.test(l))
    return { cat: "fire_and_life_safety", label: "Fire / life safety", severity: "critical" };
  if (/elevator|lift|ada/.test(l)) return { cat: "general", label: "Elevator / accessibility", severity: "high" };
  return { cat: "general", label: "General facility issue", severity: "medium" };
}

function parseLocation(text) {
  const l = text.toLowerCase();
  const parts = ["240 2nd Avenue"];
  const fm = l.match(/(\d+)(?:st|nd|rd|th)[-\s]floor|floor\s*(\d+)/);
  if (fm) parts.push(`Floor ${fm[1] || fm[2]}`);
  if (/bathroom|restroom/.test(l)) parts.push("bathroom");
  if (/gym/.test(l)) parts.push("near gym");
  const rm = l.match(/room\s*(\d+)/);
  if (rm) parts.push(`room ${rm[1]}`);
  return { location: parts.join(" · "), confidence: fm ? "Inferred" : "Likely" };
}

function matchWorkOrder(text, workOrders) {
  const { cat } = classifyIssue(text);
  const l = text.toLowerCase();
  let best = null, score = 0;
  for (const wo of workOrders) {
    const blob = `${wo.title} ${wo.description || ""} ${wo.workOrderServiceCategory || ""}`.toLowerCase();
    let s = wo.workOrderServiceCategory === cat ? 3 : 0;
    for (const kw of l.match(/[a-z]{4,}/g) || []) if (blob.includes(kw)) s++;
    if (s > score) { score = s; best = wo; }
  }
  return score >= 3 ? { wo: best, confidence: "Inferred" } : { wo: null, confidence: "Missing" };
}

function enrichPublic(issueCat, publicData) {
  const hits = [];
  const src = publicData?.sources || {};
  for (const row of (src["311_service_requests"] || []).slice(0, 25)) {
    const ct = (row.complaint_type || "").toLowerCase();
    if (issueCat === "plumbing" && /plumb|water|sewer|leak/.test(ct))
      hits.push({ source: "NYC 311", detail: row.complaint_type, address: row.incident_address, status: row.status, meaning: "Area plumbing/water complaints — strengthens habitability signal" });
    if (issueCat === "hvac" && /heat|hvac|vent/.test(ct))
      hits.push({ source: "NYC 311", detail: row.complaint_type, address: row.incident_address, status: row.status, meaning: "Area HVAC/heat complaints — check BMS zone and recurrence" });
  }
  for (const row of (src.hpd_violations || []).slice(0, 8)) {
    hits.push({ source: "HPD", detail: row.novdescription || row.class || "Violation", meaning: "Manhattan HPD record — review habitability / compliance context before closure" });
  }
  return hits.slice(0, 5);
}

function complianceFor(text, rules) {
  const l = text.toLowerCase();
  for (const r of rules || []) {
    if (r.match.some((kw) => l.includes(kw)))
      return { ...r, confidence: "Likely" };
  }
  return { id: "general", obligations: ["General facilities SOP"], confidence: "Missing" };
}

function structureFieldSignal(text, workOrders, publicData, complianceRules, meta = {}) {
  const { cat, label, severity: baseSev } = classifyIssue(text);
  const loc = parseLocation(text);
  const link = matchWorkOrder(text, workOrders);
  const comp = complianceFor(text, complianceRules?.rules);
  const publicHits = enrichPublic(cat, publicData);
  const still = !/fixed|resolved|better/.test(text.toLowerCase());
  const duration = /two weeks|2 weeks/.test(text.toLowerCase()) ? "2+ weeks" : /days|monday/.test(text.toLowerCase()) ? "multi-day" : "unknown";
  let severity = baseSev;
  if (duration === "2+ weeks" && cat === "plumbing") severity = "high";

  const missing = [];
  if (loc.confidence !== "Verified") missing.push("Exact room / asset tag");
  if (!meta.photo) missing.push("Photo evidence");
  if (!link.wo) missing.push("Linked work order");

  const cleaned = `${loc.location}: ${label}. Student: "${text}". Duration ${duration}. Still happening: ${still}. ${comp.inspection || "Facilities inspection recommended."}`;

  return {
    rawSignal: text,
    issueType: cat,
    issueLabel: label,
    location: loc.location,
    locationConfidence: loc.confidence,
    severity,
    urgency: severity === "critical" || (severity === "high" && still) ? "same_day" : "scheduled",
    affectedUsers: /student|class|teacher/.test(text.toLowerCase()) ? "Students and staff" : "Building occupants",
    duration,
    stillHappening: still,
    evidenceQuality: meta.photo ? "Verified" : "Missing",
    linkedWorkOrder: link.wo ? { id: link.wo.id, title: link.wo.title } : null,
    linkConfidence: link.confidence,
    publicEnrichment: publicHits,
    compliance: {
      obligations: comp.obligations,
      escalateIf: comp.escalateIf || [],
      inspection: comp.inspection,
      agency: comp.agency,
      confidence: comp.confidence,
    },
    missingInformation: missing,
    followUpQuestions: [
      "Is water still present or spreading?",
      "Which fixtures are affected?",
      "Known shutoff location?",
      "Reported before?",
    ],
    cleanedDescription: cleaned,
    recommendedAction: link.wo
      ? `Enrich WO "${link.wo.title}" — attach student evidence, verify ${comp.inspection || "inspection"}, check ${comp.agency || "vendor"} path`
      : `Create corrective maintenance WO — ${label}; dispatch ${comp.agency || "facilities"}`,
    assignmentGroup: { hvac: "HVAC", plumbing: "Plumbing", electrical: "Electrical", fire_and_life_safety: "Life safety" }[cat] || "Facilities ops",
    escalate: /electrical|fire|elevator|sewage|flood|weeks/.test(text.toLowerCase()),
    studentStatusMessage: "Signal received and structured. Facilities review recommended.",
    closureVerificationQuestion: "Did this actually get fixed?",
    confidenceLabels: { location: loc.confidence, issue: "Likely", link: link.confidence, public: publicHits.length ? "Verified" : "Missing", compliance: comp.confidence },
  };
}

function saveClosure(workOrderId, status, structured) {
  const key = "team12_closure_log";
  const log = JSON.parse(localStorage.getItem(key) || "[]");
  log.push({ at: new Date().toISOString(), workOrderId, status, structured });
  localStorage.setItem(key, JSON.stringify(log));
  return log;
}

function downloadPayload(structured, action) {
  const blob = new Blob([JSON.stringify({ action, structured }, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `signal_${Date.now()}.json`;
  a.click();
}

window.WorkflowEngine = { structureFieldSignal, saveClosure, downloadPayload, CONF };
