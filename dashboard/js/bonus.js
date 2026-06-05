function renderBonus(workOrders, assets, locationsTree) {
  renderBuildings(workOrders, locationsTree);
  renderCategories(workOrders);
  renderSignalForm(workOrders);
}

function renderBuildings(workOrders, tree) {
  const el = document.getElementById("building-stats");
  if (!el) return;
  const counts = {};
  workOrders.forEach((wo) => {
    const name = wo.location?.locationName || wo.locationAddress || "Unknown";
    if (isOpenWO(wo)) counts[name] = (counts[name] || 0) + 1;
  });
  const top = Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);
  const floors = countFloors(tree);
  el.innerHTML = `
    <p class="muted">${floors} sub-locations in portfolio tree · ${assets.length} assets indexed</p>
    <ol>${top.length ? top.map(([n, c]) => `<li><strong>${escape(n)}</strong> — ${c} open</li>`).join("") : "<li>No open work orders by building</li>"}</ol>`;
}

function countFloors(tree) {
  let n = 0;
  function walk(nodes) {
    (nodes || []).forEach((node) => {
      n += 1;
      walk(node.sublocation || node.children);
    });
  }
  walk(tree);
  return n;
}

function renderCategories(workOrders) {
  const el = document.getElementById("category-stats");
  if (!el) return;
  const groups = {};
  workOrders.forEach((wo) => {
    const cat = wo.workOrderServiceCategory || "other";
    groups[cat] = (groups[cat] || 0) + 1;
  });
  el.innerHTML = Object.entries(groups)
    .sort((a, b) => b[1] - a[1])
    .map(([cat, n]) => `<div class="cat-row"><span>${escape(cat)}</span><span class="cat-count">${n}</span></div>`)
    .join("");
}

function renderSignalForm(workOrders) {
  const form = document.getElementById("signal-form");
  const out = document.getElementById("signal-output");
  if (!form) return;
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = document.getElementById("signal-text").value.trim();
    if (!text) return;
    const structured = structureSignal(text, workOrders);
    out.hidden = false;
    out.innerHTML = `
      <h3>Structured signal</h3>
      <dl>
        <dt>Raw signal</dt><dd>${escape(text)}</dd>
        <dt>Location</dt><dd>${escape(structured.location)} <span class="label">${structured.locationConf}</span></dd>
        <dt>Issue</dt><dd>${escape(structured.issue)} <span class="label">${structured.issueConf}</span></dd>
        <dt>Linked work order</dt><dd>${escape(structured.linkedWO)} <span class="label">${structured.linkConf}</span></dd>
        <dt>Next action</dt><dd>${escape(structured.nextAction)}</dd>
      </dl>
      <p class="muted">To record in CriticalAsset: <code>python scripts/submit_signal.py</code> with this payload.</p>
      <pre class="signal-json">${escape(JSON.stringify(structured, null, 2))}</pre>`;
  });
}

function structureSignal(text, workOrders) {
  const lower = text.toLowerCase();
  let location = "240 2nd Avenue";
  let locationConf = "Likely";
  const floorMatch = lower.match(/(\d+)(st|nd|rd|th)[-\s]floor|floor\s*(\d+)/);
  if (floorMatch) {
    location = `Floor ${floorMatch[1] || floorMatch[3]}`;
    locationConf = "Inferred";
  }
  if (/bathroom|restroom/.test(lower)) location += " · bathroom";

  let issue = "Facility issue reported by student";
  let issueConf = "Likely";
  if (/leak|water|flood/.test(lower)) { issue = "Water / leak"; issueConf = "Likely"; }
  if (/elevator/.test(lower)) { issue = "Elevator failure"; issueConf = "Likely"; }
  if (/hot|overheat|cold/.test(lower)) { issue = "HVAC / temperature"; issueConf = "Likely"; }

  let linked = workOrders.find((wo) => {
    const t = (wo.title + " " + (wo.description || "")).toLowerCase();
    if (/steam|hvac|heat/.test(lower) && /steam|hvac/.test(t)) return true;
    if (/electric|panel|power/.test(lower) && /electrical/.test(t)) return true;
    return false;
  });
  const linkedWO = linked ? `${linked.title} (${linked.id.slice(0, 8)}…)` : "No automatic match — create new issue";
  const linkConf = linked ? "Inferred" : "Missing";

  return {
    location,
    locationConf,
    issue,
    issueConf,
    linkedWO,
    linkConf,
    linkedWorkOrderId: linked?.id || null,
    nextAction: linked ? "Attach student observation to open work order" : "Dispatch inspection work order",
    confidenceLabels: ["Verified", "Likely", "Inferred", "Missing"],
    raw: text,
  };
}

function isOpenWO(wo) {
  const s = (wo.workOrderStage?.name || "").toLowerCase();
  return /open|to do|todo|pending|new/.test(s);
}

function escape(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

window.renderBonus = renderBonus;
