const DATA_BASE = document.body.dataset.dataBase || "../data";
let workOrders = [];
let publicData = {};
let complianceRules = {};
let lastStructured = null;
let selectedWoId = null;

async function loadJson(path) {
  const r = await fetch(`${DATA_BASE}/${path}`);
  if (!r.ok) throw new Error(path);
  return r.json();
}

function esc(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function renderStructured(s) {
  const el = document.getElementById("structured-out");
  el.innerHTML = `<dl class="field-grid">
    <dt>Issue</dt><dd>${esc(s.issueLabel)} <span class="label">${s.confidenceLabels.issue}</span></dd>
    <dt>Location</dt><dd>${esc(s.location)} <span class="label">${s.locationConfidence}</span></dd>
    <dt>Severity / urgency</dt><dd>${esc(s.severity)} / ${esc(s.urgency)}</dd>
    <dt>Affected</dt><dd>${esc(s.affectedUsers)}</dd>
    <dt>Duration</dt><dd>${esc(s.duration)} · still happening: ${s.stillHappening}</dd>
    <dt>Linked WO</dt><dd>${s.linkedWorkOrder ? esc(s.linkedWorkOrder.title) : "None"} <span class="label">${s.linkConfidence}</span></dd>
    <dt>Missing</dt><dd>${s.missingInformation.map(esc).join(", ") || "—"}</dd>
    <dt>Follow-up</dt><dd><ul>${s.followUpQuestions.map((q)=>`<li>${esc(q)}</li>`).join("")}</ul></dd>
  </dl>`;
}

function renderPublic(s) {
  const el = document.getElementById("public-out");
  if (!s.publicEnrichment.length) {
    el.innerHTML = '<p class="muted">No matching public records in cached East Village pull. Re-run scripts/enrich_public.py.</p>';
    return;
  }
  el.innerHTML = s.publicEnrichment.map((h) =>
    `<div class="pub-row"><strong>${esc(h.source)}</strong> — ${esc(h.detail || h.type || "")}<br/>
    <span class="muted">${esc(h.address || "")} ${esc(h.status || "")}</span><br/>${esc(h.meaning)}</div>`
  ).join("");
}

function renderWorkflow(s) {
  const el = document.getElementById("workflow-out");
  el.innerHTML = `
    <dl class="field-grid">
      <dt>Cleaned description</dt><dd>${esc(s.cleanedDescription)}</dd>
      <dt>Obligations</dt><dd>${(s.compliance.obligations||[]).map(esc).join("; ")} <span class="label">${s.compliance.confidence}</span></dd>
      <dt>Inspection</dt><dd>${esc(s.compliance.inspection || "—")}</dd>
      <dt>Agency path</dt><dd>${esc(s.compliance.agency || "Facilities")}</dd>
      <dt>Assignment</dt><dd>${esc(s.assignmentGroup)}</dd>
      <dt>Next action</dt><dd><strong>${esc(s.recommendedAction)}</strong></dd>
      <dt>Student message</dt><dd>${esc(s.studentStatusMessage)}</dd>
    </dl>
    ${s.escalate ? '<p class="escalate">⚠ Escalation recommended — safety, recurrence, or compliance trigger</p>' : ""}`;
}

async function init() {
  const [wo, pub, comp] = await Promise.all([
    loadJson("workorders.json"),
    loadJson("public/nyc_open_data.json").catch(() => ({})),
    loadJson("compliance_rules.json").catch(() => ({})),
  ]);
  workOrders = wo.data?.workOrders?.nodes || [];
  publicData = pub;
  complianceRules = comp;

  const sel = document.getElementById("wo-select");
  workOrders.forEach((w) => {
    const o = document.createElement("option");
    o.value = w.id;
    o.textContent = `${w.title} (${w.workOrderServiceCategory})`;
    sel.appendChild(o);
  });

  sel.addEventListener("change", () => {
    selectedWoId = sel.value || null;
    const w = workOrders.find((x) => x.id === selectedWoId);
    document.getElementById("wo-preview").innerHTML = w
      ? `<strong>Weak data check:</strong> ${(w.description || "").length < 80 ? "Short description — good candidate" : "Has description"}.<br/>${esc(w.description || "")}`
      : "No selection";
  });
}

document.getElementById("btn-structure").addEventListener("click", () => {
  const text = document.getElementById("signal-input").value.trim();
  if (!text) return;
  const photo = document.getElementById("photo-note").value.trim();
  let structured = WorkflowEngine.structureFieldSignal(text, workOrders, publicData, complianceRules, { photo });
  if (selectedWoId) {
    const w = workOrders.find((x) => x.id === selectedWoId);
    if (w) structured.linkedWorkOrder = { id: w.id, title: w.title };
    structured.linkConfidence = "Verified";
  }
  if (!document.getElementById("still-happening").checked) structured.stillHappening = false;
  lastStructured = structured;
  document.getElementById("results").classList.remove("hidden");
  renderStructured(structured);
  renderPublic(structured);
  renderWorkflow(structured);
  document.querySelectorAll(".step").forEach((s) => s.classList.add("active"));
});

document.getElementById("btn-download").addEventListener("click", () => {
  if (lastStructured) WorkflowEngine.downloadPayload(lastStructured, "record");
});

document.getElementById("btn-record").addEventListener("click", () => {
  if (!lastStructured) return;
  WorkflowEngine.downloadPayload(lastStructured, "record");
  const cmd = document.getElementById("record-cmd");
  cmd.classList.remove("hidden");
  const q = lastStructured.rawSignal.replace(/"/g, '\\"');
  cmd.textContent = `python3 scripts/record_signal.py "${q}"` +
    (lastStructured.linkedWorkOrder ? `  # links to ${lastStructured.linkedWorkOrder.id}` : "");
});

document.querySelectorAll("[data-closure]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const status = btn.dataset.closure;
    const woId = lastStructured?.linkedWorkOrder?.id || selectedWoId || "unlinked";
    const log = WorkflowEngine.saveClosure(woId, status, lastStructured);
    const out = document.getElementById("closure-out");
    out.innerHTML = `Recorded locally (${status}). ${log.length} closure events in browser log.<br/>
      Server write: <code>python3 scripts/record_signal.py --update-id ${woId} --closure ${status} --file signal.json</code>`;
  });
});

init().catch((e) => console.error(e));
