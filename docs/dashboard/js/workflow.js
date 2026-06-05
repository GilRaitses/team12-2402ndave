let workOrders = [];
let publicData = {};
let complianceRules = {};
let lastStructured = null;
let selectedWoId = null;

async function loadJson(path) {
  const r = await fetch(`${Api.dataBase()}/${path}`);
  if (!r.ok) throw new Error(path);
  return r.json();
}

function esc(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function aiBadge(s) {
  const engine = s.aiEngine || "fallback_rules";
  const label = engine === "openai" ? `AI: OpenAI (${s.aiModel || "gpt-4o-mini"})` : "AI: fallback rules";
  return `<span class="label ai-badge">${esc(label)}</span>`;
}

function renderStructured(s) {
  const el = document.getElementById("structured-out");
  const labels = s.confidenceLabels || {};
  el.innerHTML = `${aiBadge(s)}<dl class="field-grid">
    <dt>Issue</dt><dd>${esc(s.issueLabel)} <span class="label">${esc(labels.issue || "Likely")}</span></dd>
    <dt>Location</dt><dd>${esc(s.location)} <span class="label">${esc(s.locationConfidence || labels.location || "")}</span></dd>
    <dt>Severity / urgency</dt><dd>${esc(s.severity)} / ${esc(s.urgency)}</dd>
    <dt>Affected</dt><dd>${esc(s.affectedUsers || "Building occupants")}</dd>
    <dt>Duration</dt><dd>${esc(s.duration || s.timing?.duration || "unknown")} · still: ${s.stillHappening}</dd>
    <dt>Linked WO</dt><dd>${s.linkedWorkOrder ? esc(s.linkedWorkOrder.title) : "None"} <span class="label">${esc(s.linkConfidence)}</span></dd>
    <dt>Missing</dt><dd>${(s.missingInformation || []).map(esc).join(", ") || "—"}</dd>
    <dt>Follow-up</dt><dd><ul>${(s.followUpQuestions || []).map((q)=>`<li>${esc(q)}</li>`).join("")}</ul></dd>
  </dl>`;
}

function renderPublic(s) {
  const el = document.getElementById("public-out");
  if (!s.publicEnrichment?.length) {
    el.innerHTML = '<p class="muted">No building-specific public records matched. Area context may still apply.</p>';
    return;
  }
  el.innerHTML = s.publicEnrichment.map((h) =>
    `<div class="pub-row"><strong>${esc(h.source)}</strong> — ${esc(h.detail || h.type || "")}<br/>
    <span class="muted">${esc(h.address || "")} ${esc(h.status || "")}</span><br/>${esc(h.meaning)}</div>`
  ).join("");
}

function renderWorkflow(s) {
  const el = document.getElementById("workflow-out");
  const comp = s.compliance || {};
  el.innerHTML = `
    <div class="copilot-grid">
      <div class="copilot-col">
        <h3>Before (weak WO)</h3>
        <p class="muted copilot-before">${esc(s.originalDescription || "No linked work order description")}</p>
      </div>
      <div class="copilot-col">
        <h3>After (AI enriched)</h3>
        <p class="copilot-after">${esc(s.cleanedDescription)}</p>
      </div>
    </div>
    <dl class="field-grid">
      <dt>Obligations</dt><dd>${(comp.obligations||[]).map(esc).join("; ")} <span class="label">${esc(comp.confidence || "")}</span></dd>
      <dt>Inspection</dt><dd>${esc(comp.inspection || "—")}</dd>
      <dt>Agency path</dt><dd>${esc(comp.agency || "Facilities")}</dd>
      <dt>Assignment</dt><dd>${esc(s.assignmentGroup)}</dd>
      <dt>Next action</dt><dd><strong>${esc(s.recommendedAction)}</strong></dd>
      <dt>Student message</dt><dd>${esc(s.studentStatusMessage)}</dd>
    </dl>
    ${s.escalate ? '<p class="escalate">Escalation recommended — safety, recurrence, or compliance trigger</p>' : ""}`;
}

async function init() {
  const woResult = await Api.loadWorkOrders(true);
  workOrders = woResult.nodes;
  publicData = await loadJson("public/nyc_open_data.json").catch(() => ({}));
  complianceRules = await loadJson("compliance_rules.json").catch(() => ({}));

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
      ? `<strong>Weak data check:</strong> ${(w.description || "").length < 120 ? "Thin description — good copilot candidate" : "Has description"}.<br/>${esc(w.description || "")}`
      : "No selection";
  });
}

