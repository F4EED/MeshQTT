"""Commente temporairement le code Info Routes 42 dans app.js et map.js."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def patch_app_js() -> None:
    path = ROOT / "app/static/app.js"
    text = path.read_text(encoding="utf-8")

    replacements = [
        (
            "const inforouteRefreshBtn = document.getElementById(\"inforoute-refresh-btn\");\n"
            "const inforouteStatusEl = document.getElementById(\"inforoute-status\");\n"
            "const inforouteContentEl = document.getElementById(\"inforoute-content\");\n"
            "const inforouteChannelSelect = document.getElementById(\"inforoute-channel\");\n"
            "const inforouteMeshText = document.getElementById(\"inforoute-mesh-text\");\n"
            "const inforouteMeshCharCount = document.getElementById(\"inforoute-mesh-char-count\");\n"
            "const inforouteRelayBtn = document.getElementById(\"inforoute-relay-btn\");\n",
            "// Info Routes 42 — desactive pour le moment\n"
            "// const inforouteRefreshBtn = document.getElementById(\"inforoute-refresh-btn\");\n"
            "// const inforouteStatusEl = document.getElementById(\"inforoute-status\");\n"
            "// const inforouteContentEl = document.getElementById(\"inforoute-content\");\n"
            "// const inforouteChannelSelect = document.getElementById(\"inforoute-channel\");\n"
            "// const inforouteMeshText = document.getElementById(\"inforoute-mesh-text\");\n"
            "// const inforouteMeshCharCount = document.getElementById(\"inforoute-mesh-char-count\");\n"
            "// const inforouteRelayBtn = document.getElementById(\"inforoute-relay-btn\");\n",
        ),
        (
            "const inforoutePanel = document.getElementById(\"inforoute-panel\");\n"
            "const inforouteEnabledToggle = document.getElementById(\"inforoute-enabled-toggle\");\n",
            "// const inforoutePanel = document.getElementById(\"inforoute-panel\");\n"
            "// const inforouteEnabledToggle = document.getElementById(\"inforoute-enabled-toggle\");\n",
        ),
        (
            "const INFOROUTE_DEFAULT_CHANNEL = \"D_Ligerien\";\n"
            "const INFOROUTE_WAYPOINT_CHANNEL = 0;\n"
            "const INFOROUTE_AUTO_REFRESH_MS = 30 * 60 * 1000;\n"
            "let inforouteRefreshBusy = false;\n"
            "let inforouteAutoRefreshTimer = null;\n"
            "let inforouteMapChannel = null;\n",
            "// Info Routes 42 — desactive pour le moment\n"
            "// const INFOROUTE_DEFAULT_CHANNEL = \"D_Ligerien\";\n"
            "// const INFOROUTE_WAYPOINT_CHANNEL = 0;\n"
            "// const INFOROUTE_AUTO_REFRESH_MS = 30 * 60 * 1000;\n"
            "// let inforouteRefreshBusy = false;\n"
            "// let inforouteAutoRefreshTimer = null;\n"
            "// let inforouteMapChannel = null;\n",
        ),
    ]
    for old, new in replacements:
        if old not in text:
            raise SystemExit(f"Bloc introuvable dans app.js:\n{old[:80]}...")
        text = text.replace(old, new, 1)

    start = text.index("function getInforouteDefaultChannelIndex(meshSettings) {")
    end = text.index("function getNodeLabel(nodeId) {")
    block = text[start:end]

    replacement = '''function updateSendChannelSelect(meshSettings) {
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
''' + block + '''*/

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

'''
    text = text[:start] + replacement + text[end:]

    listener_old = """inforouteRefreshBtn?.addEventListener("click", () => refreshInforoute42({ manual: true }));
mapBtn?.addEventListener("click", () => openInforouteMapWindow());
inforouteEnabledToggle?.addEventListener("change", () => {
  setInforouteEnabled(inforouteEnabledToggle.checked);
});
inforouteRelayBtn?.addEventListener("click", () => relayInforoute42ToMesh());
inforouteMeshText?.addEventListener("input", () => {
  const clamped = clampMeshMessage(inforouteMeshText.value);
  if (clamped !== inforouteMeshText.value) {
    inforouteMeshText.value = clamped;
  }
  updateMeshMessageCounter(inforouteMeshText, inforouteMeshCharCount);
  updateInforouteRelayState();
});
"""
    listener_new = """// Info Routes 42 — desactive pour le moment
// inforouteRefreshBtn?.addEventListener("click", () => refreshInforoute42({ manual: true }));
mapBtn?.addEventListener("click", () => openMapWindow());
// inforouteEnabledToggle?.addEventListener("change", () => {
//   setInforouteEnabled(inforouteEnabledToggle.checked);
// });
// inforouteRelayBtn?.addEventListener("click", () => relayInforoute42ToMesh());
// inforouteMeshText?.addEventListener("input", () => { ... });
"""
    if listener_old not in text:
        raise SystemExit("Event listeners inforoute introuvables")
    text = text.replace(listener_old, listener_new, 1)

    for old, new in [
        (
            "  bindMeshMessageInput(inforouteMeshText, inforouteMeshCharCount);\n"
            "  updateInforouteRelayState();\n",
            "  // Info Routes 42 — desactive pour le moment\n"
            "  // bindMeshMessageInput(inforouteMeshText, inforouteMeshCharCount);\n"
            "  // updateInforouteRelayState();\n",
        ),
        (
            "  applyInforouteEnabled(isInforouteEnabled());\n",
            "  // applyInforouteEnabled(isInforouteEnabled());\n",
        ),
        (
            "  updateInforouteRelayState();\n  connectBtn.disabled = connected;\n",
            "  // updateInforouteRelayState();\n  connectBtn.disabled = connected;\n",
        ),
    ]:
        if old not in text:
            raise SystemExit(f"Bloc init introuvable: {old!r}")
        text = text.replace(old, new, 1)

    path.write_text(text, encoding="utf-8")


def patch_map_js() -> None:
    path = ROOT / "app/static/map.js"
    text = path.read_text(encoding="utf-8")
    start = text.index('const INFOROUTE_AUTO_REFRESH_MS = 30 * 60 * 1000;')
    end = text.index('function initMap() {')
    block = text[start:end]
    replacement = '''// Info Routes 42 — desactive pour le moment
/*
''' + block + '''*/

'''
    text = text[:start] + replacement + text[end:]

    tail_old = """mapRefreshBtn?.addEventListener("click", () => refreshInforouteMap({ manual: true }));

window.addEventListener("storage", (event) => {
  if (event.key === SETTINGS_STORAGE_KEY) {
    applyInforouteLayerEnabled(loadInforouteEnabledFromSettings());
  }
});

initMap();
initBroadcast();
applyInforouteLayerEnabled(loadInforouteEnabledFromSettings());
"""
    tail_new = """// mapRefreshBtn?.addEventListener("click", () => refreshInforouteMap({ manual: true }));
// window.addEventListener("storage", ...);

initMap();
setMapStatus("Fond OSM — Info Routes 42 desactive", "");
// initBroadcast();
// applyInforouteLayerEnabled(loadInforouteEnabledFromSettings());
"""
    if tail_old not in text:
        raise SystemExit("Fin map.js introuvable")
    text = text.replace(tail_old, tail_new, 1)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    patch_app_js()
    patch_map_js()
    print("OK")
