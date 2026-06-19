"""Client MQTT nodeless pour Meshtastic."""

from __future__ import annotations

import asyncio
import math
import random
import secrets
import ssl
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import paho.mqtt.client as mqtt

try:
    from meshtastic import BROADCAST_NUM
    from meshtastic.protobuf import mesh_pb2, mqtt_pb2, portnums_pb2
except ImportError:
    from meshtastic import BROADCAST_NUM, mesh_pb2, mqtt_pb2, portnums_pb2

from app.constants import MESH_TEXT_MESSAGE_MAX_BYTES, mesh_message_byte_length
from app.mesh_crypto import encrypt_payload, try_decode_encrypted_packet
from app.settings import CHANNEL_COUNT, default_channel_slot


@dataclass
class ChannelConfig:
    name: str = ""
    key: str = ""
    enabled: bool = False
    role: str = "DESACTIVE"

    def is_active(self) -> bool:
        if self.role != "DESACTIVE":
            return bool(self.name.strip())
        return self.enabled and bool(self.name.strip())


def channel_slot_to_config(slot: dict[str, Any]) -> ChannelConfig:
    return ChannelConfig(
        name=slot.get("name", ""),
        key=slot.get("key", ""),
        enabled=bool(slot.get("enabled", False)),
        role=slot.get("role", "DESACTIVE"),
    )


@dataclass
class MqttConfig:
    broker: str = "127.0.0.1"
    port: int = 1883
    username: str = ""
    password: str = ""
    root_topic: str = "msh/EU_868/2/e/"
    channels: list[ChannelConfig] = field(default_factory=lambda: [
        channel_slot_to_config(default_channel_slot(i)) for i in range(CHANNEL_COUNT)
    ])
    active_channel: int = 0
    short_name: str = "MQTT"
    long_name: str = "MeshQTT Web"
    node_id: int | None = None

    def __post_init__(self) -> None:
        while len(self.channels) < CHANNEL_COUNT:
            self.channels.append(
                channel_slot_to_config(default_channel_slot(len(self.channels)))
            )
        self.channels = self.channels[:CHANNEL_COUNT]
        self.active_channel = max(0, min(CHANNEL_COUNT - 1, self.active_channel))

    def enabled_channels(self) -> list[tuple[int, ChannelConfig]]:
        return [
            (i, ch)
            for i, ch in enumerate(self.channels)
            if ch.is_active()
        ]

    def channel_at(self, index: int) -> ChannelConfig | None:
        if 0 <= index < CHANNEL_COUNT:
            ch = self.channels[index]
            if ch.name.strip():
                return ch
        return None

    def resolve_send_channel(self, index: int | None = None) -> tuple[int, ChannelConfig]:
        if index is not None and (ch := self.channel_at(index)):
            return index, ch
        if ch := self.channel_at(self.active_channel):
            return self.active_channel, ch
        for i, ch in self.enabled_channels():
            return i, ch
        raise ValueError("Aucun canal Meshtastic actif configuré")


@dataclass
class NodeInfo:
    user_id: str
    short_name: str
    long_name: str


@dataclass
class ChatMessage:
    timestamp: float
    from_id: int
    to_id: int
    text: str
    message_id: int
    encrypted: bool
    channel_index: int | None = None
    channel_name: str = ""
    from_short: str = "?"
    to_short: str = "?"


