const messagesEl = document.getElementById("messages");
const nodesListEl = document.getElementById("nodes-list");
const nodeCountEl = document.getElementById("node-count");
const statusBar = document.getElementById("status-bar");
const sendGroupForm = document.getElementById("send-group-form");
const sendDirectForm = document.getElementById("send-direct-form");
const groupMessageInput = document.getElementById("group-message-input");
const directMessageInput = document.getElementById("direct-message-input");
const groupMessageCharCount = document.getElementById("group-message-char-count");
const directMessageCharCount = document.getElementById("direct-message-char-count");
const sendGroupBtn = document.getElementById("send-group-btn");
const sendDirectBtn = document.getElementById("send-direct-btn");
const sendChannelSelect = document.getElementById("send-channel");
const directDestinationSelect = document.getElementById("direct-destination");
// Info Routes 42 — desactive pour le moment
// const inforouteRefreshBtn = document.getElementById("inforoute-refresh-btn");
// const inforouteStatusEl = document.getElementById("inforoute-status");
// const inforouteContentEl = document.getElementById("inforoute-content");
// const inforouteChannelSelect = document.getElementById("inforoute-channel");
// const inforouteMeshText = document.getElementById("inforoute-mesh-text");
// const inforouteMeshCharCount = document.getElementById("inforoute-mesh-char-count");
// const inforouteRelayBtn = document.getElementById("inforoute-relay-btn");
const connectBtn = document.getElementById("connect-btn");
const disconnectBtn = document.getElementById("disconnect-btn");
const mapBtn = document.getElementById("map-btn");
// const inforoutePanel = document.getElementById("inforoute-panel");
// const inforouteEnabledToggle = document.getElementById("inforoute-enabled-toggle");
const themeBtn = document.getElementById("theme-btn");
const mqttModal = document.getElementById("mqtt-modal");
const meshModal = document.getElementById("mesh-modal");
const mqttForm = document.getElementById("mqtt-form");
const meshForm = document.getElementById("mesh-form");
const channelTabsEl = document.getElementById("channel-tabs");
const channelPanelsEl = document.getElementById("channel-panels");
const activeChannelSelect = document.getElementById("active-channel-select");
const nodeIdInput = document.getElementById("node-id-input");
const proposeNodeIdBtn = document.getElementById("propose-node-id-btn");
const presetsListEl = document.getElementById("presets-list");
const presetNewBtn = document.getElementById("preset-new-btn");
const presetModal = document.getElementById("preset-modal");
const presetForm = document.getElementById("preset-form");
const presetModalTitle = document.getElementById("preset-modal-title");
const presetCategorySelect = document.getElementById("preset-category");
const presetChannelSelect = document.getElementById("preset-channel-select");
const presetInput = document.getElementById("preset-input");
const presetVisuInput = document.getElementById("preset-visu-input");
const presetOptionInput = document.getElementById("preset-option-input");
const presetCharCount = document.getElementById("preset-char-count");
const presetSendModal = document.getElementById("preset-send-modal");
const presetSendForm = document.getElementById("preset-send-form");
const presetSendModalTitle = document.getElementById("preset-send-modal-title");
const presetSendChannelHint = document.getElementById("preset-send-channel-hint");
const presetSendInput = document.getElementById("preset-send-input");
const presetSendCharCount = document.getElementById("preset-send-char-count");
const presetCatModal = document.getElementById("preset-cat-modal");
const presetCatForm = document.getElementById("preset-cat-form");
const presetCatModalTitle = document.getElementById("preset-cat-modal-title");
const presetCatSelectWrap = document.getElementById("preset-cat-select-wrap");
const presetCatLabelWrap = document.getElementById("preset-cat-label-wrap");
const presetCatSelect = document.getElementById("preset-cat-select");
const presetCatLabelInput = document.getElementById("preset-cat-label-input");
const presetCatHint = document.getElementById("preset-cat-hint");
const presetCatAddBtn = document.getElementById("preset-cat-add-btn");
const presetCatEditBtn = document.getElementById("preset-cat-edit-btn");
const presetCatDelBtn = document.getElementById("preset-cat-del-btn");
const presetCatSubmitBtn = document.getElementById("preset-cat-submit-btn");
const presetCatDeleteBar = document.getElementById("preset-cat-delete-bar");
const presetCatDeleteSelect = document.getElementById("preset-cat-delete-select");
const presetCatDeleteConfirmBtn = document.getElementById("preset-cat-delete-confirm");
const presetCatDeleteCancelBtn = document.getElementById("preset-cat-delete-cancel");
const presetCatDeleteHint = document.getElementById("preset-cat-delete-hint");
const presetBakeBtn = document.getElementById("preset-bake-btn");

const nodes = new Map();
let settings = null;
let activeChannelTab = 0;
let isConnected = false;

const CHANNEL_COUNT = 8;
const CHANNEL_ROLES = ["PRINCIPAL", "SECONDAIRE", "DESACTIVE"];
/** Limite Meshtastic (~200 octets UTF-8, clients officiels Android/iOS/Web). */
const MESH_MESSAGE_MAX_BYTES = 200;
const SETTINGS_KEY = "meshqtt-settings";
const PRESETS_KEY = "meshqtt-presets";
const PRESETS_OPEN_KEY = "meshqtt-presets-open";
const PRESET_CATEGORIES_KEY = "meshqtt-preset-categories";
const PRESET_REMOVED_CATEGORIES_KEY = "meshqtt-preset-removed-categories";

const DEFAULT_PRESET_CATEGORIES = [
  { id: "pompier", label: "Pompier" },
  { id: "secours", label: "Secours" },
  { id: "secouriste", label: "Secouriste" },
  { id: "crise", label: "Gestion de crise" },
  { id: "communautaire", label: "Communautaire" },
];

function presetEntry(text, channel = 0, visu = "", option = false) {
  return { text, channel, visu, option: Boolean(option) };
}

const DEFAULT_PRESETS = {
  pompier: [
    presetEntry("Feu confirmé — renfort demandé"),
    presetEntry("Intervention terminée"),
  ],
  secours: [presetEntry("Victime localisée"), presetEntry("Évacuation en cours")],
  secouriste: [
    presetEntry("Premiers secours en cours"),
    presetEntry("Victime stabilisée"),
  ],
  crise: [presetEntry("Cellule de crise activée"), presetEntry("Point de situation H+1")],
  communautaire: [
    presetEntry("Hello from MeshQTT!"),
    presetEntry("Test ping mesh"),
    presetEntry("73"),
  ],
};

let openPresetCategories = new Set();
let presetEditState = null;
let presetSendState = null;
let presetCategories = structuredClone(DEFAULT_PRESET_CATEGORIES);
let presetCatModalMode = "add";
let bundledPresetsData = null;

// Info Routes 42 — desactive pour le moment
// const INFOROUTE_DEFAULT_CHANNEL = "D_Ligerien";
// const INFOROUTE_WAYPOINT_CHANNEL = 0;
// const INFOROUTE_AUTO_REFRESH_MS = 30 * 60 * 1000;
// let inforouteRefreshBusy = false;
// let inforouteAutoRefreshTimer = null;
// let inforouteMapChannel = null;

const DEFAULT_SETTINGS = {
  mqtt: {
    broker: "192.168.1.66",
    port: 1883,
    username: "",
    password: "",
    root_topic: "msh/EU_868",
  },
  meshtastic: {
    channels: [
      { name: "Fr_Balise", key: "AQ==", enabled: true, role: "PRINCIPAL" },
      { name: "Fr_EMCOM", key: "AQ==", enabled: true, role: "SECONDAIRE" },
      { name: "Fr_BlaBla", key: "AQ==", enabled: true, role: "SECONDAIRE" },
      { name: "D_Ligerien", key: "AQ==", enabled: true, role: "SECONDAIRE" },
      {
        name: "interco",
        key: "L5gSgxLSvkOfmejKZwIPWCtMzhb+upi8fXyFOvRXm2Q=",
        enabled: true,
        role: "SECONDAIRE",
      },
      {
        name: "AASC",
        key: "HlXAVy6LrbQ0idduXZj2a8p79wifB8ZIBZNT3UrqbB4=",
        enabled: true,
        role: "SECONDAIRE",
      },
      {
        name: "mqtt",
        key: "AQ==",
        enabled: true,
        role: "SECONDAIRE",
      },
      {
        name: "logistique",
        key: "zx8k0MF/HFrPDSFJTKOe4PjnUl4+dDpIAh8LPtaZ3YU=",
        enabled: true,
        role: "SECONDAIRE",
      },
    ],
    active_channel: 0,
    short_name: "MQTT",
    long_name: "MeshQTT Web",
    node_id: null,
  },
  ui: { theme: "dark" /* inforoute_enabled: true — desactive */ },
};

const RESERVED_NODE_IDS = new Set([1, 2, 3, 4, 0xffffffff]);

function meshMessageByteLength(text) {
  return new TextEncoder().encode(text).length;
}

function clampMeshMessage(text) {
  if (meshMessageByteLength(text) <= MESH_MESSAGE_MAX_BYTES) return text;
  let end = text.length;
  while (end > 0 && meshMessageByteLength(text.slice(0, end)) > MESH_MESSAGE_MAX_BYTES) {
    end -= 1;
  }
  return text.slice(0, end);
}

function isMeshMessageValid(text) {
  const trimmed = text.trim();
  return trimmed.length > 0 && meshMessageByteLength(trimmed) <= MESH_MESSAGE_MAX_BYTES;
}

function meshMessageTooLongToast(text) {
  const bytes = meshMessageByteLength(text.trim());
  showToast(
    `Message trop long (${bytes}/${MESH_MESSAGE_MAX_BYTES} octets UTF-8)`,
    "error"
  );
}

function updateMeshMessageCounter(inputEl, countEl) {
  if (!inputEl || !countEl) return;
  const bytes = meshMessageByteLength(inputEl.value);
  countEl.textContent = String(bytes);
  const wrap = countEl.closest(".mesh-msg-count");
  wrap?.classList.toggle("mesh-msg-count-at-limit", bytes >= MESH_MESSAGE_MAX_BYTES);
  wrap?.classList.toggle("mesh-msg-count-over", bytes > MESH_MESSAGE_MAX_BYTES);
}

function bindMeshMessageInput(inputEl, countEl) {
  if (!inputEl) return;
  inputEl.addEventListener("input", () => {
    const clamped = clampMeshMessage(inputEl.value);
    if (clamped !== inputEl.value) {
      inputEl.value = clamped;
    }
    updateMeshMessageCounter(inputEl, countEl);
  });
  updateMeshMessageCounter(inputEl, countEl);
}

function normalizeRootTopic(raw) {
  let topic = String(raw || "").trim();
  if (!topic) return DEFAULT_SETTINGS.mqtt.root_topic;
  for (const marker of ["/2/e", "/2/json", "/2/c"]) {
    if (topic.includes(marker)) {
      topic = topic.split(marker)[0];
    }
  }
  if (topic.startsWith("msh/EU/433")) {
    topic = "msh/EU_868";
  }
  topic = topic.replace(/\/+$/, "");
  const parts = topic.split("/").filter(Boolean);
  if (parts.length < 2 || parts[0] !== "msh" || !parts[1]) {
    return DEFAULT_SETTINGS.mqtt.root_topic;
  }
  return topic;
}

