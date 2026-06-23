"""Persistance des paramètres MQTT, Meshtastic et interface."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

SETTINGS_PATH = Path(__file__).resolve().parent.parent / "data" / "settings.json"
CHANNEL_COUNT = 8


CHANNEL_ROLES = frozenset({"PRINCIPAL", "SECONDAIRE", "DESACTIVE"})

BUNDLED_CHANNELS: list[dict[str, Any]] = [
    {
        "name": "Fr_Balise",
        "key": "AQ==",
        "enabled": True,
        "role": "PRINCIPAL",
    },
    {
        "name": "Fr_EMCOM",
        "key": "AQ==",
        "enabled": True,
        "role": "SECONDAIRE",
    },
    {
        "name": "Fr_BlaBla",
        "key": "AQ==",
        "enabled": True,
        "role": "SECONDAIRE",
    },
    {
        "name": "D_Ligerien",
        "key": "AQ==",
        "enabled": True,
        "role": "SECONDAIRE",
    },
    {
        "name": "interco",
        "key": "L5gSgxLSvkOfmejKZwIPWCtMzhb+upi8fXyFOvRXm2Q=",
        "enabled": True,
        "role": "SECONDAIRE",
    },
    {
        "name": "AASC",
        "key": "HlXAVy6LrbQ0idduXZj2a8p79wifB8ZIBZNT3UrqbB4=",
        "enabled": True,
        "role": "SECONDAIRE",
    },
    {
        "name": "SAP",
        "key": "QIiUp++FeMAxPd0u+d5VfKSTJA70C9fGem2Jtn4SDJs=",
        "enabled": True,
        "role": "SECONDAIRE",
    },
    {
        "name": "logistique",
        "key": "zx8k0MF/HFrPDSFJTKOe4PjnUl4+dDpIAh8LPtaZ3YU=",
        "enabled": True,
        "role": "SECONDAIRE",
    },
]


def default_channel_slot(index: int) -> dict[str, Any]:
    if 0 <= index < len(BUNDLED_CHANNELS):
        return deepcopy(BUNDLED_CHANNELS[index])
    return {"name": "", "key": "", "enabled": False, "role": "DESACTIVE"}


def normalize_channel_slot(ch: dict[str, Any], index: int) -> dict[str, Any]:
    role = ch.get("role")
    if role not in CHANNEL_ROLES:
        if not ch.get("enabled", False) or not str(ch.get("name", "")).strip():
            role = "DESACTIVE"
        elif index == 0:
            role = "PRINCIPAL"
        else:
            role = "SECONDAIRE"
    enabled = role != "DESACTIVE"
    return {
        "name": str(ch.get("name", "")),
        "key": str(ch.get("key", "")),
        "enabled": enabled,
        "role": role,
    }


def default_channels() -> list[dict[str, Any]]:
    return [default_channel_slot(i) for i in range(CHANNEL_COUNT)]


DEFAULTS: dict[str, Any] = {
    "mqtt": {
        "broker": "192.168.1.66",
        "port": 1883,
        "username": "",
        "password": "",
        "root_topic": "msh/EU_868",
    },
    "meshtastic": {
        "channels": default_channels(),
        "active_channel": 0,
        "short_name": "MQTT",
        "long_name": "MeshQTT Web",
        "node_id": None,
    },
    "ui": {
        "theme": "dark",
        # "inforoute_enabled": True,  # Info Routes 42 — desactive pour le moment
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def normalize_meshtastic(mesh: dict[str, Any]) -> dict[str, Any]:
    """Assure 8 canaux (0–7) et migre l'ancien format channel/key."""
    mesh = deepcopy(mesh)
    channels = mesh.get("channels")

    if not isinstance(channels, list) or len(channels) != CHANNEL_COUNT:
        slots = default_channels()
        if isinstance(channels, list):
            for i, ch in enumerate(channels[:CHANNEL_COUNT]):
                if isinstance(ch, dict):
                    slots[i] = {**slots[i], **ch}
        if mesh.get("channel"):
            slots[0] = {
                "name": mesh["channel"],
                "key": mesh.get("key", "AQ=="),
                "enabled": True,
            }
        mesh["channels"] = slots

    mesh["channels"] = [
        normalize_channel_slot(ch, i)
        for i, ch in enumerate(mesh["channels"][:CHANNEL_COUNT])
    ]
    while len(mesh["channels"]) < CHANNEL_COUNT:
        mesh["channels"].append(default_channel_slot(len(mesh["channels"])))

    active = mesh.get("active_channel", 0)
    mesh["active_channel"] = max(0, min(CHANNEL_COUNT - 1, int(active)))
    mesh.pop("channel", None)
    mesh.pop("key", None)
    return mesh


