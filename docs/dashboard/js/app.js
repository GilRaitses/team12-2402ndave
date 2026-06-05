const DATA_BASE = document.body.dataset.dataBase || "../data";

let workOrders = [];

async function loadData() {
  const status = document.getElementById("status");
  try {
    const res = await fetch(`${DATA_BASE}/workorders.json`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = await res.json();
    if (json.errors) throw new Error(json.errors[0]?.message || "GraphQL error");
    workOrders = json.data?.workOrders?.nodes || [];
    status.hidden = true;
    render();
  } catch (err) {
    status.className = "status-msg error";
    status.hidden = false;
    status.textContent =
      `No hydrated data yet (${err.message}). Run: python scripts/fetch_all.py`;
  }
}

function stageName(wo) {
  return wo.workOrderStage?.name || wo.workOrderStageId || "—";
}

function isOverdue(wo) {
  if (!wo.endDate) return false;
  return new Date(wo.endDate) < new Date() && !/complete|closed|resolved/i.test(stageName(wo));
}

function isOpen(wo) {
  const s = stageName(wo).toLowerCase();
  return /open|new|pending|queued/.test(s);
}

function isInProgress(wo) {
  const s = stageName(wo).toLowerCase();
  return /progress|active|assigned|in.?flight/.test(s);
}

function filtered() {
  const status = document.getElementById("filter-status").value;
  const priority = document.getElementById("filter-priority").value;
  return workOrders.filter((wo) => {
    if (status === "open" && !isOpen(wo)) return false;
    if (status === "progress" && !isInProgress(wo)) return false;
    if (status === "overdue" && !isOverdue(wo)) return false;
    if (priority !== "all" && (wo.severity || "").toLowerCase() !== priority) return false;
    return true;
  });
}

function renderCounters(rows) {
  document.getElementById("count-open").textContent = workOrders.filter(isOpen).length;
  document.getElementById("count-progress").textContent = workOrders.filter(isInProgress).length;
  document.getElementById("count-overdue").textContent = workOrders.filter(isOverdue).length;
}

function severityClass(s) {
  return (s || "medium").toLowerCase();
}

function renderTable(rows) {
  const tbody = document.getElementById("wo-body");
  tbody.innerHTML = rows
    .map(
      (wo) => `
    <tr data-id="${wo.id}">
      <td>${escapeHtml(wo.title)}</td>
      <td>${escapeHtml(stageName(wo))}</td>
      <td><span class="badge ${severityClass(wo.severity)}">${wo.severity || "—"}</span></td>
      <td>${escapeHtml(wo.asset?.name || "—")}</td>
      <td>${escapeHtml(wo.location?.locationName || wo.locationAddress || "—")}</td>
      <td>${wo.endDate ? new Date(wo.endDate).toLocaleDateString() : "—"}</td>
    </tr>`
    )
    .join("");

  tbody.querySelectorAll("tr").forEach((tr) => {
    tr.addEventListener("click", () => selectRow(tr.dataset.id));
  });
}

function selectRow(id) {
  document.querySelectorAll("#wo-body tr").forEach((tr) => {
    tr.classList.toggle("selected", tr.dataset.id === id);
  });
  const wo = workOrders.find((w) => w.id === id);
  const panel = document.getElementById("detail");
  if (!wo) {
    panel.innerHTML = '<p class="empty">Select a work order</p>';
    return;
  }
  panel.innerHTML = `
    <h2>${escapeHtml(wo.title)}</h2>
    <dl>
      <dt>Description</dt><dd>${escapeHtml(wo.description || "—")}</dd>
      <dt>Stage</dt><dd>${escapeHtml(stageName(wo))}</dd>
      <dt>Severity</dt><dd>${escapeHtml(wo.severity || "—")}</dd>
      <dt>Priority</dt><dd>${escapeHtml(String(wo.executionPriority ?? "—"))}</dd>
      <dt>Due</dt><dd>${wo.endDate ? new Date(wo.endDate).toLocaleString() : "—"}</dd>
      <dt>Asset</dt><dd>${escapeHtml(wo.asset?.name || "—")} (${escapeHtml(wo.asset?.status || "")})</dd>
      <dt>Location</dt><dd>${escapeHtml(wo.location?.locationName || wo.locationAddress || "—")}</dd>
      <dt>Assignees</dt><dd>${(wo.assignees || []).map((a) => escapeHtml(a.name)).join(", ") || "—"}</dd>
    </dl>`;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function render() {
  const rows = filtered();
  renderCounters(rows);
  renderTable(rows);
}

document.getElementById("filter-status").addEventListener("change", render);
document.getElementById("filter-priority").addEventListener("change", render);

loadData();