document.getElementById("btn-structure").addEventListener("click", async () => {
  const text = document.getElementById("signal-input").value.trim();
  if (!text || text.trim().length < 8) {
    alert("Enter a field observation (at least 8 characters).");
    return;
  }
  const photo = document.getElementById("photo-note").value.trim();
  const fileInput = document.getElementById("photo-file");
  let photoNote = photo;
  if (fileInput?.files?.[0]) {
    photoNote = (photo ? photo + " · " : "") + `Photo: ${fileInput.files[0].name}`;
  }

  const btn = document.getElementById("btn-structure");
  btn.disabled = true;
  btn.textContent = "Structuring…";

  let structured;
  try {
    structured = await Api.structure(text, selectedWoId, photoNote);
    if (!structured) {
      structured = WorkflowEngine.structureFieldSignal(text, workOrders, publicData, complianceRules, { photo: photoNote });
    }
    if (selectedWoId && !structured.linkedWorkOrder) {
      const w = workOrders.find((x) => x.id === selectedWoId);
      if (w) {
        structured.linkedWorkOrder = { id: w.id, title: w.title };
        structured.linkConfidence = "Verified";
        structured.originalDescription = w.description || "";
      }
    }
    if (!document.getElementById("still-happening").checked) structured.stillHappening = false;
    lastStructured = structured;
    document.getElementById("results").classList.remove("hidden");
    renderStructured(structured);
    renderPublic(structured);
    renderWorkflow(structured);
    document.querySelectorAll(".step").forEach((s) => s.classList.add("active"));
  } catch (e) {
    alert("Structure failed: " + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Structure with AI →";
  }
});

document.getElementById("btn-download").addEventListener("click", () => {
  if (lastStructured) WorkflowEngine.downloadPayload(lastStructured, "record");
});

document.getElementById("btn-record").addEventListener("click", async () => {
  if (!lastStructured) return;
  const desc = (lastStructured.cleanedDescription || lastStructured.rawSignal || "").trim();
  if (desc.length < 20) {
    alert("Structure a signal first — description too short to record.");
    return;
  }
  const btn = document.getElementById("btn-record");
  const cmd = document.getElementById("record-cmd");
  btn.disabled = true;
  btn.textContent = "Recording…";

  if (Api.isLive()) {
    try {
      const result = await Api.record(lastStructured);
      if (result.ok) {
        cmd.classList.remove("hidden");
        cmd.textContent = `Recorded in CriticalAsset: ${result.action} · ${result.workOrder.id}\n${result.workOrder.title}`;
        if (result.workOrder.id) lastStructured.linkedWorkOrder = { id: result.workOrder.id, title: result.workOrder.title };
      } else {
        cmd.classList.remove("hidden");
        cmd.textContent = `Error: ${result.error}`;
      }
    } catch (e) {
      cmd.classList.remove("hidden");
      cmd.textContent = `Error: ${e.message}`;
    }
  } else {
    WorkflowEngine.downloadPayload(lastStructured, "record");
    cmd.classList.remove("hidden");
    cmd.textContent = `Static mode: python3 scripts/record_signal.py "${lastStructured.rawSignal.replace(/"/g, '\\"')}"`;
  }
  btn.disabled = false;
  btn.textContent = Api.isLive() ? "Record to CriticalAsset" : "Download + record via script";
});

document.querySelectorAll("[data-closure]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const status = btn.dataset.closure;
    const woId = lastStructured?.linkedWorkOrder?.id || selectedWoId;
    const out = document.getElementById("closure-out");
    if (!woId) {
      out.innerHTML = "Link a work order first.";
      return;
    }
    if (Api.isLive()) {
      const result = await Api.closure(woId, status, lastStructured);
      if (result.ok) {
        out.innerHTML = `Closure <strong>${status}</strong> written to CriticalAsset WO ${woId.slice(0,8)}…`;
      } else {
        out.innerHTML = `Closure failed: ${result.error}`;
      }
    } else {
      WorkflowEngine.saveClosure(woId, status, lastStructured);
      out.innerHTML = `Recorded locally (${status}). Run: python3 scripts/record_signal.py --update-id ${woId} --closure ${status}`;
    }
  });
});

Api.showBanner();
init().catch((e) => console.error(e));
