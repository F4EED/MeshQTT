"""Serveur web MeshQTT — interface navigateur pour Meshtastic MQTT."""

from __future__ import annotations

import asyncio
import json
import socket
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from app.constants import validate_mesh_text_message
# Info Routes 42 — desactive pour le moment
# from app.inforoute42 import fetch_inforoute42_bulletin
from app.events import WsEventHub
from app.mqtt_client import AsyncMeshtasticBridge
from app.presets import load_bundled_presets, save_bundled_presets
from app.settings import CHANNEL_COUNT, load_settings, normalize_meshtastic, save_settings, settings_to_mqtt_config

STATIC_DIR = Path(__file__).resolve().parent / "static"
event_hub = WsEventHub()
bridge = AsyncMeshtasticBridge()


class MqttSettings(BaseModel):
    broker: str = "192.168.1.66"
    port: int = 1883
    username: str = ""
    password: str = ""
    root_topic: str = "msh/EU_868"


class ChannelSlot(BaseModel):
    name: str = ""
    key: str = ""
    enabled: bool = False
    role: Literal["PRINCIPAL", "SECONDAIRE", "DESACTIVE"] = "DESACTIVE"


class MeshtasticSettings(BaseModel):
    channels: list[ChannelSlot] = Field(default_factory=list)
    active_channel: int = Field(default=0, ge=0, le=CHANNEL_COUNT - 1)
    short_name: str = Field(default="MQTT", max_length=4)
    long_name: str = "MeshQTT Web"
    node_id: int | None = None

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, channels: list[ChannelSlot]) -> list[ChannelSlot]:
        if len(channels) != CHANNEL_COUNT:
            raise ValueError(f"Exactement {CHANNEL_COUNT} canaux requis (indices 0–7)")
        return channels


class UiSettings(BaseModel):
    theme: str = Field(default="dark", pattern="^(light|dark)$")
    # inforoute_enabled: bool = True  # Info Routes 42 — desactive pour le moment


class SettingsUpdate(BaseModel):
    mqtt: MqttSettings | None = None
    meshtastic: MeshtasticSettings | None = None
    ui: UiSettings | None = None


class PresetCategory(BaseModel):
    id: str = Field(min_length=1, max_length=60)
    label: str = Field(min_length=1, max_length=60)


class PresetMessage(BaseModel):
    text: str = Field(min_length=1)
    channel: int = Field(default=0, ge=0, le=CHANNEL_COUNT - 1)
    visu: str = ""
    option: bool = False


class PresetsBundle(BaseModel):
    categories: list[PresetCategory] = Field(default_factory=list)
    presets: dict[str, list[PresetMessage]] = Field(default_factory=dict)


class SendRequest(BaseModel):
    text: str = Field(min_length=1)
    to: int | None = None
    channel: int | None = Field(default=None, ge=0, le=CHANNEL_COUNT - 1)

    @field_validator("text")
    @classmethod
    def validate_text_bytes(cls, value: str) -> str:
        return validate_mesh_text_message(value)


class WaypointRequest(BaseModel):
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    name: str = Field(min_length=1, max_length=30)
    description: str = Field(default="", max_length=100)
    channel: int | None = Field(default=None, ge=0, le=CHANNEL_COUNT - 1)
    to: int | None = None
    expire: int | None = Field(default=None, ge=0)
    icon: int = Field(default=128205, ge=0)
    waypoint_id: int | None = Field(default=None, ge=0)


class ConnectRequest(BaseModel):
    """Config optionnelle envoyée par le navigateur (mode hors-ligne)."""
    mqtt: MqttSettings | None = None
    meshtastic: MeshtasticSettings | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    bridge.bind_loop(loop, event_hub.publish)
    app.state.event_hub = event_hub

    settings = load_settings()
    config = settings_to_mqtt_config(settings)
    if config.enabled_channels():
        await asyncio.to_thread(bridge.client.connect, config)

    yield

    bridge.client.disconnect()


