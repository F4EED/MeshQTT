"use strict";

const INFOROUTE_AUTO_REFRESH_MS = 30 * 60 * 1000;
const FRANCE_CENTER = [46.5, 2.5];
const FRANCE_ZOOM = 6;
const FRANCE_BOUNDS = [
  [41.0, -5.5],
  [51.5, 10.5],
];
const SETTINGS_STORAGE_KEY = "meshqtt-settings";

const EVENT_CATEGORIES = [
  { id: "accident", label: "Accident", color: "#e74c3c" },
  { id: "danger", label: "Danger", color: "#e67e22" },
  { id: "travaux", label: "Travaux", color: "#3498db" },
  { id: "gravillonnage", label: "Gravillonnage", color: "#f1c40f" },
  { id: "autres", label: "Autres", color: "#95a5a6" },
  { id: "deviation", label: "Déviation", color: "#9b59b6" },
];

const mapStatusEl = document.getElementById("map-status");
const mapRefreshBtn = document.getElementById("map-refresh-btn");
const legendEl = document.getElementById("map-legend");

let map = null;
let markersLayer = null;
let refreshBusy = false;
let autoRefreshTimer = null;
let mapChannel = null;
let inforouteLayerEnabled = true;

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function loadInforouteEnabledFromSettings() {
  try {
    const raw = localStorage.getItem(SETTINGS_STORAGE_KEY);
    if (!raw) return true;
    const settings = JSON.parse(raw);
    return settings.ui?.inforoute_enabled !== false;
  } catch {
    return true;
  }
}

function getEventLatLon(ev) {
  let lat = ev.latitude != null ? Number(ev.latitude) : NaN;
  let lon = ev.longitude != null ? Number(ev.longitude) : NaN;
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
    lat = ev.latitude_from_xy != null ? Number(ev.latitude_from_xy) : NaN;
    lon = ev.longitude_from_xy != null ? Number(ev.longitude_from_xy) : NaN;
  }
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  if (lat < 41 || lat > 52 || lon < -6 || lon > 11) return null;
  return { lat, lon };
}

function buildPopupHtml(cat, ev) {
  const title = ev.title || "Signalement";
  const desc = ev.description || "";
  const period = ev.period || "";
  return `<p class="map-popup-title">${escapeHtml(title)}</p>
    <span class="map-popup-cat" style="background:${cat.color}22;color:${cat.color}">${escapeHtml(cat.label)}</span>
    ${desc ? `<p class="map-popup-desc">${escapeHtml(desc)}</p>` : ""}
    ${period ? `<p class="map-popup-period">${escapeHtml(period)}</p>` : ""}`;
}

function renderLegend(counts) {
  if (!legendEl) return;
  legendEl.innerHTML = EVENT_CATEGORIES.filter((c) => counts[c.id] > 0)
    .map(
      (c) =>
        `<div class="map-legend-item"><span class="map-legend-swatch" style="background:${c.color}"></span>${escapeHtml(c.label)} (${counts[c.id]})</div>`
    )
    .join("");
}

function clearInforouteMarkers() {
  if (!markersLayer) return;
  markersLayer.clearLayers();
  renderLegend({});
  if (map) map.setView(FRANCE_CENTER, FRANCE_ZOOM);
}

function renderMarkers(data) {
  if (!markersLayer) return 0;

  markersLayer.clearLayers();
  const counts = Object.fromEntries(EVENT_CATEGORIES.map((c) => [c.id, 0]));
  const events = data?.events || {};
  const bounds = [];

  for (const cat of EVENT_CATEGORIES) {
    const list = Array.isArray(events[cat.id]) ? events[cat.id] : [];
    for (const ev of list) {
      const coords = getEventLatLon(ev);
      if (!coords) continue;

      counts[cat.id] += 1;
      bounds.push([coords.lat, coords.lon]);

      const marker = L.circleMarker([coords.lat, coords.lon], {
        radius: 8,
        color: cat.color,
        fillColor: cat.color,
        fillOpacity: 0.85,
        weight: 2,
      });
      marker.bindPopup(buildPopupHtml(cat, ev), { maxWidth: 320 });
      markersLayer.addLayer(marker);
    }
  }

  renderLegend(counts);

  const total = Object.values(counts).reduce((s, n) => s + n, 0);
  if (bounds.length === 1) {
    map.setView(bounds[0], Math.max(map.getZoom(), 10));
  } else if (bounds.length > 1) {
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 11 });
  } else {
    map.setView(FRANCE_CENTER, FRANCE_ZOOM);
  }

  return total;
}

