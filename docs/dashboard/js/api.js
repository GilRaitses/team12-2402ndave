/** Live demo API — probes /api/health when not on GitHub Pages */
const Api = {
  _live: false,
  _ready: null,

  async init() {
    if (this._ready) return this._ready;
    this._ready = (async () => {
      const h = window.location.hostname;
      if (h === "localhost" || h === "127.0.0.1") {
        this._live = true;
        return;
      }
      if (document.body?.dataset?.liveApi === "true") {
        try {
          const r = await fetch("/api/health", { signal: AbortSignal.timeout(5000) });
          this._live = r.ok;
        } catch {
          this._live = false;
        }
        return;
      }
      this._live = false;
    })();
    return this._ready;
  },

  isLive() {
    return this._live;
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
      b.textContent = "Static mode (GitHub Pages). Live deployment: see submission cover page.";
      document.body.prepend(b);
      return;
    }
    const b = document.createElement("div");
    b.className = "demo-banner live";
    b.textContent = "LIVE — CriticalAsset + OpenAI + NYC Open Data (server-side secrets)";
    document.body.prepend(b);
  },
};
