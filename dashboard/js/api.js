/** Live demo API helpers — localhost uses api_server.py */
const Api = {
  isLive() {
    return window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
  },

  dataBase() {
    return document.body.dataset.dataBase || "../data";
  },

  async loadWorkOrders(portfolioOnly = true) {
    if (this.isLive()) {
      const res = await fetch("/api/live/workorders");
      const json = await res.json();
      let nodes = json.data?.workOrders?.nodes || [];
      if (portfolioOnly) nodes = nodes.filter((w) => w._source !== "hackathon_test");
      return { nodes, fetchedAt: json.fetchedAt, live: !json.cached };
    }
    const res = await fetch(`${this.dataBase()}/workorders.json`);
    const json = await res.json();
    let nodes = json.data?.workOrders?.nodes || [];
    if (portfolioOnly) nodes = nodes.filter((w) => w._source !== "hackathon_test");
    return { nodes, fetchedAt: null, live: false };
  },

  async structure(signal, workOrderId, photoNote) {
    if (this.isLive()) {
      const res = await fetch("/api/structure", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ signal, workOrderId, photoNote, live: true, useLlm: true }),
      });
      return res.json();
    }
    return null;
  },

  async record(structured) {
    if (!this.isLive()) return { ok: false, error: "static mode" };
    const res = await fetch("/api/record", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ structured }),
    });
    return res.json();
  },

  async closure(workOrderId, status, structured) {
    if (!this.isLive()) return { ok: false, error: "static mode" };
    const res = await fetch("/api/closure", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workOrderId, status, structured }),
    });
    return res.json();
  },

  showBanner() {
    if (!this.isLive()) {
      const b = document.createElement("div");
      b.className = "demo-banner static";
      b.textContent = "Static mode (GitHub Pages). Run python3 backend/api_server.py for live demo.";
      document.body.prepend(b);
      return;
    }
    const b = document.createElement("div");
    b.className = "demo-banner live";
    b.textContent = "LIVE DEMO — connected to CriticalAsset + OpenAI";
    document.body.prepend(b);
  },
};