function refreshSettingsFromStorage() {
  const local = loadLocalSettings();
  if (!local) return;
  settings = local;
  if (settings.meshtastic?.channels) {
    settings.meshtastic.channels = normalizeChannelsList(settings.meshtastic.channels);
  }
  if (settings.mqtt?.root_topic) {
    settings.mqtt.root_topic = normalizeRootTopic(settings.mqtt.root_topic);
  }
}

function migrateLocalMqtt(mqtt) {
  if (!mqtt) return DEFAULT_SETTINGS.mqtt;
  if (mqtt.broker === "mqtt.meshtastic.org" || mqtt.broker === "mqtt.meshtastic.com") {
    return {
      ...mqtt,
      broker: "192.168.1.66",
      username: "",
      password: "",
    };
  }
  if (mqtt.root_topic) {
    mqtt.root_topic = normalizeRootTopic(mqtt.root_topic);
  }
  return mqtt;
}

function loadLocalSettings() {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const previousBroker = parsed.mqtt?.broker;
    if (parsed.mqtt) parsed.mqtt = migrateLocalMqtt(parsed.mqtt);
    const merged = mergeSettings(DEFAULT_SETTINGS, parsed);
    merged.meshtastic.channels = normalizeChannelsList(merged.meshtastic?.channels);
    if (
      previousBroker &&
      (previousBroker === "mqtt.meshtastic.org" ||
        previousBroker === "mqtt.meshtastic.com")
    ) {
      saveLocalSettings(merged);
    }
    return merged;
  } catch {
    return null;
  }
}

function saveLocalSettings(data) {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(data));
}

function normalizeChannelRole(role, index, enabled = false) {
  if (CHANNEL_ROLES.includes(role)) return role;
  if (!enabled) return "DESACTIVE";
  return index === 0 ? "PRINCIPAL" : "SECONDAIRE";
}

function normalizeChannelSlot(ch, index) {
  const role = normalizeChannelRole(ch?.role, index, ch?.enabled);
  return {
    name: ch?.name || "",
    key: ch?.key || "",
    role,
    enabled: role !== "DESACTIVE",
  };
}

function normalizeChannelsList(channels) {
  return Array.from({ length: CHANNEL_COUNT }, (_, i) =>
    normalizeChannelSlot(channels?.[i] || {}, i)
  );
}

function channelRoleOptionsHtml(selectedRole) {
  return CHANNEL_ROLES.map(
    (role) =>
      `<option value="${role}"${role === selectedRole ? " selected" : ""}>${role}</option>`
  ).join("");
}

function mergeSettings(base, override) {
  const result = structuredClone(base);
  for (const [key, value] of Object.entries(override || {})) {
    if (
      value &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      result[key] &&
      typeof result[key] === "object" &&
      !Array.isArray(result[key])
    ) {
      result[key] = { ...result[key], ...value };
    } else {
      result[key] = value;
    }
  }
  if (override?.meshtastic?.channels) {
    result.meshtastic.channels = override.meshtastic.channels;
  }
  return result;
}

function generateNodeIdProposal() {
  let id;
  do {
    id =
      Math.floor(Math.random() * (0xfffffffe - 0x10000000 + 1)) + 0x10000000;
  } while (RESERVED_NODE_IDS.has(id));
  return id;
}

function formatNodeId(id) {
  return "!" + Number(id).toString(16).padStart(8, "0");
}

function proposeNodeIdIntoForm() {
  const proposal = formatNodeId(generateNodeIdProposal());
  if (nodeIdInput) nodeIdInput.value = proposal;
  return proposal;
}

