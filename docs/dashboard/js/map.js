function initMap(workOrders, locationsTree) {
  const el = document.getElementById("building-map");
  if (!el || typeof L === "undefined") return;

  const lat = 40.7326568;
  const lon = -73.9844033;
  const map = L.map(el).setView([lat, lon], 17);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "© OpenStreetMap",
    maxZoom: 19,
  }).addTo(map);

  const openCount = workOrders.filter((w) => /to do|open|pending/i.test(w.workOrderStage?.name || "")).length;
  L.marker([lat, lon])
    .addTo(map)
    .bindPopup(`<strong>240 2nd Avenue</strong><br/>${openCount} open work orders`);

  const site = (locationsTree || [])[0];
  const mapsLink = site?.metadata?.mapsLink;
  if (mapsLink) {
    const linkEl = document.getElementById("maps-link");
    if (linkEl) linkEl.href = mapsLink;
  }
}

window.initMap = initMap;