app = FastAPI(title="MeshQTT", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/map")
async def map_page():
    """Carte Leaflet (fond OSM). Couche Info Routes 42 desactivee pour le moment."""
    return FileResponse(STATIC_DIR / "map.html")


@app.get("/api/settings")
async def api_get_settings():
    return load_settings()


@app.put("/api/settings")
async def api_put_settings(body: SettingsUpdate):
    current = load_settings()
    patch: dict[str, Any] = {}
    if body.mqtt is not None:
        patch["mqtt"] = body.mqtt.model_dump()
    if body.meshtastic is not None:
        patch["meshtastic"] = body.meshtastic.model_dump()
    if body.ui is not None:
        patch["ui"] = body.ui.model_dump()
    return save_settings(_merge_patch(current, patch))


@app.get("/api/presets-default")
async def api_get_presets_default():
    """Messages prédéfinis embarqués (data/presets.json)."""
    return load_bundled_presets()


@app.put("/api/presets-default")
async def api_put_presets_default(body: PresetsBundle):
    """Intègre les prédéfinis saisis dans l'application (fichier serveur)."""
    payload = {
        "categories": [c.model_dump() for c in body.categories],
        "presets": {
            key: [m.model_dump() for m in messages]
            for key, messages in body.presets.items()
        },
    }
    return save_bundled_presets(payload)


def _merge_patch(current: dict, patch: dict) -> dict:
    result = current.copy()
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = {**result[key], **value}
        else:
            result[key] = value
    return result


@app.get("/api/status")
async def api_status():
    cfg = bridge.client.config
    settings = load_settings()
    mesh = normalize_meshtastic(settings["meshtastic"])
    enabled = [
        {"index": i, "name": ch["name"]}
        for i, ch in enumerate(mesh["channels"])
        if ch.get("enabled") and ch.get("name")
    ]
    return {
        "connected": bridge.client.connected,
        "broker": cfg.broker,
        "root_topic": cfg.root_topic,
        "active_channel": mesh.get("active_channel", 0),
        "channels": enabled,
        "node_id": bridge.client.node_number if cfg.node_id else None,
        "node_name": bridge.client.node_name if cfg.node_id else None,
        "short_name": mesh.get("short_name"),
        "long_name": mesh.get("long_name"),
        **bridge.client.get_rx_stats(),
    }


@app.get("/api/mqtt/health")
async def api_mqtt_health():
    """Vérifie que le broker configuré accepte une connexion TCP."""
    settings = load_settings()
    mqtt = settings["mqtt"]
    broker = str(mqtt.get("broker", "127.0.0.1"))
    port = int(mqtt.get("port", 1883))

    def _probe() -> dict[str, Any]:
        hint = None
        if broker.lower() == "localhost":
            try:
                resolved = socket.getaddrinfo(broker, port, type=socket.SOCK_STREAM)
                if resolved and resolved[0][4][0] == "::1":
                    hint = (
                        "Sur Windows, « localhost » peut résoudre en ::1 (autre Mosquitto que Docker). "
                        "Utilisez 127.0.0.1 ou l'IP LAN du PC (ex. 192.168.x.x)."
                    )
            except OSError:
                pass
        try:
            with socket.create_connection((broker, port), timeout=3):
                pass
            return {
                "ok": True,
                "broker": broker,
                "port": port,
                "reachable": True,
                "hint": hint,
            }
        except OSError as exc:
            if hint is None and broker in ("127.0.0.1", "localhost", "::1") and port == 1883:
                hint = (
                    "Un seul Mosquitto doit écouter sur 1883. "
                    "Dans MeshQTT : docker compose up -d (conteneur meshqtt-mosquitto)."
                )
            return {
                "ok": False,
                "broker": broker,
                "port": port,
                "reachable": False,
                "error": str(exc),
                "hint": hint,
            }

    return await asyncio.to_thread(_probe)


@app.get("/api/nodes")
async def api_nodes():
    return {"nodes": bridge.client.get_nodes()}


@app.get("/api/positions")
async def api_positions():
    """Dernière position connue par nœud (mémoire serveur, depuis MQTT)."""
    return {"positions": bridge.client.get_positions()}


def _apply_client_settings(body: ConnectRequest | None) -> dict[str, Any]:
    current = load_settings()
    if body is None or (body.mqtt is None and body.meshtastic is None):
        return current
    patch: dict[str, Any] = {}
    if body.mqtt is not None:
        patch["mqtt"] = body.mqtt.model_dump()
    if body.meshtastic is not None:
        patch["meshtastic"] = body.meshtastic.model_dump()
    return save_settings(_merge_patch(current, patch))


@app.post("/api/connect")
async def api_connect(body: ConnectRequest | None = None):
    settings = _apply_client_settings(body)
    config = settings_to_mqtt_config(settings)
    bridge.client.connect(config)
    mesh = normalize_meshtastic(settings["meshtastic"])
    if bridge.client.config.node_id is not None:
        mesh["node_id"] = bridge.client.config.node_id
        save_settings({**settings, "meshtastic": mesh})
    return {"ok": True, "node_name": bridge.client.node_name}


@app.post("/api/disconnect")
async def api_disconnect():
    bridge.client.disconnect()
    return {"ok": True}


@app.post("/api/send")
async def api_send(body: SendRequest):
    bridge.client.send_text(body.text, body.to, body.channel)
    return {"ok": True}


@app.post("/api/waypoint")
async def api_waypoint(body: WaypointRequest):
    bridge.client.send_waypoint(
        body.latitude,
        body.longitude,
        body.name,
        body.description,
        channel_index=body.channel,
        destination_id=body.to,
        expire=body.expire,
        icon=body.icon,
        waypoint_id=body.waypoint_id,
    )
    return {"ok": True}


# Info Routes 42 — desactive pour le moment
# @app.get("/api/inforoute42")
# async def api_inforoute42():
#     """Proxy vers inforoute42.fr — seul appel externe Internet du serveur."""
#     try:
#         return await asyncio.to_thread(fetch_inforoute42_bulletin)
#     except ConnectionError as exc:
#         raise HTTPException(status_code=502, detail=str(exc)) from exc
#     except ValueError as exc:
#         raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    queue = event_hub.subscribe()

    async def forward_events() -> None:
        while True:
            event = await queue.get()
            await ws.send_text(json.dumps(event, default=str))

    task = asyncio.create_task(forward_events())
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        task.cancel()
        event_hub.unsubscribe(queue)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=True)