function setMapStatus(text, kind) {
  if (!mapStatusEl) return;
  mapStatusEl.textContent = text;
  mapStatusEl.className = "map-status" + (kind ? ` ${kind}` : "");
}

function stopAutoRefresh() {
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer);
    autoRefreshTimer = null;
  }
}

async function refreshInforouteMap({ manual = false } = {}) {
  if (!inforouteLayerEnabled) {
    if (manual) setMapStatus("Info Routes 42 désactivé — fond carte uniquement", "");
    return;
  }
  if (refreshBusy) {
    if (manual) setMapStatus("Actualisation déjà en cours…", "loading");
    return;
  }
  refreshBusy = true;
  if (mapRefreshBtn) mapRefreshBtn.disabled = true;
  setMapStatus(
    manual ? "Chargement via Internet…" : "Actualisation automatique…",
    "loading"
  );

  try {
    const res = await fetch("/api/inforoute42", { cache: "no-store" });
    const payload = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = payload.detail;
      const message = Array.isArray(detail)
        ? detail[0]?.msg || detail[0]
        : detail;
      throw new Error(message || "Échec de la récupération");
    }

    const total = renderMarkers(payload);
    const when = payload.fetched_at
      ? new Date(payload.fetched_at).toLocaleString("fr-FR")
      : "maintenant";
    const updated = payload.updated_at_display || payload.updated_at || "—";
    setMapStatus(
      `Site ${updated} — ${total} point(s) — actualisé le ${when} — auto. 30 min`,
      "ok"
    );
  } catch (err) {
    setMapStatus(err.message || "Inforoute 42 inaccessible", "error");
  } finally {
    refreshBusy = false;
    if (mapRefreshBtn) mapRefreshBtn.disabled = false;
  }
}

function startAutoRefresh() {
  stopAutoRefresh();
  refreshInforouteMap({ manual: false });
  autoRefreshTimer = setInterval(
    () => refreshInforouteMap({ manual: false }),
    INFOROUTE_AUTO_REFRESH_MS
  );
}

function applyInforouteLayerEnabled(enabled) {
  inforouteLayerEnabled = Boolean(enabled);
  if (mapRefreshBtn) mapRefreshBtn.hidden = !inforouteLayerEnabled;

  if (!inforouteLayerEnabled) {
    stopAutoRefresh();
    clearInforouteMarkers();
    setMapStatus("Info Routes 42 désactivé — fond carte uniquement", "");
    return;
  }

  startAutoRefresh();
}

function initMap() {
  map = L.map("map", {
    center: FRANCE_CENTER,
    zoom: FRANCE_ZOOM,
    minZoom: 5,
    maxBounds: FRANCE_BOUNDS,
    maxBoundsViscosity: 0.85,
  });

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19,
  }).addTo(map);

  markersLayer = L.layerGroup().addTo(map);
  renderLegend({});
}

function initBroadcast() {
  if (typeof BroadcastChannel === "undefined") return;
  mapChannel = new BroadcastChannel("meshqtt-inforoute42");
  mapChannel.onmessage = (event) => {
    if (event.data?.type === "inforoute_enabled") {
      applyInforouteLayerEnabled(event.data.enabled);
      return;
    }
    if (
      event.data?.type === "inforoute42" &&
      event.data.payload &&
      inforouteLayerEnabled
    ) {
      const total = renderMarkers(event.data.payload);
      const when = event.data.payload.fetched_at
        ? new Date(event.data.payload.fetched_at).toLocaleString("fr-FR")
        : "maintenant";
      setMapStatus(
        `Synchronisé depuis MeshQTT — ${total} point(s) — ${when}`,
        "ok"
      );
    }
  };
}

mapRefreshBtn?.addEventListener("click", () => refreshInforouteMap({ manual: true }));

window.addEventListener("storage", (event) => {
  if (event.key === SETTINGS_STORAGE_KEY) {
    applyInforouteLayerEnabled(loadInforouteEnabledFromSettings());
  }
});

initMap();
initBroadcast();
applyInforouteLayerEnabled(loadInforouteEnabledFromSettings());
