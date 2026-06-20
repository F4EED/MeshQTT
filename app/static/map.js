"use strict";

const FRANCE_CENTER = [46.5, 2.5];
const FRANCE_ZOOM = 6;
const FRANCE_BOUNDS = [
  [41.0, -5.5],
  [51.5, 10.5],
];

const mapStatusEl = document.getElementById("map-status");

let map = null;

function setMapStatus(text, kind) {
  if (!mapStatusEl) return;
  mapStatusEl.textContent = text;
  mapStatusEl.className = "map-status" + (kind ? ` ${kind}` : "");
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
}

initMap();
setMapStatus("Fond OSM — Info Routes 42 desactive", "");

/* Info Routes 42 — desactive pour le moment (reactiver map.html + app.js + main.py)
const INFOROUTE_AUTO_REFRESH_MS = 30 * 60 * 1000;
const SETTINGS_STORAGE_KEY = "meshqtt-settings";
const EVENT_CATEGORIES = [ ... ];
const mapRefreshBtn = document.getElementById("map-refresh-btn");
const legendEl = document.getElementById("map-legend");
let markersLayer = null;
... refreshInforouteMap, initBroadcast, etc.
*/