function normalizeTheme(theme) {
  if (theme === "light" || theme === "dark") return theme;
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

function formatTime(ts) {
  return new Date(ts * 1000).toLocaleTimeString("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function escapeHtml(text) {
  const d = document.createElement("div");
  d.textContent = text;
  return d.innerHTML;
}

function showToast(message, type = "success") {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = message;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 2800);
}

function appendSystem(text) {
  const el = document.createElement("div");
  el.className = "msg system";
  el.textContent = text;
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function channelLabel(data) {
  if (data.channel_index != null && data.channel_name) {
    return `[${data.channel_index}:${escapeHtml(data.channel_name)}] `;
  }
  if (data.channel_name) {
    return `[${escapeHtml(data.channel_name)}] `;
  }
  return "";
}

function appendMessage(data) {
  const isDm = data.to_id !== 4294967295;
  const el = document.createElement("div");
  el.className = "msg broadcast";
  if (isDm) el.classList.add("dm");
  if (data.encrypted) el.classList.add("encrypted");

  const meta = document.createElement("span");
  meta.className = "meta";
  meta.textContent = formatTime(data.timestamp);

  const badge = data.encrypted ? '<span class="badge">🔒</span>' : "";
  const arrow = isDm ? ` → ${escapeHtml(data.to_short)}` : "";
  const ch = channelLabel(data);
  el.innerHTML = `${meta.outerHTML}${badge}${ch}<strong>${escapeHtml(data.from_short)}</strong>${arrow}: ${escapeHtml(data.text)}`;
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function getEnabledChannels(meshSettings) {
  return (meshSettings?.channels || [])
    .map((ch, index) => ({ ...ch, index }))
    .filter((ch) => ch.enabled && ch.name.trim());
}

function fillChannelSelect(selectEl, meshSettings, previousValue) {
  if (!selectEl) return;
  const enabled = getEnabledChannels(meshSettings || settings?.meshtastic);
  const current = previousValue ?? selectEl.value;
  selectEl.innerHTML = "";

  for (const ch of enabled) {
    const opt = document.createElement("option");
    opt.value = String(ch.index);
    opt.textContent = `${ch.index}: ${ch.name}`;
    selectEl.appendChild(opt);
  }

  const active = meshSettings?.active_channel ?? settings?.meshtastic?.active_channel ?? 0;
  if (enabled.some((ch) => ch.index === Number(current))) {
    selectEl.value = String(current);
  } else if (enabled.some((ch) => ch.index === active)) {
    selectEl.value = String(active);
  } else if (enabled.length) {
    selectEl.value = String(enabled[0].index);
  }
}

function getChannelIndexByName(meshSettings, name) {
  const channels = meshSettings?.channels || settings?.meshtastic?.channels || [];
  const target = name.trim().toLowerCase();
  for (let index = 0; index < channels.length; index += 1) {
    const ch = channels[index];
    if (ch.enabled && ch.name.trim().toLowerCase() === target) {
      return index;
    }
  }
  return null;
}

function updateSendChannelSelect(meshSettings) {
  fillChannelSelect(sendChannelSelect, meshSettings, sendChannelSelect.value);
  renderPresets();
}

// Info Routes 42 — desactive pour le moment (reactiver le bloc commente + index.html, map.js, main.py)
function updateInforouteRelayState() {}
function applyInforouteEnabled() {}
function isInforouteEnabled() { return false; }

function openMapWindow() {
  const features = "noopener,noreferrer,width=1200,height=820";
  window.open("/map", "meshqtt-map", features);
}

/*
function getInforouteDefaultChannelIndex(meshSettings) {
  const mesh = meshSettings || settings?.meshtastic;
  const named = getChannelIndexByName(mesh, INFOROUTE_DEFAULT_CHANNEL);
  if (named != null) return named;
  const active = mesh?.active_channel ?? 0;
  const enabled = getEnabledChannels(mesh);
  if (enabled.some((ch) => ch.index === active)) return active;
  return enabled[0]?.index ?? null;
}

function updateSendChannelSelect(meshSettings) {
  fillChannelSelect(sendChannelSelect, meshSettings, sendChannelSelect.value);
  const preferred =
    inforouteChannelSelect?.value ||
    String(getInforouteDefaultChannelIndex(meshSettings) ?? "");
  fillChannelSelect(inforouteChannelSelect, meshSettings, preferred);
  renderPresets();
}

function updateInforouteRelayState() {
  const hasText = Boolean(inforouteMeshText?.value.trim());
  const hasChannel = inforouteChannelSelect?.options.length > 0;
  if (inforouteChannelSelect) {
    inforouteChannelSelect.disabled = !isConnected || !hasChannel;
  }
  if (inforouteMeshText) {
    inforouteMeshText.disabled = !isConnected;
  }
  if (inforouteRelayBtn) {
    inforouteRelayBtn.disabled = !isConnected || !hasText || !hasChannel;
  }
  updateInforouteEventSendButtons();
}

const INFOROUTE_EVENT_CATEGORIES = [
  { id: "accident", label: "Accident" },
  { id: "danger", label: "Danger" },
  { id: "travaux", label: "Travaux" },
  { id: "gravillonnage", label: "Gravillonnage" },
  { id: "autres", label: "Autres" },
  { id: "deviation", label: "Déviation" },
];

function buildInforouteEventMeshText(ev) {
  const parts = [];
  const title = (ev.title || "").trim();
  const desc = (ev.description || "").trim();
  const period = (ev.period || "").trim();
  if (title) parts.push(title);
  if (desc) parts.push(desc);
  if (period) parts.push(period);
  if (!parts.length) return "";

  let msg = parts.join("\n");
  if (meshMessageByteLength(msg) > MESH_MESSAGE_MAX_BYTES) {
    msg = parts.join(" ");
  }
  return clampMeshMessage(msg);
}

function formatInforouteCoord(value) {
  if (value == null || value === "") return null;
  const num = Number(value);
  if (Number.isFinite(num)) return num.toFixed(6);
  return String(value);
}

function createInforouteGeoCommentElement(ev) {
  const hasGeo =
    ev.point_xy ||
    ev.point_latlng ||
    ev.latitude != null ||
    ev.longitude != null ||
    ev.latitude_from_xy != null ||
    ev.longitude_from_xy != null;
  if (!hasGeo) return null;

  const geo = document.createElement("div");
  geo.className = "inforoute-event-geo";
  const lines = [];

  if (ev.point_latlng) {
    lines.push(`point_latlng : ${ev.point_latlng}`);
  }
  if (ev.point_xy) {
    lines.push(`point_xy : ${ev.point_xy}`);
  }
  const lat = formatInforouteCoord(ev.latitude);
  const lon = formatInforouteCoord(ev.longitude);
  if (lat != null && lon != null) {
    lines.push(`latitude / longitude (XML) : ${lat}, ${lon}`);
  }
  const latXy = formatInforouteCoord(ev.latitude_from_xy);
  const lonXy = formatInforouteCoord(ev.longitude_from_xy);
  if (latXy != null && lonXy != null) {
    lines.push(
      "latitude / longitude (transform. xy → WGS84) : " + `${latXy}, ${lonXy}`
    );
    lines.push(
      "formule : lat = -6.422e-05·x - 0.00245244·y + 46.296656 ; " +
        "lon = 0.00175586·x - 4.598e-05·y + 3.694272"
    );
  }

  geo.textContent = lines.map((line) => `// ${line}`).join("\n");
  return geo;
}

function getInforouteEventLatLon(ev) {
  let lat = ev.latitude != null ? Number(ev.latitude) : NaN;
  let lon = ev.longitude != null ? Number(ev.longitude) : NaN;
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
    lat = ev.latitude_from_xy != null ? Number(ev.latitude_from_xy) : NaN;
    lon = ev.longitude_from_xy != null ? Number(ev.longitude_from_xy) : NaN;
  }
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  return { lat, lon };
}

function buildInforouteWaypointPayload(ev) {
  const coords = getInforouteEventLatLon(ev);
  if (!coords) return null;
  return {
    latitude: coords.lat,
    longitude: coords.lon,
    name: (ev.title || "InfoR42").trim().slice(0, 30),
    description: (ev.description || "").trim().slice(0, 100),
  };
}

function updateInforouteEventSendButtons() {
  if (!inforouteContentEl) return;
  const canSend = isConnected;
  inforouteContentEl.querySelectorAll(".inforoute-event-send-btn").forEach((btn) => {
    btn.disabled = !canSend;
    const hasCoords = btn.dataset.hasCoords === "1";
    const wpHint = hasCoords
      ? ` · Ctrl+clic : repère carte → canal ${INFOROUTE_WAYPOINT_CHANNEL}`
      : "";
    btn.title = canSend
      ? `Clic : texte → ${INFOROUTE_DEFAULT_CHANNEL}${wpHint}`
      : "Connexion MQTT requise";
  });
  inforouteContentEl.querySelectorAll(".inforoute-event-msg-btn").forEach((btn) => {
    btn.disabled = !canSend;
  });
  inforouteContentEl.querySelectorAll(".inforoute-event-waypoint-btn").forEach((btn) => {
    const hasCoords = btn.dataset.hasCoords === "1";
    btn.disabled = !canSend || !hasCoords;
  });
}

function handleInforouteEventClick(ev, mouseEvent) {
  if (mouseEvent.ctrlKey || mouseEvent.metaKey) {
    mouseEvent.preventDefault();
    sendInforouteWaypointToMesh(ev, INFOROUTE_WAYPOINT_CHANNEL);
    return;
  }
  sendInforouteEventToMesh(ev);
}

function createInforouteEventsElement(events) {
  const wrap = document.createElement("div");
  wrap.className = "inforoute-events";

  for (const cat of INFOROUTE_EVENT_CATEGORIES) {
    const list = Array.isArray(events?.[cat.id]) ? events[cat.id] : [];
    if (!list.length) continue;

    const section = document.createElement("section");
    section.className = "inforoute-event-group";

    const heading = document.createElement("h3");
    heading.className = "inforoute-event-title";
    heading.innerHTML = `${escapeHtml(cat.label)}
      <span class="inforoute-event-count">${list.length}</span>`;
    section.appendChild(heading);

    const ul = document.createElement("ul");
    ul.className = "inforoute-event-list";

    for (const ev of list) {
      const coords = getInforouteEventLatLon(ev);
      const li = document.createElement("li");
      li.className = "inforoute-event-item";

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "inforoute-event-send-btn";
      btn.dataset.hasCoords = coords ? "1" : "0";
      btn.disabled = !isConnected;
      btn.title = isConnected
        ? `Clic : texte → ${INFOROUTE_DEFAULT_CHANNEL}${
            coords
              ? ` · Ctrl+clic : repère carte → canal ${INFOROUTE_WAYPOINT_CHANNEL}`
              : ""
          }`
        : "Connexion MQTT requise";

      if (ev.title) {
        const strong = document.createElement("strong");
        strong.textContent = ev.title;
        btn.appendChild(strong);
      }
      if (ev.description) {
        const desc = document.createElement("span");
        desc.className = "inforoute-event-desc";
        desc.textContent = ev.description;
        btn.appendChild(desc);
      }
      if (ev.period) {
        const period = document.createElement("span");
        period.className = "inforoute-event-period";
        period.textContent = ev.period;
        btn.appendChild(period);
      }

      btn.addEventListener("click", (e) => handleInforouteEventClick(ev, e));
      li.appendChild(btn);

      const actions = document.createElement("div");
      actions.className = "inforoute-event-actions";

      const msgBtn = document.createElement("button");
      msgBtn.type = "button";
      msgBtn.className = "btn inforoute-event-msg-btn";
      msgBtn.textContent = `Message → ${INFOROUTE_DEFAULT_CHANNEL}`;
      msgBtn.disabled = !isConnected;
      msgBtn.title = isConnected
        ? `Envoyer le texte sur ${INFOROUTE_DEFAULT_CHANNEL}`
        : "Connexion MQTT requise";
      msgBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        sendInforouteEventToMesh(ev);
      });

      const wpBtn = document.createElement("button");
      wpBtn.type = "button";
      wpBtn.className = "btn inforoute-event-waypoint-btn";
      wpBtn.textContent = `📍 Repère → canal ${INFOROUTE_WAYPOINT_CHANNEL}`;
      wpBtn.dataset.hasCoords = coords ? "1" : "0";
      wpBtn.disabled = !isConnected || !coords;
      wpBtn.title = coords
        ? `Placer sur la carte Meshtastic (${coords.lat.toFixed(5)}, ${coords.lon.toFixed(5)}) — canal ${INFOROUTE_WAYPOINT_CHANNEL}`
        : "Coordonnées indisponibles pour ce signalement";
      wpBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        sendInforouteWaypointToMesh(ev, INFOROUTE_WAYPOINT_CHANNEL);
      });

      actions.appendChild(msgBtn);
      actions.appendChild(wpBtn);
      li.appendChild(actions);

      const geo = createInforouteGeoCommentElement(ev);
      if (geo) li.appendChild(geo);

      ul.appendChild(li);
    }

    section.appendChild(ul);
    wrap.appendChild(section);
  }

  return wrap;
}

function countWords(text) {
  const trimmed = (text || "").trim();
  if (!trimmed) return 0;
  return trimmed.split(/\s+/).filter(Boolean).length;
}

function getInforouteBulletinPlainText(data) {
  const parts = [];
  if (data.teaser) parts.push(String(data.teaser).trim());
  const items = Array.isArray(data.bulletin_items) ? data.bulletin_items : [];
  if (items.length) {
    for (const item of items) {
      const line = String(item).trim();
      if (line) parts.push(line);
    }
  } else if (data.bulletin_text) {
    parts.push(String(data.bulletin_text).trim());
  }
  return parts.join(" ");
}

function getInforouteBulletinStats(data) {
  const text = getInforouteBulletinPlainText(data);
  return {
    words: countWords(text),
    chars: text.length,
    utf8Bytes: meshMessageByteLength(text),
  };
}

function renderInforouteContent(data) {
  if (!inforouteContentEl) return;
  const updated = data.updated_at_display || data.updated_at;
  const updatedLabel = updated
    ? `Mise à jour du site : ${escapeHtml(updated)}`
    : "Info Routes 42 — Conseil départemental de la Loire";

  let body = "";
  if (data.teaser) {
    body += `<p class="inforoute-teaser">${escapeHtml(data.teaser)}</p>`;
  }

  const items = Array.isArray(data.bulletin_items) ? data.bulletin_items : [];
  if (items.length) {
    body += `<ul class="inforoute-list">${items
      .map((item) => `<li>${escapeHtml(item)}</li>`)
      .join("")}</ul>`;
  } else if (data.bulletin_text) {
    body += `<p>${escapeHtml(data.bulletin_text)}</p>`;
  }

  const bulletinStats = getInforouteBulletinStats(data);
  if (bulletinStats.words > 0) {
    const wordLabel = bulletinStats.words === 1 ? "mot" : "mots";
    const charLabel = bulletinStats.chars === 1 ? "caractère" : "caractères";
    body += `<p class="inforoute-bulletin-words">${bulletinStats.words} ${wordLabel} · ${bulletinStats.chars} ${charLabel} · ${bulletinStats.utf8Bytes} octets UTF-8</p>`;
  }

  inforouteContentEl.innerHTML = `<p class="inforoute-updated">${updatedLabel}</p>${body}`;

  const eventsEl = createInforouteEventsElement(data.events);
  if (eventsEl.childElementCount) {
    inforouteContentEl.appendChild(eventsEl);
  }

  if (data.phone) {
    const phone = document.createElement("p");
    phone.className = "inforoute-phone";
    phone.textContent = `Info routes : ${data.phone}`;
    inforouteContentEl.appendChild(phone);
  }
}

function isInforouteEnabled() {
  return settings?.ui?.inforoute_enabled !== false;
}

function stopInforouteAutoRefresh() {
  if (inforouteAutoRefreshTimer) {
    clearInterval(inforouteAutoRefreshTimer);
    inforouteAutoRefreshTimer = null;
  }
}

function applyInforouteEnabled(enabled) {
  const on = Boolean(enabled);
  if (inforoutePanel) inforoutePanel.hidden = !on;
  if (inforouteEnabledToggle) inforouteEnabledToggle.checked = on;
  notifyMapInforouteToggle(on);
  if (on) {
    startInforouteAutoRefresh();
  } else {
    stopInforouteAutoRefresh();
  }
}

function notifyMapInforouteToggle(enabled) {
  if (typeof BroadcastChannel === "undefined") return;
  if (!inforouteMapChannel) {
    inforouteMapChannel = new BroadcastChannel("meshqtt-inforoute42");
  }
  inforouteMapChannel.postMessage({
    type: "inforoute_enabled",
    enabled: Boolean(enabled),
  });
}

async function setInforouteEnabled(enabled) {
  try {
    await persistSettings({ ui: { inforoute_enabled: Boolean(enabled) } });
  } catch {
    // localStorage déjà à jour
  }
  applyInforouteEnabled(Boolean(enabled));
}

function broadcastInforouteToMap(payload) {
  if (!isInforouteEnabled()) return;
  if (typeof BroadcastChannel === "undefined") return;
  if (!inforouteMapChannel) {
    inforouteMapChannel = new BroadcastChannel("meshqtt-inforoute42");
  }
  inforouteMapChannel.postMessage({ type: "inforoute42", payload });
}

function openInforouteMapWindow() {
  const features = "noopener,noreferrer,width=1200,height=820";
  window.open("/map", "meshqtt-inforoute-map", features);
}

async function refreshInforoute42({ manual = true } = {}) {
  if (!isInforouteEnabled()) return;
  if (inforouteRefreshBusy) {
    if (manual) showToast("Actualisation déjà en cours", "error");
    return;
  }
  inforouteRefreshBusy = true;
  if (inforouteRefreshBtn) inforouteRefreshBtn.disabled = true;
  if (inforouteStatusEl) {
    inforouteStatusEl.textContent = manual
      ? "Chargement via Internet…"
      : "Actualisation automatique…";
    inforouteStatusEl.className = "inforoute-status loading";
  }
  try {
    const res = await fetch("/api/inforoute42", { cache: "no-store" });
    const payload = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = payload.detail;
      const message = Array.isArray(detail)
        ? detail[0]?.msg || detail[0]
        : detail;
      if (res.status === 404) {
        throw new Error(
          "Route API introuvable — redémarrez le serveur MeshQTT (uvicorn) puis réessayez"
        );
      }
      throw new Error(message || "Échec de la récupération");
    }
    renderInforouteContent(payload);
    const defaultChannel = getInforouteDefaultChannelIndex(settings?.meshtastic);
    if (inforouteChannelSelect && defaultChannel != null) {
      inforouteChannelSelect.value = String(defaultChannel);
    }
    if (inforouteStatusEl) {
      const when = payload.fetched_at
        ? new Date(payload.fetched_at).toLocaleString("fr-FR")
        : "maintenant";
      const totalEvents = Object.values(payload.event_counts || {}).reduce(
        (sum, n) => sum + Number(n || 0),
        0
      );
      inforouteStatusEl.textContent = `Actualisé le ${when} — ${totalEvents} signalement(s) — auto. 30 min`;
      inforouteStatusEl.className = "inforoute-status ok";
    }
    updateInforouteRelayState();
    broadcastInforouteToMap(payload);
  } catch (err) {
    if (inforouteStatusEl) {
      inforouteStatusEl.textContent = err.message || "Inforoute 42 inaccessible";
      inforouteStatusEl.className = "inforoute-status error";
    }
    if (manual) {
      showToast("Info Routes 42 : chargement impossible", "error");
    }
  } finally {
    inforouteRefreshBusy = false;
    if (inforouteRefreshBtn) inforouteRefreshBtn.disabled = false;
  }
}

function startInforouteAutoRefresh() {
  if (!isInforouteEnabled()) return;
  stopInforouteAutoRefresh();
  refreshInforoute42({ manual: false });
  inforouteAutoRefreshTimer = setInterval(
    () => refreshInforoute42({ manual: false }),
    INFOROUTE_AUTO_REFRESH_MS
  );
}

async function relayInforoute42ToMesh() {
  const text = inforouteMeshText?.value.trim();
  if (!text) return;
  const channel = parseInt(inforouteChannelSelect?.value, 10);
  if (Number.isNaN(channel)) return;
  await sendMeshMessage(text, channel, null);
}

async function sendInforouteEventToMesh(ev) {
  if (!isConnected) {
    showToast("Connectez-vous au broker MQTT", "error");
    return;
  }
  const channel = getInforouteDefaultChannelIndex(settings?.meshtastic);
  if (channel == null) {
    showToast(`Canal ${INFOROUTE_DEFAULT_CHANNEL} introuvable`, "error");
    return;
  }
  const text = buildInforouteEventMeshText(ev);
  if (!text) return;

  if (inforouteMeshText) {
    inforouteMeshText.value = text;
    updateMeshMessageCounter(inforouteMeshText, inforouteMeshCharCount);
  }
  if (inforouteChannelSelect) {
    inforouteChannelSelect.value = String(channel);
  }
  updateInforouteRelayState();
  await sendMeshMessage(text, channel, null);
}

async function sendMeshWaypoint(
  { latitude, longitude, name, description },
  channelIndex = null
) {
  if (!isConnected) {
    showToast("Connectez-vous pour envoyer", "error");
    return false;
  }

  const channel =
    channelIndex !== null && channelIndex !== undefined
      ? channelIndex
      : getInforouteDefaultChannelIndex(settings?.meshtastic);

  if (channel == null || !isChannelSendable(channel)) {
    showToast(
      `Canal ${getChannelLabel(channel)} non actif — vérifiez la config Meshtastic`,
      "error"
    );
    return false;
  }

  const res = await localFetch("/api/waypoint", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      latitude,
      longitude,
      name,
      description,
      channel,
    }),
  }).catch(() => null);

  if (!res?.ok) {
    showToast("Envoi du repère impossible", "error");
    return false;
  }

  appendSystem(
    `→ Repère [${getChannelLabel(channel)}] ${name} (${latitude.toFixed(5)}, ${longitude.toFixed(5)})`
  );
  showToast("Repère placé sur la carte mesh", "success");
  return true;
}

async function sendInforouteWaypointToMesh(ev, channelIndex = INFOROUTE_WAYPOINT_CHANNEL) {
  const payload = buildInforouteWaypointPayload(ev);
  if (!payload) {
    showToast("Coordonnées indisponibles pour ce signalement", "error");
    return;
  }
  if (!isChannelSendable(channelIndex)) {
    showToast(
      `Canal ${getChannelLabel(channelIndex)} non actif — vérifiez la config Meshtastic`,
      "error"
    );
    return;
  }
  await sendMeshWaypoint(payload, channelIndex);
}

*/

async function sendMeshWaypoint(
  { latitude, longitude, name, description },
  channelIndex = null
) {
  if (!isConnected) {
    showToast("Connectez-vous pour envoyer", "error");
    return false;
  }

  const channel =
    channelIndex !== null && channelIndex !== undefined
      ? channelIndex
      : (settings?.meshtastic?.active_channel ?? 0);

  if (channel == null || !isChannelSendable(channel)) {
    showToast(
      `Canal ${getChannelLabel(channel)} non actif — vérifiez la config Meshtastic`,
      "error"
    );
    return false;
  }

  const res = await localFetch("/api/waypoint", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      latitude,
      longitude,
      name,
      description,
      channel,
    }),
  }).catch(() => null);

  if (!res?.ok) {
    showToast("Envoi du repère impossible", "error");
    return false;
  }

  appendSystem(
    `→ Repère [${getChannelLabel(channel)}] ${name} (${latitude.toFixed(5)}, ${longitude.toFixed(5)})`
  );
  showToast("Repère placé sur la carte mesh", "success");
  return true;
}

