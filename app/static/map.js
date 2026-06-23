"use strict";

const FRANCE_CENTER = [46.5, 2.5];
const FRANCE_ZOOM = 6;
const FRANCE_BOUNDS = [
  [41.0, -5.5],
  [51.5, 10.5],
];

const mapStatusEl = document.getElementById("map-status");
const legendEl = document.getElementById("map-legend");

let map = null;
let nodesLayer = null;
const markersByNode = new Map();
const nodeMeta = new Map();

function setMapStatus(text, kind) {
  if (!mapStatusEl) return;
  mapStatusEl.textContent = text;
  mapStatusEl.className = "map-status" + (kind ? ` ${kind}` : "");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatTime(ts) {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function nodeColor(fromId) {
  const hue = (Number(fromId) * 47) % 360;
  return `hsl(${hue}, 72%, 52%)`;
}

function channelLabel(data) {
  if (data.channel_index != null && data.channel_name) {
    return `${data.channel_index}:${data.channel_name}`;
  }
  if (data.channel_name) return data.channel_name;
  return "—";
}

function buildPopup(pos) {
  const meta = nodeMeta.get(pos.from_id);
  const shortName = pos.from_short || meta?.short_name || `!${Number(pos.from_id).toString(16).padStart(8, "0")}`;
  const longName = pos.long_name || meta?.long_name || shortName;
  const alt =
    pos.altitude != null && !Number.isNaN(Number(pos.altitude))
      ? `<p class="map-popup-desc">Altitude : ${Number(pos.altitude).toFixed(0)} m</p>`
      : "";
  return (
    `<p class="map-popup-title">${escapeHtml(shortName)}</p>` +
    `<p class="map-popup-desc">${escapeHtml(longName)}</p>` +
    `<p class="map-popup-desc">Canal : ${escapeHtml(channelLabel(pos))}</p>` +
    `<p class="map-popup-desc">${Number(pos.latitude).toFixed(5)}, ${Number(pos.longitude).toFixed(5)}</p>` +
    alt +
    `<p class="map-popup-period">${escapeHtml(formatTime(pos.timestamp))}</p>`
  );
}

function updateLegend() {
  if (!legendEl) return;
  const count = markersByNode.size;
  if (!count) {
    legendEl.innerHTML = '<span class="map-legend-muted">Aucune position reçue</span>';
    return;
  }
  legendEl.innerHTML =
    `<div class="map-legend-item"><span class="map-legend-swatch" style="background:#6ab7ff"></span>` +
    `<span>${count} nœud${count > 1 ? "s" : ""}</span></div>`;
}

function upsertNodeMarker(pos) {
  if (!nodesLayer || pos.latitude == null || pos.longitude == null) return;

  const lat = Number(pos.latitude);
  const lon = Number(pos.longitude);
  if (Number.isNaN(lat) || Number.isNaN(lon)) return;

  const fromId = Number(pos.from_id);
  const color = nodeColor(fromId);
  let marker = markersByNode.get(fromId);

  if (!marker) {
    marker = L.circleMarker([lat, lon], {
      radius: 8,
      color: "#1a1d24",
      weight: 2,
      fillColor: color,
      fillOpacity: 0.92,
    }).addTo(nodesLayer);
    markersByNode.set(fromId, marker);
  } else {
    marker.setLatLng([lat, lon]);
    marker.setStyle({ fillColor: color });
  }

  marker.bindPopup(buildPopup(pos));
  updateLegend();
}

function rememberNode(data) {
  nodeMeta.set(Number(data.from_id), {
    short_name: data.short_name,
    long_name: data.long_name,
  });
  const marker = markersByNode.get(Number(data.from_id));
  if (marker && marker.getPopup()) {
    const latLng = marker.getLatLng();
    upsertNodeMarker({
      from_id: data.from_id,
      latitude: latLng.lat,
      longitude: latLng.lng,
      timestamp: Date.now() / 1000,
      from_short: data.short_name,
      long_name: data.long_name,
    });
  }
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

  nodesLayer = L.layerGroup().addTo(map);
}

async function loadStoredPositions() {
  setMapStatus("Chargement des positions…", "loading");
  try {
    const res = await fetch("/api/positions");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    for (const pos of data.positions || []) {
      upsertNodeMarker(pos);
    }
    const count = markersByNode.size;
    setMapStatus(
      count
        ? `${count} position${count > 1 ? "s" : ""} en mémoire — écoute MQTT`
        : "En écoute — positions Meshtastic en direct",
      count ? "ok" : ""
    );
  } catch (err) {
    setMapStatus(`Positions indisponibles (${err.message}) — écoute MQTT`, "error");
  }
}

function connectWebSocket() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${proto}//${location.host}/ws`);

  ws.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    if (data.type === "position") {
      upsertNodeMarker(data);
      const count = markersByNode.size;
      setMapStatus(
        `${count} nœud${count > 1 ? "s" : ""} — dernière MAJ ${formatTime(data.timestamp)}`,
        "ok"
      );
    } else if (data.type === "node") {
      rememberNode(data);
    }
  };

  ws.onclose = () => setTimeout(connectWebSocket, 2000);
}

initMap();
updateLegend();
loadStoredPositions();
connectWebSocket();