def normalize_ui(ui: dict[str, Any]) -> dict[str, Any]:
    ui = deepcopy(ui)
    theme = ui.get("theme", "dark")
    ui["theme"] = theme if theme in ("light", "dark") else "dark"
    # Info Routes 42 — desactive pour le moment
    # ui["inforoute_enabled"] = bool(ui.get("inforoute_enabled", True))
    return ui


def normalize_root_topic(raw: str) -> str:
    """Topic racine MQTT — réseau Gaulix : msh/EU_868 (crossband, sans /2/e/)."""
    root = str(raw or DEFAULTS["mqtt"]["root_topic"]).strip()
    # Ancien format Meshtastic public (msh/EU_868/2/e/ ou msh/EU/433/2/e/) → Gaulix
    if "/2/e" in root:
        root = root.split("/2/e")[0]
    if root.startswith("msh/EU/433"):
        root = "msh/EU_868"
    root = root.rstrip("/")
    return f"{root}/" if root else "msh/EU_868/"


def normalize_mqtt(mqtt: dict[str, Any]) -> dict[str, Any]:
    """Normalise la config MQTT ; migre l'ancien broker public Meshtastic."""
    mqtt = deepcopy(mqtt)
    if mqtt.get("broker") in ("mqtt.meshtastic.org", "mqtt.meshtastic.com"):
        mqtt["broker"] = DEFAULTS["mqtt"]["broker"]
        mqtt["username"] = ""
        mqtt["password"] = ""
    mqtt["root_topic"] = normalize_root_topic(mqtt.get("root_topic", ""))
    return mqtt


def normalize_settings(data: dict[str, Any]) -> dict[str, Any]:
    result = _deep_merge(DEFAULTS, data)
    result["mqtt"] = normalize_mqtt({**DEFAULTS["mqtt"], **result.get("mqtt", {})})
    result["meshtastic"] = normalize_meshtastic(result["meshtastic"])
    result["ui"] = normalize_ui(result.get("ui", {}))
    return result


def load_settings() -> dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return json.loads(json.dumps(DEFAULTS))
    try:
        stored = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        return normalize_settings(stored)
    except (json.JSONDecodeError, OSError, ValueError, TypeError):
        return json.loads(json.dumps(DEFAULTS))


def save_settings(data: dict[str, Any]) -> dict[str, Any]:
    merged = normalize_settings(data)
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return merged


def settings_to_mqtt_config(settings: dict[str, Any]):
    from app.mqtt_client import MqttConfig, channel_slot_to_config

    mqtt = settings["mqtt"]
    mesh = normalize_meshtastic(settings["meshtastic"])
    channels = [channel_slot_to_config(ch) for ch in mesh["channels"]]
    return MqttConfig(
        broker=mqtt["broker"],
        port=int(mqtt["port"]),
        username=mqtt.get("username", ""),
        password=mqtt.get("password", ""),
        root_topic=mqtt["root_topic"],
        channels=channels,
        active_channel=mesh.get("active_channel", 0),
        short_name=mesh.get("short_name", "MQTT")[:4],
        long_name=mesh.get("long_name", "MeshQTT Web"),
        node_id=mesh.get("node_id"),
    )