function getNodeLabel(nodeId) {
  const n = nodes.get(nodeId);
  return n ? `${n.short_name} (${n.user_id})` : `nœud ${nodeId}`;
}

function updateDirectSendState() {
  const hasNode = Boolean(directDestinationSelect?.value);
  const canDirect =
    isConnected && directDestinationSelect.options.length > 1 && hasNode;
  sendDirectBtn.disabled = !canDirect;
}

function updateNodesList() {
  nodesListEl.innerHTML = "";
  nodeCountEl.textContent = nodes.size;

  const sorted = [...nodes.values()].sort((a, b) =>
    a.short_name.localeCompare(b.short_name)
  );

  const selectedNodeId = directDestinationSelect?.value || "";

  for (const n of sorted) {
    const li = document.createElement("li");
    li.className = "node-item";
    li.dataset.nodeId = String(n.node_id);
    if (String(n.node_id) === selectedNodeId) {
      li.classList.add("selected");
    }
    li.innerHTML = `<span class="short">${escapeHtml(n.short_name)}</span>
      <div class="id">${escapeHtml(n.user_id)}</div>
      <div>${escapeHtml(n.long_name)}</div>`;
    li.title = "Sélectionner pour message direct";
    li.addEventListener("click", () => {
      directDestinationSelect.value = String(n.node_id);
      nodesListEl.querySelectorAll(".node-item.selected").forEach((el) => {
        el.classList.remove("selected");
      });
      li.classList.add("selected");
      updateDirectSendState();
      if (!directMessageInput.disabled) {
        directMessageInput.focus();
      }
    });
    nodesListEl.appendChild(li);
  }

  directDestinationSelect.innerHTML = '<option value="">Choisir…</option>';
  for (const n of sorted) {
    const opt = document.createElement("option");
    opt.value = n.node_id;
    opt.textContent = `${n.short_name} (${n.user_id})`;
    directDestinationSelect.appendChild(opt);
  }
  if (selectedNodeId && sorted.some((n) => String(n.node_id) === selectedNodeId)) {
    directDestinationSelect.value = selectedNodeId;
  }
  updateDirectSendState();
}

function setConnected(connected, message) {
  isConnected = connected;
  statusBar.className = `status ${connected ? "connected" : "disconnected"}`;
  statusBar.textContent = message || (connected ? "Connecté" : "Déconnecté");
  const canSendGroup = connected && sendChannelSelect.options.length > 0;
  groupMessageInput.disabled = !canSendGroup;
  sendGroupBtn.disabled = !canSendGroup;
  sendChannelSelect.disabled = !canSendGroup;
  directMessageInput.disabled = !connected;
  directDestinationSelect.disabled = !connected;
  updateDirectSendState();
  // updateInforouteRelayState();
  connectBtn.disabled = connected;
  disconnectBtn.disabled = !connected;
  presetsListEl.querySelectorAll(".preset-send-btn").forEach((btn) => {
    btn.disabled = !connected;
  });
}

function normalizePresetItem(item) {
  const defaultChannel = settings?.meshtastic?.active_channel ?? 0;
  if (typeof item === "string") {
    return { text: item, channel: defaultChannel, visu: "", option: false };
  }
  const channel = Number.isFinite(Number(item?.channel))
    ? Math.max(0, Math.min(CHANNEL_COUNT - 1, Number(item.channel)))
    : defaultChannel;
  return {
    text: String(item?.text ?? ""),
    channel,
    visu: String(item?.visu ?? "").trim(),
    option: Boolean(item?.option),
  };
}

function normalizePresetsList(list) {
  return (list || []).map(normalizePresetItem).filter((p) => p.text);
}

function presetText(item) {
  return normalizePresetItem(item).text;
}

function getChannelLabel(index) {
  const ch = settings?.meshtastic?.channels?.[index];
  const name = ch?.name?.trim();
  return name ? `${index}: ${name}` : `Canal ${index}`;
}

function fillPresetChannelSelect(selectedChannel) {
  if (!presetChannelSelect) return;
  presetChannelSelect.innerHTML = "";
  const channels =
    settings?.meshtastic?.channels || DEFAULT_SETTINGS.meshtastic.channels;
  const fallback = settings?.meshtastic?.active_channel ?? 0;

  for (let i = 0; i < CHANNEL_COUNT; i++) {
    const ch = channels[i] || {};
    const opt = document.createElement("option");
    opt.value = String(i);
    const name = ch.name?.trim();
    opt.textContent = name ? `Canal ${i}: ${name}` : `Canal ${i} (non configuré)`;
    presetChannelSelect.appendChild(opt);
  }

  const selected = selectedChannel ?? fallback;
  presetChannelSelect.value = String(
    Math.max(0, Math.min(CHANNEL_COUNT - 1, selected))
  );
}

function isChannelSendable(channelIndex) {
  const enabled = getEnabledChannels(settings?.meshtastic);
  return enabled.some((ch) => ch.index === channelIndex);
}

function presetKey(item) {
  const p = normalizePresetItem(item);
  return `${p.text}\0${p.channel}\0${p.visu}\0${p.option}`;
}