class MeshtasticMqttClient:
    """Pont MQTT Meshtastic avec callbacks thread-safe vers asyncio."""

    def __init__(self, on_event: Callable[[dict[str, Any]], None]) -> None:
        self._on_event = on_event
        self._config = MqttConfig()
        self._client: mqtt.Client | None = None
        self._loop_thread: threading.Thread | None = None
        self._connected = False
        self._global_message_id = random.randint(100000, 999999)
        self._nodes: dict[int, NodeInfo] = {}
        self._seen_ids: set[int] = set()
        self._lock = threading.Lock()
        self._channel_name_to_index: dict[str, int] = {}

    @property
    def config(self) -> MqttConfig:
        return self._config

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def node_number(self) -> int:
        if self._config.node_id is None:
            self._config.node_id = random.randint(0x10000000, 0xFFFFFFFE)
        return self._config.node_id

    @property
    def node_name(self) -> str:
        return "!" + hex(self.node_number)[2:]

    def _emit(self, event: dict[str, Any]) -> None:
        self._on_event(event)

    def _rebuild_channel_map(self) -> None:
        self._channel_name_to_index = {
            ch.name: i for i, ch in enumerate(self._config.channels) if ch.name.strip()
        }

    def connect(self, config: MqttConfig) -> None:
        self.disconnect()
        self._config = config
        self._rebuild_channel_map()
        if self._config.node_id is None:
            self._config.node_id = random.randint(0x10000000, 0xFFFFFFFE)

        enabled = self._config.enabled_channels()
        if not enabled:
            self._emit({"type": "error", "message": "Aucun canal activé — configurez au moins un canal (0–7)"})
            return

        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="",
            clean_session=True,
        )
        self._client.username_pw_set(self._config.username, self._config.password)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        if self._config.port == 8883:
            self._client.tls_set(cert_reqs=ssl.CERT_REQUIRED)

        try:
            self._client.connect(self._config.broker, self._config.port, 60)
        except Exception as exc:
            hint = ""
            if self._config.broker in ("127.0.0.1", "localhost", "::1") and self._config.port == 1883:
                hint = (
                    " — vérifiez qu'un seul Mosquitto écoute sur le port 1883 "
                    "(docker compose up -d dans MeshQTT → conteneur meshqtt-mosquitto)"
                )
            self._emit({"type": "error", "message": f"Connexion MQTT impossible : {exc}{hint}"})
            return

        self._loop_thread = threading.Thread(target=self._client.loop_forever, daemon=True)
        self._loop_thread.start()

    def disconnect(self) -> None:
        self._connected = False
        if self._client:
            try:
                self._client.disconnect()
                self._client.loop_stop()
            except Exception:
                pass
            self._client = None

    def send_text(
        self,
        text: str,
        destination_id: int | None = None,
        channel_index: int | None = None,
    ) -> None:
        if not self._client or not self._connected:
            self._emit({"type": "error", "message": "Non connecté au broker MQTT"})
            return

        nbytes = mesh_message_byte_length(text)
        if nbytes > MESH_TEXT_MESSAGE_MAX_BYTES:
            self._emit(
                {
                    "type": "error",
                    "message": (
                        f"Message trop long ({nbytes}/{MESH_TEXT_MESSAGE_MAX_BYTES} "
                        "octets UTF-8)"
                    ),
                }
            )
            return

        try:
            idx, _channel = self._config.resolve_send_channel(channel_index)
        except ValueError as exc:
            self._emit({"type": "error", "message": str(exc)})
            return

        to_id = destination_id if destination_id is not None else BROADCAST_NUM
        encoded = mesh_pb2.Data()
        encoded.portnum = portnums_pb2.TEXT_MESSAGE_APP
        encoded.payload = text.encode("utf-8")
        encoded.bitfield = 1
        self._publish_packet(to_id, encoded, channel_index=idx)

    def _generate_waypoint_id(self) -> int:
        seed = secrets.randbits(32)
        return int(math.floor(seed * math.pow(2, -32) * 1e9))

    def send_waypoint(
        self,
        latitude: float,
        longitude: float,
        name: str,
        description: str = "",
        *,
        channel_index: int | None = None,
        destination_id: int | None = None,
        expire: int | None = None,
        icon: int = 128205,
        waypoint_id: int | None = None,
    ) -> None:
        if not self._client or not self._connected:
            self._emit({"type": "error", "message": "Non connecté au broker MQTT"})
            return

        if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
            self._emit({"type": "error", "message": "Coordonnées waypoint invalides"})
            return

        try:
            idx, _channel = self._config.resolve_send_channel(channel_index)
        except ValueError as exc:
            self._emit({"type": "error", "message": str(exc)})
            return

        waypoint = mesh_pb2.Waypoint()
        waypoint.id = waypoint_id if waypoint_id is not None else self._generate_waypoint_id()
        waypoint.latitude_i = int(latitude * 1e7)
        waypoint.longitude_i = int(longitude * 1e7)
        waypoint.expire = expire if expire is not None else int(time.time()) + 86400
        waypoint.name = name[:30]
        waypoint.description = description[:100]
        waypoint.icon = icon
        waypoint.locked_to = 0

        to_id = destination_id if destination_id is not None else BROADCAST_NUM
        encoded = mesh_pb2.Data()
        encoded.portnum = portnums_pb2.WAYPOINT_APP
        encoded.payload = waypoint.SerializeToString()
        encoded.bitfield = 1
        self._publish_packet(to_id, encoded, channel_index=idx)

    def _publish_topic(self, channel_name: str) -> str:
        return f"{self._config.root_topic}{channel_name}/{self.node_name}"

    def _subscribe_topics(self) -> list[str]:
        return [
            f"{self._config.root_topic}{ch.name}/#"
            for _, ch in self._config.enabled_channels()
        ]

    def _keys_for_channel_id(self, channel_id: str) -> list[str]:
        keys: list[str] = []
        idx = self._channel_name_to_index.get(channel_id)
        if idx is not None:
            key = self._config.channels[idx].key
            if key:
                keys.append(key)
        for _, ch in self._config.enabled_channels():
            if ch.name != channel_id and ch.key:
                keys.append(ch.key)
        return keys

    def _publish_packet(
        self,
        destination_id: int,
        encoded_message,
        channel_index: int | None = None,
    ) -> None:
        assert self._client is not None
        idx, channel = self._config.resolve_send_channel(channel_index)

        mesh_packet = mesh_pb2.MeshPacket()
        mesh_packet.id = self._global_message_id
        self._global_message_id += 1
        setattr(mesh_packet, "from", self.node_number)
        mesh_packet.to = destination_id
        mesh_packet.want_ack = False
        mesh_packet.hop_limit = 3
        mesh_packet.hop_start = 3

        if not channel.key:
            mesh_packet.decoded.CopyFrom(encoded_message)
        else:
            channel_hash, encrypted = encrypt_payload(
                channel.name,
                channel.key,
                mesh_packet.id,
                self.node_number,
                encoded_message,
            )
            mesh_packet.channel = channel_hash
            mesh_packet.encrypted = encrypted

        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.packet.CopyFrom(mesh_packet)
        envelope.channel_id = channel.name
        envelope.gateway_id = self.node_name
        self._client.publish(self._publish_topic(channel.name), envelope.SerializeToString())

    def _on_connect(self, client, userdata, connect_flags, reason_code, properties) -> None:
        if reason_code != 0:
            self._emit(
                {
                    "type": "status",
                    "connected": False,
                    "message": f"Échec connexion MQTT (code {reason_code})",
                }
            )
            return

        self._connected = True
        topics = self._subscribe_topics()
        for topic in topics:
            client.subscribe(topic)

        labels = [f"{i}:{ch.name}" for i, ch in self._config.enabled_channels()]
        self._emit(
            {
                "type": "status",
                "connected": True,
                "message": (
                    f"Connecté à {self._config.broker} — "
                    f"{self._config.root_topic} — "
                    f"canaux {', '.join(labels)} — {self.node_name}"
                ),
                "root_topic": self._config.root_topic,
                "node_id": self.node_number,
                "node_name": self.node_name,
                "channels": [
                    {
                        "index": i,
                        "name": ch.name,
                        "enabled": ch.is_active(),
                        "role": ch.role,
                    }
                    for i, ch in enumerate(self._config.channels)
                    if ch.is_active()
                ],
            }
        )
        self._send_node_info(BROADCAST_NUM)

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties) -> None:
        self._connected = False
        self._emit(
            {
                "type": "status",
                "connected": False,
                "message": f"Déconnecté du broker (code {reason_code})",
            }
        )

    def _send_node_info(self, destination_id: int) -> None:
        user = mesh_pb2.User()
        user.id = self.node_name
        user.long_name = self._config.long_name
        user.short_name = self._config.short_name
        user.hw_model = mesh_pb2.HardwareModel.PRIVATE_HW

        encoded = mesh_pb2.Data()
        encoded.portnum = portnums_pb2.NODEINFO_APP
        encoded.payload = user.SerializeToString()
        encoded.bitfield = 1
        self._publish_packet(destination_id, encoded)

    def _name(self, node_id: int, kind: str = "short") -> str:
        info = self._nodes.get(node_id)
        if not info:
            return f"!{node_id:08x}"
        return info.short_name if kind == "short" else info.long_name

    def _on_message(self, client, userdata, msg) -> None:
        try:
            envelope = mqtt_pb2.ServiceEnvelope()
            envelope.ParseFromString(msg.payload)
            mp = envelope.packet
            channel_id = envelope.channel_id or ""
        except Exception:
            return

        channel_index = self._channel_name_to_index.get(channel_id)
        encrypted = False

        if mp.HasField("encrypted") and not mp.HasField("decoded"):
            encrypted = True
            keys = self._keys_for_channel_id(channel_id)
            if not try_decode_encrypted_packet(mp, keys):
                self._emit(
                    {
                        "type": "error",
                        "message": f"Déchiffrement échoué (canal {channel_id or '?'})",
                    }
                )
                return

        if not mp.HasField("decoded"):
            return

        port = mp.decoded.portnum

        if port == portnums_pb2.NODEINFO_APP:
            info = mesh_pb2.User()
            info.ParseFromString(mp.decoded.payload)
            from_id = getattr(mp, "from")
            self._nodes[from_id] = NodeInfo(
                user_id=info.id,
                short_name=info.short_name or "?",
                long_name=info.long_name or info.id,
            )
            self._emit(
                {
                    "type": "node",
                    "from_id": from_id,
                    "user_id": info.id,
                    "short_name": info.short_name,
                    "long_name": info.long_name,
                }
            )
            return

        if port == portnums_pb2.TEXT_MESSAGE_APP:
            from_id = getattr(mp, "from")
            to_id = mp.to
            msg_id = mp.id

            with self._lock:
                if msg_id in self._seen_ids:
                    return
                self._seen_ids.add(msg_id)

            try:
                text = mp.decoded.payload.decode("utf-8")
            except UnicodeDecodeError:
                text = mp.decoded.payload.hex()

            ch_name = channel_id
            if channel_index is None and ch_name:
                channel_index = self._channel_name_to_index.get(ch_name)

            chat = ChatMessage(
                timestamp=time.time(),
                from_id=from_id,
                to_id=to_id,
                text=text,
                message_id=msg_id,
                encrypted=encrypted,
                channel_index=channel_index,
                channel_name=ch_name,
                from_short=self._name(from_id),
                to_short=self._name(to_id) if to_id != BROADCAST_NUM else "broadcast",
            )
            self._emit({"type": "message", **chat.__dict__})

            if to_id == self.node_number and mp.want_ack:
                self._send_ack(from_id, msg_id)

    def _send_ack(self, destination_id: int, message_id: int) -> None:
        encoded = mesh_pb2.Data()
        encoded.portnum = portnums_pb2.ROUTING_APP
        encoded.request_id = message_id
        encoded.payload = b"\030\000"
        self._publish_packet(destination_id, encoded)

    def get_nodes(self) -> list[dict[str, Any]]:
        return [
            {
                "node_id": nid,
                "user_id": n.user_id,
                "short_name": n.short_name,
                "long_name": n.long_name,
            }
            for nid, n in sorted(self._nodes.items())
        ]


class AsyncMeshtasticBridge:
    """Expose le client MQTT à FastAPI via une queue asyncio."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue[dict[str, Any]] | None = None
        self.client = MeshtasticMqttClient(self._thread_callback)

    def bind_loop(self, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue) -> None:
        self._loop = loop
        self._queue = queue

    def _thread_callback(self, event: dict[str, Any]) -> None:
        if self._loop and self._queue:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, event)
