const DATA_BASE = document.body.dataset.dataBase || "../data";

let workOrders = [];
let allWorkOrders = [];
let assets = [];
let locationsTree = [];
let portfolioOnly = true;

async function loadJson(path) {
  const res = await fetch(`${DATA_BASE}/${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${path}`);
  return res.json();
}

async function loadData() {
  const status = document.getElementById("status");
  try {
    const woResult = await Api.loadWorkOrders(portfolioOnly);
    allWorkOrders = woResult.nodes;
    workOrders = allWorkOrders;

    const [ast, tree] = await Promise.all([
      loadJson("assets.json").catch(() => ({ data: { assets: { assets: [] } } })),
      loadJson("locations_tree.json").catch(() => ({ data: { locationsTree: [] } })),
    ]);
    assets = ast.data?.assets?.assets || [];
    locationsTree = tree.data?.locationsTree || [];

    if (woResult.live) {
      status.className = "status-msg";
      status.hidden = false;
      status.textContent = `Live feed · ${workOrders.length} work orders · fetched ${new Date(woResult.fetchedAt * 1000).toLocaleTimeString()}`;
    } else {
      status.hidden = true;
    }
    render();
    if (window.renderBonus) window.renderBonus(workOrders, assets, locationsTree);
    if (window.initMap) window.initMap(workOrders, locationsTree);
  } catch (err) {
    status.className = "status-msg error";
    status.hidden = false;
    status.textContent = `Data load failed (${err.message}). Run: python scripts/fetch_all.py`;
  }
}

function parseDate(v) {
  if (!v) return null;
  const n = Number(v);
  const d = Number.isFinite(n) ? new Date(n) : new Date(v);
  return Number.isNaN(d.getTime()) ? null : d;
}

function stageName(wo) {
  return wo.workOrderStage?.name || wo.workOrderStageId || "—";
}

function isOverdue(wo) {
  const due = parseDate(wo.endDate);
  if (!due) return false;
  return due < new Date() && !/complete|closed|resolved|done/i.test(stageName(wo));
}

function isOpen(wo) {
  const s = stageName(wo).toLowerCase();
  return /open|new|pending|queued|to do|todo/.test(s);
}

function isInProgress(wo) {
  const s = stageName(wo).toLowerCase();
  return /progress|active|assigned|in.?flight|in progress/.test(s);
}

function filtered() {
  const status = document.getElementById("filter-status").value;
  const priority = document.getElementById("filter-priority").value;
  const category = document.getElementById("filter-category")?.value || "all";
  return workOrders.filter((wo) => {
    if (status === "open" && !isOpen(wo)) return false;
    if (status === "progress" && !isInProgress(wo)) return false;
    if (status === "overdue" && !isOverdue(wo)) return false;
    if (priority !== "all" && (wo.severity || "").toLowerCase() !== priority) return false;
    if (category !== "all" && (wo.workOrderServiceCategory || "other") !== category) return false;
    return true;
  });
}

function renderCounters() {
  document.getElementById("count-open").textContent = workOrders.filter(isOpen).length;
  document.getElementById("count-progress").textContent = workOrders.filter(isInProgress).length;
  document.getElementById("count-overdue").textContent = workOrders.filter(isOverdue).length;
  document.getElementById("count-total").textContent = workOrders.length;
}

function severityClass(s) {
  return (s || "medium").toLowerCase();
}

function formatDate(v) {
  const d = parseDate(v);
  return d ? d.toLocaleDateString() : "—";
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
      <td>${escapeHtml(wo.workOrderServiceCategory || "—")}</td>
      <td>${escapeHtml(wo.location?.locationName || wo.locationAddress || "—")}</td>
      <td>${formatDate(wo.endDate)}</td>
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
  const linkedAssets = (wo.workOrderAssets || []).map((a) => a.asset?.name).filter(Boolean);
  panel.innerHTML = `
    <h2>${escapeHtml(wo.title)}</h2>
    <dl>
      <dt>Description</dt><dd>${escapeHtml(wo.description || "—")}</dd>
      <dt>Stage</dt><dd>${escapeHtml(stageName(wo))}</dd>
      <dt>Severity</dt><dd>${escapeHtml(wo.severity || "—")}</dd>
      <dt>Priority</dt><dd>${escapeHtml(String(wo.executionPriority ?? "—"))}</dd>
      <dt>Category</dt><dd>${escapeHtml(wo.workOrderServiceCategory || "—")}</dd>
      <dt>Type</dt><dd>${escapeHtml(wo.workOrderType || "—")}</dd>
      <dt>Due</dt><dd>${formatDate(wo.endDate)}</dd>
      <dt>Primary asset</dt><dd>${escapeHtml(wo.asset?.name || "—")}</dd>
      <dt>All assets</dt><dd>${linkedAssets.map(escapeHtml).join(", ") || "—"}</dd>
      <dt>Location</dt><dd>${escapeHtml(wo.location?.locationName || wo.locationAddress || "—")}</dd>
    </dl>`;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function populateCategoryFilter() {
  const sel = document.getElementById("filter-category");
  if (!sel) return;
  while (sel.options.length > 1) sel.remove(1);
  const cats = [...new Set(workOrders.map((w) => w.workOrderServiceCategory).filter(Boolean))].sort();
  cats.forEach((c) => {
    const o = document.createElement("option");
    o.value = c;
    o.textContent = c;
    sel.appendChild(o);
  });
}

function render() {
  populateCategoryFilter();
  const rows = filtered();
  renderCounters();
  renderTable(rows);
}

document.getElementById("portfolio-only")?.addEventListener("change", (e) => {
  portfolioOnly = e.target.checked;
  loadData();
});

["filter-status", "filter-priority", "filter-category"].forEach((id) => {
  const el = document.getElementById(id);
  if (el) el.addEventListener("change", render);
});

(async () => {
  await Api.init();
  Api.showBanner();
  loadData();
})();