function mergePresetLists(bundledList, localList) {
  const bundled = normalizePresetsList(bundledList || []);
  const local = normalizePresetsList(localList || []);
  const seen = new Set(bundled.map((p) => presetKey(p)));
  const extra = local.filter((p) => !seen.has(presetKey(p)));
  return [...bundled, ...extra];
}

function mergePresetCategories(bundled, local) {
  const base = Array.isArray(bundled) && bundled.length ? bundled : DEFAULT_PRESET_CATEGORIES;
  if (!Array.isArray(local) || !local.length) {
    return structuredClone(base);
  }
  const bundledById = new Map(base.map((c) => [c.id, { ...c }]));
  return local
    .map((cat) => {
      if (!cat?.id || !cat?.label) return null;
      const id = String(cat.id).trim();
      const label = String(cat.label).trim();
      if (!id || !label) return null;
      const fromBundled = bundledById.get(id);
      return { id, label: label || fromBundled?.label || id };
    })
    .filter(Boolean);
}

function readPresetCategoriesFromStorage() {
  try {
    const raw = localStorage.getItem(PRESET_CATEGORIES_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (
      Array.isArray(parsed) &&
      parsed.length > 0 &&
      parsed.every((c) => c && typeof c.id === "string" && typeof c.label === "string")
    ) {
      return parsed.map((c) => ({
        id: c.id.trim(),
        label: c.label.trim(),
      })).filter((c) => c.id && c.label);
    }
  } catch {
    /* ignore */
  }
  return null;
}

function readPresetsFromStorage() {
  try {
    const raw = localStorage.getItem(PRESETS_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed) || (parsed && typeof parsed === "object")) {
      return parsed;
    }
  } catch {
    /* ignore */
  }
  return null;
}

function getBundledCategories() {
  return bundledPresetsData?.categories?.length
    ? bundledPresetsData.categories
    : DEFAULT_PRESET_CATEGORIES;
}

function getBundledPresetsForCategory(categoryId) {
  if (bundledPresetsData?.presets?.[categoryId]) {
    return bundledPresetsData.presets[categoryId];
  }
  return DEFAULT_PRESETS[categoryId] || [];
}

async function loadBundledPresetsFromServer() {
  try {
    const res = await fetch("/api/presets-default", { cache: "no-store" });
    if (!res.ok) throw new Error("fetch failed");
    bundledPresetsData = await res.json();
  } catch {
    bundledPresetsData = {
      categories: structuredClone(DEFAULT_PRESET_CATEGORIES),
      presets: structuredClone(DEFAULT_PRESETS),
    };
  }
  presetCategories = loadPresetCategories();
}

function defaultPresetsCopy() {
  const data = {};
  for (const cat of presetCategories) {
    data[cat.id] = normalizePresetsList(getBundledPresetsForCategory(cat.id));
  }
  return data;
}

function readRemovedCategoryIds() {
  try {
    const raw = localStorage.getItem(PRESET_REMOVED_CATEGORIES_KEY);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return new Set(parsed.filter((id) => typeof id === "string" && id.trim()));
    }
  } catch {
    /* ignore */
  }
  return new Set();
}

function rememberRemovedCategoryId(categoryId) {
  const removed = readRemovedCategoryIds();
  removed.add(categoryId);
  localStorage.setItem(PRESET_REMOVED_CATEGORIES_KEY, JSON.stringify([...removed]));
}

function forgetRemovedCategoryId(categoryId) {
  const removed = readRemovedCategoryIds();
  if (!removed.delete(categoryId)) return;
  localStorage.setItem(
    PRESET_REMOVED_CATEGORIES_KEY,
    JSON.stringify([...removed])
  );
}

function loadPresetCategories() {
  const removed = readRemovedCategoryIds();
  const bundled = getBundledCategories();
  const fromStorage = readPresetCategoriesFromStorage();
  let categories = mergePresetCategories(bundled, fromStorage);
  if (removed.size) {
    categories = categories.filter((c) => !removed.has(c.id));
  }
  return categories;
}

function loadPresets() {
  const stored = readPresetsFromStorage();
  const out = {};
  for (const cat of presetCategories) {
    if (
      stored &&
      typeof stored === "object" &&
      !Array.isArray(stored) &&
      Array.isArray(stored[cat.id])
    ) {
      out[cat.id] = normalizePresetsList(stored[cat.id]);
    } else {
      out[cat.id] = normalizePresetsList(getBundledPresetsForCategory(cat.id));
    }
  }
  if (Array.isArray(stored)) {
    out.communautaire = mergePresetLists(out.communautaire || [], stored);
  }
  return out;
}

async function bakePresetsIntoApp() {
  const payload = {
    categories: presetCategories,
    presets: loadPresets(),
  };
  const count = Object.values(payload.presets).reduce(
    (sum, list) => sum + (list?.length || 0),
    0
  );
  const msg =
    `Enregistrer ${count} message(s) prédéfini(s) dans l'application ?\n` +
    "Ils seront visibles à chaque ouverture (même sans données locales).";
  if (!window.confirm(msg)) return;

  try {
    const res = await fetch("/api/presets-default", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("Échec de l'enregistrement");
    bundledPresetsData = await res.json();
    presetCategories = loadPresetCategories();
    initPresetCategorySelect();
    renderPresets();
    showToast("Messages prédéfinis intégrés dans l'application");
  } catch (err) {
    showToast(err.message || "Impossible d'intégrer les prédéfinis", "error");
  }
}

function getPresetCategoryLabel(categoryId) {
  return presetCategories.find((c) => c.id === categoryId)?.label || categoryId;
}

function slugifyCategoryId(label) {
  let base =
    label
      .normalize("NFD")
      .replace(/\p{M}/gu, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_|_$/g, "") || "rubrique";
  let id = base;
  let n = 2;
  while (presetCategories.some((c) => c.id === id)) {
    id = `${base}_${n++}`;
  }
  return id;
}

function fillPresetCatSelect(selectedId) {
  if (!presetCatSelect) return;
  presetCatSelect.innerHTML = "";
  for (const cat of presetCategories) {
    const opt = document.createElement("option");
    opt.value = cat.id;
    opt.textContent = cat.label;
    presetCatSelect.appendChild(opt);
  }
  if (presetCatSelect.options.length) {
    presetCatSelect.selectedIndex = 0;
  }
  if (selectedId && presetCategories.some((c) => c.id === selectedId)) {
    presetCatSelect.value = selectedId;
  }
}

function fillPresetDeleteSelect(selectedId) {
  if (!presetCatDeleteSelect) return;
  presetCatDeleteSelect.innerHTML = "";
  for (const cat of presetCategories) {
    const count = (loadPresets()[cat.id] || []).length;
    const opt = document.createElement("option");
    opt.value = cat.id;
    opt.textContent = count ? `${cat.label} (${count})` : `${cat.label} (vide)`;
    presetCatDeleteSelect.appendChild(opt);
  }
  if (presetCatDeleteSelect.options.length) {
    presetCatDeleteSelect.selectedIndex = 0;
  }
  if (selectedId && presetCategories.some((c) => c.id === selectedId)) {
    presetCatDeleteSelect.value = selectedId;
  }
  updatePresetDeleteHint();
}

function updatePresetDeleteHint() {
  if (!presetCatDeleteHint || !presetCatDeleteSelect) return;
  const catId = presetCatDeleteSelect.value;
  if (!catId) {
    presetCatDeleteHint.textContent = "Aucune rubrique disponible.";
    return;
  }
  const label = getPresetCategoryLabel(catId);
  const count = (loadPresets()[catId] || []).length;
  presetCatDeleteHint.textContent =
    count > 0
      ? `« ${label} » et ses ${count} message(s) seront supprimés.`
      : `« ${label} » sera retirée (rubrique vide).`;
}

function updatePresetCatModalDeleteHint() {
  if (!presetCatHint || !presetCatSelect) return;
  const catId = presetCatSelect.value;
  if (!catId) {
    presetCatHint.textContent = "Aucune rubrique disponible.";
    return;
  }
  const label = getPresetCategoryLabel(catId);
  const count = (loadPresets()[catId] || []).length;
  presetCatHint.textContent =
    count > 0
      ? `« ${label} » et ses ${count} message(s) seront supprimés.`
      : `« ${label} » sera retirée (rubrique vide).`;
}

function showPresetDeleteBar() {
  if (!presetCatDeleteBar) return;
  fillPresetDeleteSelect();
  if (presetCategories.length <= 1) {
    showToast("Impossible de supprimer la dernière rubrique", "error");
    return;
  }
  presetCatDeleteBar.hidden = false;
  presetCatDeleteSelect?.focus();
}

function hidePresetDeleteBar() {
  if (presetCatDeleteBar) presetCatDeleteBar.hidden = true;
}

async function syncBundledPresetsToServer() {
  const payload = {
    categories: presetCategories,
    presets: loadPresets(),
  };
  const res = await fetch("/api/presets-default", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Échec sync serveur");
  bundledPresetsData = await res.json();
}

async function executePresetCategoryDelete(catId) {
  if (!catId) {
    showToast("Choisissez une rubrique à supprimer", "error");
    return false;
  }
  if (presetCategories.length <= 1) {
    showToast("Impossible de supprimer la dernière rubrique", "error");
    return false;
  }
  const label = getPresetCategoryLabel(catId);
  const nextCategories = presetCategories.filter((c) => c.id !== catId);
  const presets = loadPresets();
  delete presets[catId];
  savePresets(presets);
  persistPresetCategories(nextCategories, { removedCategoryId: catId });
  hidePresetDeleteBar();
  closePresetCatModal();
  try {
    await syncBundledPresetsToServer();
  } catch {
    showToast(`Rubrique « ${label} » supprimée (cache local)`, "ok");
    return true;
  }
  showToast(`Rubrique « ${label} » supprimée`);
  return true;
}

function syncPresetsStorageForCategories(categories) {
  const presets = loadPresets();
  const out = {};
  for (const cat of categories) {
    out[cat.id] = presets[cat.id] || [];
  }
  localStorage.setItem(PRESETS_KEY, JSON.stringify(out));
}

function persistPresetCategories(categories, { removedCategoryId = null } = {}) {
  if (removedCategoryId) {
    rememberRemovedCategoryId(removedCategoryId);
  }
  presetCategories = categories;
  localStorage.setItem(PRESET_CATEGORIES_KEY, JSON.stringify(categories));
  syncPresetsStorageForCategories(categories);
  openPresetCategories = new Set(
    [...openPresetCategories].filter((id) => categories.some((c) => c.id === id))
  );
  saveOpenPresetCategories();
  initPresetCategorySelect();
  fillPresetCatSelect(presetCatSelect?.value || categories[0]?.id);
  renderPresets();
}

function openPresetCatModal(mode) {
  presetCatModalMode = mode;
  if (!presetCatModal || !presetCatLabelInput) return;

  fillPresetCatSelect(presetCatSelect?.value || presetCategories[0]?.id);

  if (mode === "add") {
    presetCatModalTitle.textContent = "Ajouter une rubrique";
    presetCatSelectWrap.hidden = true;
    presetCatLabelWrap.hidden = false;
    presetCatLabelInput.disabled = false;
    presetCatLabelInput.value = "";
    presetCatLabelInput.required = true;
    presetCatHint.textContent =
      "La rubrique apparaîtra dans la liste des messages prédéfinis.";
    if (presetCatSubmitBtn) {
      presetCatSubmitBtn.textContent = "Valider";
      presetCatSubmitBtn.classList.remove("danger");
    }
  } else if (mode === "edit") {
    presetCatModalTitle.textContent = "Modifier une rubrique";
    presetCatSelectWrap.hidden = false;
    presetCatLabelWrap.hidden = false;
    presetCatLabelInput.disabled = false;
    presetCatLabelInput.required = true;
    const cat = presetCategories.find((c) => c.id === presetCatSelect.value);
    presetCatLabelInput.value = cat?.label || "";
    presetCatHint.textContent = "Renomme la rubrique sélectionnée.";
    if (presetCatSubmitBtn) {
      presetCatSubmitBtn.textContent = "Valider";
      presetCatSubmitBtn.classList.remove("danger");
    }
  } else if (mode === "delete") {
    if (presetCategories.length <= 1) {
      showToast("Impossible de supprimer la dernière rubrique", "error");
      return;
    }
    presetCatModalTitle.textContent = "Supprimer une rubrique";
    presetCatSelectWrap.hidden = false;
    presetCatLabelWrap.hidden = true;
    presetCatLabelInput.required = false;
    presetCatLabelInput.disabled = true;
    presetCatLabelInput.value = "";
    if (presetCatSubmitBtn) {
      presetCatSubmitBtn.textContent = "Supprimer";
      presetCatSubmitBtn.classList.add("danger");
    }
    updatePresetCatModalDeleteHint();
  }

  hidePresetDeleteBar();
  openModal(presetCatModal);
  if (mode === "add" || mode === "edit") {
    presetCatLabelInput.focus();
  } else if (mode === "delete") {
    presetCatSelect?.focus();
  }
}

function closePresetCatModal() {
  if (presetCatModal?.open) presetCatModal.close();
}

function submitPresetCatModal() {
  if (presetCatModalMode === "add") {
    const label = presetCatLabelInput.value.trim();
    if (!label) return;
    if (presetCategories.some((c) => c.label.toLowerCase() === label.toLowerCase())) {
      showToast("Une rubrique avec ce nom existe déjà", "error");
      return;
    }
    const id = slugifyCategoryId(label);
    forgetRemovedCategoryId(id);
    persistPresetCategories([...presetCategories, { id, label }]);
    closePresetCatModal();
    showToast(`Rubrique « ${label} » ajoutée`);
    return;
  }

  if (presetCatModalMode === "edit") {
    const catId = presetCatSelect.value;
    const label = presetCatLabelInput.value.trim();
    if (!catId || !label) return;
    if (
      presetCategories.some(
        (c) => c.id !== catId && c.label.toLowerCase() === label.toLowerCase()
      )
    ) {
      showToast("Une rubrique avec ce nom existe déjà", "error");
      return;
    }
    const next = presetCategories.map((c) =>
      c.id === catId ? { ...c, label } : c
    );
    persistPresetCategories(next);
    closePresetCatModal();
    showToast(`Rubrique renommée : ${label}`);
    return;
  }

  if (presetCatModalMode !== "delete") return;

  void executePresetCategoryDelete(presetCatSelect.value);
}

function normalizePresetsByCategory(data) {
  const out = {};
  for (const cat of presetCategories) {
    out[cat.id] = normalizePresetsList(data[cat.id]);
  }
  return out;
}

function loadOpenPresetCategories() {
  try {
    const raw = localStorage.getItem(PRESETS_OPEN_KEY);
    if (raw) {
      const ids = JSON.parse(raw);
      if (Array.isArray(ids)) return new Set(ids);
    }
  } catch {
    /* ignore */
  }
  return new Set();
}

function saveOpenPresetCategories() {
  localStorage.setItem(PRESETS_OPEN_KEY, JSON.stringify([...openPresetCategories]));
}

function savePresets(data) {
  const out = {};
  for (const cat of presetCategories) {
    out[cat.id] = data[cat.id] || [];
  }
  localStorage.setItem(PRESETS_KEY, JSON.stringify(out));
}

function initPresetCategorySelect() {
  presetCategorySelect.innerHTML = "";
  for (const cat of presetCategories) {
    const opt = document.createElement("option");
    opt.value = cat.id;
    opt.textContent = cat.label;
    presetCategorySelect.appendChild(opt);
  }
}

function togglePresetCategory(categoryId) {
  if (openPresetCategories.has(categoryId)) {
    openPresetCategories.delete(categoryId);
  } else {
    openPresetCategories.add(categoryId);
  }
  saveOpenPresetCategories();
  renderPresets();
}

function updatePresetCharCount() {
  updateMeshMessageCounter(presetInput, presetCharCount);
}

function updatePresetSendCharCount() {
  updateMeshMessageCounter(presetSendInput, presetSendCharCount);
}

function openPresetSendModal(item) {
  const normalized = normalizePresetItem(item);
  presetSendState = {
    channel: normalized.channel,
    template: normalized.text,
  };
  const label = normalized.visu || normalized.text;
  presetSendModalTitle.textContent = `Compléter — ${label}`;
  presetSendChannelHint.textContent = `Canal : ${getChannelLabel(normalized.channel)}`;
  presetSendInput.value = normalized.text;
  updatePresetSendCharCount();
  openModal(presetSendModal);
  presetSendInput.focus();
  presetSendInput.setSelectionRange(
    presetSendInput.value.length,
    presetSendInput.value.length
  );
}

function closePresetSendModal() {
  if (presetSendModal?.open) presetSendModal.close();
  presetSendState = null;
  if (presetSendInput) presetSendInput.value = "";
}

async function submitPresetSendModal() {
  if (!presetSendState) return;
  const text = presetSendInput.value.trim();
  if (!text) return;
  if (!isMeshMessageValid(text)) {
    meshMessageTooLongToast(text);
    return;
  }
  const channel = presetSendState.channel;
  closePresetSendModal();
  await sendMeshMessage(text, channel);
}

function handlePresetSendClick(item) {
  const normalized = normalizePresetItem(item);
  if (normalized.option) {
    openPresetSendModal(normalized);
  } else {
    sendMeshMessage(normalized.text, normalized.channel);
  }
}

function openPresetModalCreate(categoryId) {
  presetEditState = null;
  presetModalTitle.textContent = "Nouveau message";
  presetCategorySelect.value = categoryId || presetCategories[0]?.id || "";
  presetVisuInput.value = "";
  if (presetOptionInput) presetOptionInput.checked = false;
  presetInput.value = "";
  fillPresetChannelSelect();
  updatePresetCharCount();
  openModal(presetModal);
  presetVisuInput.focus();
}

function openPresetModalEdit(categoryId, index) {
  const item = normalizePresetItem(loadPresets()[categoryId][index]);
  presetEditState = { categoryId, index };
  presetModalTitle.textContent = "Modifier le message";
  presetCategorySelect.value = categoryId;
  presetVisuInput.value = item.visu;
  if (presetOptionInput) presetOptionInput.checked = item.option;
  presetInput.value = item.text;
  fillPresetChannelSelect(item.channel);
  updatePresetCharCount();
  openPresetCategories.add(categoryId);
  saveOpenPresetCategories();
  renderPresets();
  openModal(presetModal);
  presetVisuInput.focus();
  presetVisuInput.select();
}

function closePresetModal() {
  if (presetModal.open) presetModal.close();
  presetEditState = null;
  presetVisuInput.value = "";
  if (presetOptionInput) presetOptionInput.checked = false;
  presetInput.value = "";
  renderPresets();
}

function savePresetFromModal(text, categoryId, channelIndex, visu = "", option = false) {
  if (!isMeshMessageValid(text)) {
    meshMessageTooLongToast(text);
    return false;
  }
  const presets = loadPresets();
  if (!presets[categoryId]) presets[categoryId] = [];
  const entry = {
    text,
    visu: String(visu ?? "").trim(),
    option: Boolean(option),
    channel: Math.max(0, Math.min(CHANNEL_COUNT - 1, channelIndex)),
  };

  if (presetEditState) {
    const { categoryId: oldCat, index: oldIdx } = presetEditState;
    const duplicate = presets[categoryId].some(
      (msg, i) =>
        presetText(msg) === text && !(oldCat === categoryId && i === oldIdx)
    );
    if (duplicate) {
      showToast("Ce message existe déjà dans cette rubrique", "error");
      return false;
    }

    if (oldCat === categoryId) {
      presets[categoryId][oldIdx] = entry;
    } else {
      presets[oldCat].splice(oldIdx, 1);
      presets[categoryId].push(entry);
    }
    savePresets(presets);
    closePresetModal();
    showToast("Message modifié");
    return true;
  }

  if (presets[categoryId].some((msg) => presetText(msg) === text)) {
    showToast("Ce message existe déjà dans cette rubrique", "error");
    return false;
  }

  presets[categoryId].push(entry);
  savePresets(presets);
  openPresetCategories.add(categoryId);
  saveOpenPresetCategories();
  closePresetModal();
  const label = getPresetCategoryLabel(categoryId);
  showToast(`Message ajouté — ${label}`);
  return true;
}

function removePresetMessage(categoryId, index) {
  const next = loadPresets();
  next[categoryId] = next[categoryId].filter((_, idx) => idx !== index);
  savePresets(next);
  renderPresets();
  if (
    presetEditState &&
    presetEditState.categoryId === categoryId &&
    presetEditState.index === index
  ) {
    closePresetModal();
  } else if (
    presetEditState &&
    presetEditState.categoryId === categoryId &&
    presetEditState.index > index
  ) {
    presetEditState.index -= 1;
  }
}

function renderPresets() {
  const presets = loadPresets();
  presetsListEl.innerHTML = "";
  const canSend = isConnected;

  for (const cat of presetCategories) {
    const messages = presets[cat.id] || [];
    if (!messages.length) continue;
    const section = document.createElement("section");
    section.className =
      "preset-category" + (openPresetCategories.has(cat.id) ? " open" : "");

    const header = document.createElement("button");
    header.type = "button";
    header.className = "preset-category-header";
    header.innerHTML = `<span class="preset-category-title">${escapeHtml(cat.label)}</span>
      <span class="preset-category-count">${messages.length}</span>
      <span class="preset-category-chevron" aria-hidden="true">▶</span>`;
    header.addEventListener("click", () => togglePresetCategory(cat.id));

    const body = document.createElement("div");
    body.className = "preset-category-body";
    const ul = document.createElement("ul");

    messages.forEach((rawItem, index) => {
      const item = normalizePresetItem(rawItem);
      const visuText = item.visu || item.text;
      const li = document.createElement("li");

      const sendBtnEl = document.createElement("button");
      sendBtnEl.type = "button";
      sendBtnEl.className = "btn preset-send-btn";
      sendBtnEl.textContent = visuText;
      const optionHint = item.option ? " — compléter avant envoi" : "";
      sendBtnEl.title = canSend
        ? `${item.text}${optionHint} — ${getChannelLabel(item.channel)}`
        : `${item.text}${optionHint} (connexion requise pour envoyer)`;
      if (item.option) {
        sendBtnEl.classList.add("preset-send-btn-option");
      }
      sendBtnEl.disabled = !canSend;
      sendBtnEl.addEventListener("click", (e) => {
        e.stopPropagation();
        handlePresetSendClick(item);
      });

      const editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.className = "btn preset-edit-btn";
      editBtn.textContent = "✎";
      editBtn.title = "Modifier";
      editBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        openPresetModalEdit(cat.id, index);
      });

      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "btn preset-del-btn";
      delBtn.textContent = "✕";
      delBtn.title = "Supprimer";
      delBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        removePresetMessage(cat.id, index);
      });

      li.appendChild(sendBtnEl);
      li.appendChild(editBtn);
      li.appendChild(delBtn);
      ul.appendChild(li);
    });
    body.appendChild(ul);

    section.appendChild(header);
    section.appendChild(body);
    presetsListEl.appendChild(section);
  }
}

async function sendMeshMessage(text, channelIndex = null, toNodeId = null) {
  const trimmed = text.trim();
  if (!trimmed) return;
  if (!isMeshMessageValid(trimmed)) {
    meshMessageTooLongToast(trimmed);
    return;
  }
  if (!isConnected) {
    showToast("Connectez-vous pour envoyer", "error");
    return;
  }

  let channel =
    channelIndex !== null && channelIndex !== undefined
      ? channelIndex
      : parseInt(sendChannelSelect.value, 10);

  if (!isChannelSendable(channel)) {
    showToast(`Canal ${getChannelLabel(channel)} non actif — vérifiez la config Meshtastic`, "error");
    return;
  }

  const body = { text: trimmed, channel };
  if (toNodeId !== null && toNodeId !== undefined && toNodeId !== "") {
    body.to = Number(toNodeId);
  }

  const res = await localFetch("/api/send", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).catch(() => null);

  if (!res?.ok) {
    showToast("Envoi impossible", "error");
    return;
  }

  if (body.to) {
    appendSystem(
      `→ Direct [${getChannelLabel(channel)}] → ${getNodeLabel(body.to)} : ${trimmed}`
    );
  } else {
    appendSystem(`→ Groupe [${getChannelLabel(channel)}] : ${trimmed}`);
  }
}

function openModal(dialog) {
  if (typeof dialog.showModal === "function") {
    dialog.showModal();
  }
}

function closeModal(id) {
  const dialog = document.getElementById(id);
  if (dialog) dialog.close();
}

document.querySelectorAll(".modal-close").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.dataset.close === "preset-modal") {
      closePresetModal();
    } else if (btn.dataset.close === "preset-send-modal") {
      closePresetSendModal();
    } else if (btn.dataset.close === "preset-cat-modal") {
      closePresetCatModal();
    } else {
      closeModal(btn.dataset.close);
    }
  });
});

presetNewBtn.addEventListener("click", () => openPresetModalCreate());

presetCatAddBtn?.addEventListener("click", () => openPresetCatModal("add"));
presetCatEditBtn?.addEventListener("click", () => openPresetCatModal("edit"));
presetCatDelBtn?.addEventListener("click", () => openPresetCatModal("delete"));
presetBakeBtn?.addEventListener("click", () => bakePresetsIntoApp());

presetCatDeleteSelect?.addEventListener("change", updatePresetDeleteHint);
presetCatDeleteConfirmBtn?.addEventListener("click", () => {
  executePresetCategoryDelete(presetCatDeleteSelect?.value);
});
presetCatDeleteCancelBtn?.addEventListener("click", hidePresetDeleteBar);

presetCatSelect?.addEventListener("change", () => {
  if (presetCatModalMode === "edit") {
    const cat = presetCategories.find((c) => c.id === presetCatSelect.value);
    presetCatLabelInput.value = cat?.label || "";
  } else if (presetCatModalMode === "delete") {
    updatePresetCatModalDeleteHint();
  }
});

presetCatForm?.addEventListener("submit", (e) => {
  e.preventDefault();
  submitPresetCatModal();
});

presetCatSubmitBtn?.addEventListener("click", () => {
  submitPresetCatModal();
});

presetInput.addEventListener("input", updatePresetCharCount);

presetSendInput?.addEventListener("input", updatePresetSendCharCount);

presetSendForm?.addEventListener("submit", (e) => {
  e.preventDefault();
  submitPresetSendModal();
});

presetForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = presetInput.value.trim();
  const visu = presetVisuInput.value.trim();
  const option = presetOptionInput?.checked ?? false;
  const categoryId = presetCategorySelect.value;
  const channelIndex = parseInt(presetChannelSelect.value, 10);
  if (!text || !categoryId || Number.isNaN(channelIndex)) return;
  savePresetFromModal(text, categoryId, channelIndex, visu, option);
});

// Info Routes 42 — desactive pour le moment
// inforouteRefreshBtn?.addEventListener("click", () => refreshInforoute42({ manual: true }));
mapBtn?.addEventListener("click", () => openMapWindow());
// inforouteEnabledToggle?.addEventListener("change", () => {
//   setInforouteEnabled(inforouteEnabledToggle.checked);
// });
// inforouteRelayBtn?.addEventListener("click", () => relayInforoute42ToMesh());
// inforouteMeshText?.addEventListener("input", () => { ... });

document.getElementById("mqtt-settings-btn").addEventListener("click", () => {
  fillMqttForm();
  openModal(mqttModal);
});

document.getElementById("mesh-settings-btn").addEventListener("click", () => {
  buildChannelEditor();
  fillMeshForm();
  openModal(meshModal);
});

proposeNodeIdBtn?.addEventListener("click", () => {
  const id = proposeNodeIdIntoForm();
  showToast(`ID proposé : ${id}`);
});

function fillForm(form, data) {
  for (const [key, value] of Object.entries(data)) {
    const input = form.elements.namedItem(key);
    if (input && value != null && key !== "channels") {
      input.value = value;
    }
  }
}

function fillMqttForm() {
  if (!settings?.mqtt) return;
  const mqtt = settings.mqtt;
  for (const name of ["broker", "port", "username", "password", "root_topic"]) {
    const input = mqttForm.elements.namedItem(name);
    if (input) {
      input.value = mqtt[name] ?? "";
    }
  }
}

function buildChannelEditor() {
  channelTabsEl.innerHTML = "";
  channelPanelsEl.innerHTML = "";
  activeChannelSelect.innerHTML = "";

  for (let i = 0; i < CHANNEL_COUNT; i++) {
    const tab = document.createElement("button");
    tab.type = "button";
    tab.className = "channel-tab" + (i === activeChannelTab ? " active" : "");
    tab.dataset.index = i;
    tab.setAttribute("role", "tab");
    tab.textContent = String(i);
    tab.title = `Canal ${i}`;
    channelTabsEl.appendChild(tab);

    const panel = document.createElement("div");
    panel.className = "channel-panel" + (i === activeChannelTab ? " active" : "");
    panel.dataset.index = i;
    panel.innerHTML = `
      <label>
        Rôle
        <select name="ch_${i}_role">
          ${channelRoleOptionsHtml(i === 0 ? "PRINCIPAL" : "DESACTIVE")}
        </select>
      </label>
      <label>
        Nom du canal
        <input name="ch_${i}_name" placeholder="Ex. LongFast, Private…" />
      </label>
      <label>
        Clé PSK (base64)
        <input name="ch_${i}_key" placeholder="AQ== pour le canal par défaut" />
      </label>
    `;
    channelPanelsEl.appendChild(panel);

    const opt = document.createElement("option");
    opt.value = i;
    opt.textContent = `Canal ${i}`;
    activeChannelSelect.appendChild(opt);
  }

  channelTabsEl.querySelectorAll(".channel-tab").forEach((tab) => {
    tab.addEventListener("click", () => selectChannelTab(Number(tab.dataset.index)));
  });
}

function selectChannelTab(index) {
  activeChannelTab = index;
  channelTabsEl.querySelectorAll(".channel-tab").forEach((tab) => {
    tab.classList.toggle("active", Number(tab.dataset.index) === index);
  });
  channelPanelsEl.querySelectorAll(".channel-panel").forEach((panel) => {
    panel.classList.toggle("active", Number(panel.dataset.index) === index);
  });
}

function fillMeshForm() {
  if (!settings) return;
  const mesh = settings.meshtastic;

  fillForm(meshForm, {
    short_name: mesh.short_name,
    long_name: mesh.long_name,
    active_channel: mesh.active_channel ?? 0,
    node_id:
      mesh.node_id != null
        ? formatNodeId(mesh.node_id)
        : "",
  });

  if (mesh.node_id == null && nodeIdInput && !nodeIdInput.value.trim()) {
    proposeNodeIdIntoForm();
  }

  const channels = normalizeChannelsList(mesh.channels || []);
  for (let i = 0; i < CHANNEL_COUNT; i++) {
    const ch = channels[i];
    const role = meshForm.elements.namedItem(`ch_${i}_role`);
    const name = meshForm.elements.namedItem(`ch_${i}_name`);
    const key = meshForm.elements.namedItem(`ch_${i}_key`);
    if (role) role.value = ch.role;
    if (name) name.value = ch.name || "";
    if (key) key.value = ch.key || "";
  }

  selectChannelTab(mesh.active_channel ?? 0);
  updateActiveChannelLabels();
}

function updateActiveChannelLabels() {
  for (let i = 0; i < CHANNEL_COUNT; i++) {
    const nameInput = meshForm.elements.namedItem(`ch_${i}_name`);
    const opt = activeChannelSelect.querySelector(`option[value="${i}"]`);
    if (opt && nameInput) {
      const label = nameInput.value.trim();
      opt.textContent = label ? `Canal ${i}: ${label}` : `Canal ${i}`;
    }
  }
}

channelPanelsEl.addEventListener("input", (e) => {
  if (e.target.name && e.target.name.endsWith("_name")) {
    updateActiveChannelLabels();
  }
});

function readChannelsFromForm() {
  const channels = [];
  for (let i = 0; i < CHANNEL_COUNT; i++) {
    const roleEl = meshForm.elements.namedItem(`ch_${i}_role`);
    const name = meshForm.elements.namedItem(`ch_${i}_name`);
    const key = meshForm.elements.namedItem(`ch_${i}_key`);
    const role = normalizeChannelRole(roleEl?.value, i, false);
    channels.push({
      name: (name?.value || "").trim(),
      key: (key?.value || "").trim(),
      role,
      enabled: role !== "DESACTIVE",
    });
  }
  return channels;
}

function parseNodeId(raw) {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  const hex = trimmed.startsWith("!") ? trimmed.slice(1) : trimmed;
  if (!/^[0-9a-fA-F]{1,8}$/.test(hex)) {
    throw new Error("ID nœud invalide (hex attendu, ex. !a1b2c3d4)");
  }
  return parseInt(hex, 16);
}

async function localFetch(path, options = {}) {
  return fetch(path, { ...options, cache: "no-store" });
}

let settingsSyncGeneration = 0;

async function syncSettingsToServer(data) {
  const generation = ++settingsSyncGeneration;
  const res = await localFetch("/api/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mqtt: data.mqtt,
      meshtastic: data.meshtastic,
      ui: data.ui,
    }),
  });
  if (!res.ok) {
    throw new Error("Synchronisation serveur échouée");
  }
  const synced = await res.json();
  if (generation !== settingsSyncGeneration) {
    return synced;
  }
  settings = synced;
  saveLocalSettings(synced);
  return synced;
}

async function loadBundledSettingsFromServer() {
  try {
    const res = await localFetch("/api/settings");
    if (!res.ok) throw new Error("fetch failed");
    const data = await res.json();
    const merged = mergeSettings(DEFAULT_SETTINGS, data);
    if (merged.meshtastic?.channels) {
      merged.meshtastic.channels = normalizeChannelsList(merged.meshtastic.channels);
    }
    if (merged.mqtt?.root_topic) {
      merged.mqtt.root_topic = normalizeRootTopic(merged.mqtt.root_topic);
    }
    return merged;
  } catch {
    return structuredClone(DEFAULT_SETTINGS);
  }
}

async function loadSettings() {
  const server = await loadBundledSettingsFromServer();
  const local = loadLocalSettings();
  if (local) {
    settings = mergeSettings(server, local);
    // MQTT : settings.json serveur prime (évite localStorage bloqué sur 127.0.0.1)
    settings.mqtt = { ...local.mqtt, ...server.mqtt };
  } else {
    settings = server;
  }
  if (settings.meshtastic?.channels) {
    settings.meshtastic.channels = normalizeChannelsList(settings.meshtastic.channels);
  }
  if (settings.mqtt?.root_topic) {
    settings.mqtt.root_topic = normalizeRootTopic(settings.mqtt.root_topic);
  }
  saveLocalSettings(settings);
  updateSendChannelSelect(settings.meshtastic);
  applyTheme(normalizeTheme(settings.ui?.theme));
  // applyInforouteEnabled(isInforouteEnabled());
}

async function persistSettings(patch) {
  settings = mergeSettings(settings || DEFAULT_SETTINGS, patch);
  if (settings.meshtastic?.channels) {
    settings.meshtastic.channels = normalizeChannelsList(settings.meshtastic.channels);
  }
  saveLocalSettings(settings);
  return syncSettingsToServer(settings);
}

async function saveMqttSettings(event) {
  event.preventDefault();
  const fd = new FormData(mqttForm);
  const data = Object.fromEntries(fd.entries());
  data.port = parseInt(data.port, 10);
  data.broker = String(data.broker || "").trim();
  data.username = String(data.username || "").trim();
  data.password = String(data.password || "");
  data.root_topic = normalizeRootTopic(data.root_topic);

  const shouldReconnect = isConnected;

  try {
    await persistSettings({ mqtt: data });
    closeModal("mqtt-modal");
    showToast("Configuration MQTT enregistrée");
    if (shouldReconnect) {
      appendSystem("Reconnexion avec le nouveau root topic…");
      await connectToMesh();
    }
  } catch {
    showToast("Config enregistrée localement, sync serveur échouée", "error");
    if (shouldReconnect) {
      await connectToMesh().catch(() => {});
    }
  }
}

async function saveMeshSettings(event) {
  event.preventDefault();
  const fd = new FormData(meshForm);
  const data = Object.fromEntries(fd.entries());
  let nodeId = null;

  try {
    const rawId = (data.node_id || "").trim();
    if (rawId) {
      nodeId = parseNodeId(rawId);
    } else if (nodeIdInput?.value.trim()) {
      nodeId = parseNodeId(nodeIdInput.value);
    } else {
      nodeId = generateNodeIdProposal();
      if (nodeIdInput) nodeIdInput.value = formatNodeId(nodeId);
    }
  } catch (err) {
    showToast(err.message, "error");
    return;
  }

  const channels = readChannelsFromForm();
  const hasActive = channels.some((ch) => ch.role !== "DESACTIVE" && ch.name);
  if (!hasActive) {
    showToast("Configurez au moins un canal (rôle ≠ DESACTIVE) avec un nom", "error");
    return;
  }

  const activeChannel = parseInt(data.active_channel, 10);
  const activeSlot = channels[activeChannel];
  if (activeSlot.role === "DESACTIVE" || !activeSlot.name) {
    showToast("Le canal d'envoi par défaut doit être actif (≠ DESACTIVE) et nommé", "error");
    return;
  }

  const payload = {
    channels,
    active_channel: activeChannel,
    short_name: data.short_name.slice(0, 4),
    long_name: data.long_name,
    node_id: nodeId,
  };

  try {
    await persistSettings({ meshtastic: payload });
    updateSendChannelSelect(settings.meshtastic);
    closeModal("mesh-modal");
    showToast(`Configuration Meshtastic enregistrée — ${formatNodeId(nodeId)}`);
  } catch {
    showToast("Config enregistrée localement, sync serveur échouée", "error");
  }
}

mqttForm.addEventListener("submit", saveMqttSettings);
meshForm.addEventListener("submit", saveMeshSettings);

function getStoredTheme() {
  return normalizeTheme(
    settings?.ui?.theme || loadLocalSettings()?.ui?.theme
  );
}

function applyTheme(theme) {
  const resolved = normalizeTheme(theme);
  document.documentElement.setAttribute("data-theme", resolved);
  updateThemeButton(resolved);
}

function updateThemeButton(theme) {
  const isLight = theme === "light";
  themeBtn.textContent = isLight ? "☀" : "☾";
  themeBtn.title = isLight ? "Thème : Jour" : "Thème : Nuit";
}

async function cycleTheme() {
  const next = getStoredTheme() === "light" ? "dark" : "light";
  applyTheme(next);
  try {
    await persistSettings({ ui: { theme: next } });
  } catch {
    /* localStorage déjà à jour */
  }
}

themeBtn.addEventListener("click", cycleTheme);

connectBtn.addEventListener("click", () => connectToMesh());

async function connectToMesh() {
  refreshSettingsFromStorage();
  if (!settings) {
    settings = structuredClone(DEFAULT_SETTINGS);
  }
  if (settings.mqtt?.root_topic) {
    settings.mqtt.root_topic = normalizeRootTopic(settings.mqtt.root_topic);
  }
  appendSystem(`Connexion MQTT (${settings.mqtt.root_topic})…`);
  try {
    const res = await localFetch("/api/connect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mqtt: settings.mqtt,
        meshtastic: settings.meshtastic,
      }),
    });
    if (!res.ok) throw new Error("connect failed");
    const data = await res.json();
    if (data.node_name) {
      appendSystem(`Identité locale : ${data.node_name}`);
      if (settings.meshtastic) {
        const hex = data.node_name.replace("!", "");
        settings.meshtastic.node_id = parseInt(hex, 16);
        saveLocalSettings(settings);
      }
    }
  } catch {
    showToast("Connexion impossible — serveur ou broker MQTT local", "error");
  }
}

disconnectBtn.addEventListener("click", async () => {
  await localFetch("/api/disconnect", { method: "POST" }).catch(() => {});
  appendSystem("Déconnexion demandée");
});

sendGroupForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = groupMessageInput.value.trim();
  if (!text) return;
  const channel = parseInt(sendChannelSelect.value, 10);
  await sendMeshMessage(text, channel, null);
  groupMessageInput.value = "";
  updateMeshMessageCounter(groupMessageInput, groupMessageCharCount);
});

sendDirectForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = directMessageInput.value.trim();
  const to = directDestinationSelect.value;
  if (!text) return;
  if (!to) {
    showToast("Sélectionnez un nœud destinataire", "error");
    return;
  }
  await sendMeshMessage(text, 0, parseInt(to, 10));
  directMessageInput.value = "";
  updateMeshMessageCounter(directMessageInput, directMessageCharCount);
});

directDestinationSelect.addEventListener("change", () => {
  const nodeId = directDestinationSelect.value;
  nodesListEl.querySelectorAll(".node-item.selected").forEach((el) => {
    el.classList.remove("selected");
  });
  if (nodeId) {
    nodesListEl.querySelectorAll(".node-item").forEach((el) => {
      if (el.dataset.nodeId === nodeId) {
        el.classList.add("selected");
      }
    });
  }
  updateDirectSendState();
});

function connectWebSocket() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${proto}//${location.host}/ws`);

  ws.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    if (data.type === "status") {
      setConnected(data.connected, data.message);
      if (data.connected) appendSystem(data.message);
    } else if (data.type === "message") {
      appendMessage(data);
    } else if (data.type === "node") {
      nodes.set(data.from_id, {
        node_id: data.from_id,
        user_id: data.user_id,
        short_name: data.short_name || "?",
        long_name: data.long_name || data.user_id,
      });
      updateNodesList();
    } else if (data.type === "activity") {
      if (data.kind === "sent") {
        appendSystem(data.text || "↑ MQTT envoyé");
      } else {
        const ch = channelLabel(data);
        appendSystem(
          `↓ MQTT ${ch}${data.from_short || "?"} — ${data.text || data.kind || "activité"}`
        );
      }
    } else if (data.type === "error") {
      appendSystem("Erreur : " + data.message);
    }
  };

  ws.onclose = () => setTimeout(connectWebSocket, 2000);
}

async function init() {
  buildChannelEditor();
  bindMeshMessageInput(groupMessageInput, groupMessageCharCount);
  bindMeshMessageInput(directMessageInput, directMessageCharCount);
  // Info Routes 42 — desactive pour le moment
  // bindMeshMessageInput(inforouteMeshText, inforouteMeshCharCount);
  // updateInforouteRelayState();
  bindMeshMessageInput(presetInput, presetCharCount);
  bindMeshMessageInput(presetSendInput, presetSendCharCount);
  openPresetCategories = loadOpenPresetCategories();
  await loadBundledPresetsFromServer();
  initPresetCategorySelect();
  renderPresets();
  await loadSettings();
  applyTheme(getStoredTheme());

  connectWebSocket();

  const hasActiveChannel = settings?.meshtastic?.channels?.some(
    (ch) => ch.role !== "DESACTIVE" || ch.enabled
  );
  if (hasActiveChannel) {
    await connectToMesh().catch(() => {});
  }

  fetch("/api/status")
    .then((r) => (r.ok ? r.json() : null))
    .then((s) => {
      if (s) {
        setConnected(s.connected, s.connected ? `Connecté — ${s.node_name}` : "Déconnecté");
      }
    })
    .catch(() => {});

  fetch("/api/nodes")
    .then((r) => (r.ok ? r.json() : null))
    .then((d) => {
      if (!d) return;
      for (const n of d.nodes) nodes.set(n.node_id, n);
      updateNodesList();
    })
    .catch(() => {});
}

init();
