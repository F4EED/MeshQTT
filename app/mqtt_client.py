"""Client MQTT nodeless pour Meshtastic."""

from __future__ import annotations

import asyncio
import json
import logging
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

logger = logging.getLogger(__name__)

try:
    import unishox2
except ImportError:
    unishox2 = None  # type: ignore[assignment]
from app.mesh_crypto import DEFAULT_KEY, encrypt_payload, try_decode_encrypted_packet
from app.settings import CHANNEL_COUNT, default_channel_slot

# Segments topic firmware Meshtastic (MQTT.h : root + "/2/e/" + …)
MESHTASTIC_FW_CRYPT = "/2/e/"
MESHTASTIC_FW_JSON = "/2/json/"
MESHTASTIC_FW_LEGACY = "/2/c/"
MESHTASTIC_TOPIC_PREFIXES = ("2/json/", "2/e/", "2/c/")


def mqtt_root_raw(root: str) -> str:
    """Root topic tel que configuré (slash final conservé — comme moduleConfig.mqtt.root)."""
    base = str(root or "msh/EU_868").strip()
    return base if base else "msh/EU_868"


def mqtt_root_normalized(root: str) -> str:
    """Root topic avec slash final (ex. msh/EU_868/) — affichage / compat."""
    base = mqtt_root_raw(root).rstrip("/")
    return f"{base}/" if base else "msh/EU_868/"


def mqtt_topic_prefix(root: str, *, json: bool = False, legacy: bool = False) -> str:
    """Préfixe identique au firmware : root + '/2/e/' (double slash si root se termine par /)."""
    segment = MESHTASTIC_FW_JSON if json else MESHTASTIC_FW_LEGACY if legacy else MESHTASTIC_FW_CRYPT
    return mqtt_root_raw(root) + segment


def mqtt_subscribe_topics(root: str) -> list[str]:
    """Wildcards d'abonnement — format firmware (+ variante sans double slash)."""
    raw = mqtt_root_raw(root)
    base = raw.rstrip("/")
    topics: list[str] = []
    for segment in (MESHTASTIC_FW_CRYPT, MESHTASTIC_FW_JSON, MESHTASTIC_FW_LEGACY):
        topics.append(f"{raw}{segment}#")
        if base and raw != base:
            topics.append(f"{base}{segment}#")
    return list(dict.fromkeys(topics))


def parse_channel_from_meshtastic_topic(topic: str, root: str) -> str:
    """Extrait le nom de canal depuis un topic Meshtastic (…/2/json/Canal/!node)."""
    raw = mqtt_root_raw(root)
    if topic.startswith(raw):
        rest = topic[len(raw) :]
    elif topic.startswith(mqtt_root_normalized(root)):
        rest = topic[len(mqtt_root_normalized(root)) :]
    else:
        return ""
    rest = rest.lstrip("/")
    for segment in MESHTASTIC_TOPIC_PREFIXES:
        if rest.startswith(segment):
            rest = rest[len(segment) :]
            break
    return rest.split("/")[0] if rest else ""


def is_meshtastic_json_topic(topic: str, root: str) -> bool:
    base = mqtt_root_raw(root).rstrip("/")
    return topic.startswith(base) and "/2/json/" in topic


def packet_has_decoded(mp) -> bool:
    """Proto3 : ne pas se fier uniquement à HasField(decoded)."""
    decoded = mp.decoded
    return bool(decoded.portnum) or bool(decoded.payload)


def packet_needs_decrypt(mp) -> bool:
    return bool(mp.encrypted) and not packet_has_decoded(mp)


def mesh_packet_has_content(mp) -> bool:
    """Vrai si le MeshPacket contient des données exploitables."""
    if getattr(mp, "from", 0):
        return True
    if mp.id:
        return True
    if mp.encrypted:
        return True
    return packet_has_decoded(mp)


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
    broker: str = "192.168.1.66"
    port: int = 1883
    username: str = ""
    password: str = ""
    root_topic: str = "msh/EU_868"
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

    def named_channels(self) -> list[tuple[int, ChannelConfig]]:
        """Canaux avec un nom (0–7), y compris rôle DESACTIVE — pour réception / clés PSK."""
        return [
            (i, ch)
            for i, ch in enumerate(self.channels)
            if ch.name.strip()
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
        self._mqtt_rx_count = 0
        self._last_mqtt_topic = ""
        self._last_mqtt_rx_at: float | None = None

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

    def _mqtt_root(self) -> str:
        return mqtt_root_normalized(self._config.root_topic)

    def _publish_topic(self, channel_name: str) -> str:
        # Comme le firmware : moduleConfig.mqtt.root + "/2/e/" + canal + "/" + node
        return f"{mqtt_topic_prefix(self._config.root_topic)}{channel_name}/{self.node_name}"

    def _subscribe_topics(self) -> list[str]:
        """Abonnements MQTT — réception de tous les canaux (wildcard Meshtastic)."""
        topics = mqtt_subscribe_topics(self._config.root_topic)
        root = mqtt_root_normalized(self._config.root_topic)
        for _, ch in self._config.named_channels():
            topics.append(f"{root}{ch.name}/#")
        return list(dict.fromkeys(topics))

    def _keys_for_channel_id(self, channel_id: str) -> list[str]:
        keys: list[str] = []
        seen: set[str] = set()

        def add(key: str) -> None:
            k = str(key or "").strip()
            if k and k not in seen:
                seen.add(k)
                keys.append(k)

        idx = self._channel_name_to_index.get(channel_id)
        if idx is not None:
            add(self._config.channels[idx].key)
        for _, ch in self._config.named_channels():
            add(ch.key)
        if not keys:
            add(DEFAULT_KEY)
            add("AQ==")
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

        if not channel.key or channel.key.strip() in ("", "AQ=="):
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
                    f"réception tous canaux (2/e/, 2/json/) — "
                    f"envoi : {', '.join(labels) or 'aucun'} — {self.node_name}"
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
        topic = msg.topic or ""
        with self._lock:
            self._mqtt_rx_count += 1
            self._last_mqtt_topic = topic
            self._last_mqtt_rx_at = time.time()
        logger.debug("MQTT %s (%d octets)", topic, len(msg.payload or b""))
        if is_meshtastic_json_topic(topic, self._config.root_topic):
            self._on_message_json(topic, msg.payload)
            return
        self._on_message_protobuf(topic, msg.payload)

    def _on_message_json(self, topic: str, payload: bytes) -> None:
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if not isinstance(data, dict):
            return

        msg_type = str(data.get("type") or "").lower()
        try:
            msg_id = int(data.get("id") or 0)
        except (TypeError, ValueError):
            msg_id = 0
        try:
            from_id = int(data.get("from") or 0)
        except (TypeError, ValueError):
            from_id = 0
        try:
            to_raw = data.get("to", BROADCAST_NUM)
            to_id = int(to_raw) if to_raw is not None else BROADCAST_NUM
        except (TypeError, ValueError):
            to_id = BROADCAST_NUM
        if to_id < 0:
            to_id = BROADCAST_NUM

        channel_index = data.get("channel")
        if isinstance(channel_index, int) and 0 <= channel_index < CHANNEL_COUNT:
            channel_name = self._config.channels[channel_index].name
        else:
            channel_name = parse_channel_from_meshtastic_topic(topic, self._config.root_topic)
            channel_index = self._channel_name_to_index.get(channel_name)

        if msg_type == "nodeinfo":
            body = data.get("payload")
            if not isinstance(body, dict):
                return
            user_id = str(body.get("id") or data.get("sender") or f"!{from_id:08x}")
            short_name = str(body.get("shortname") or body.get("short_name") or "?")
            long_name = str(body.get("longname") or body.get("long_name") or user_id)
            self._nodes[from_id] = NodeInfo(
                user_id=user_id,
                short_name=short_name,
                long_name=long_name,
            )
            self._emit(
                {
                    "type": "node",
                    "from_id": from_id,
                    "user_id": user_id,
                    "short_name": short_name,
                    "long_name": long_name,
                }
            )
            return

        if msg_type in (
            "text",
            "textmessage",
            "text_message_app",
            "textmessagecompressed",
            "text_message_compressed_app",
        ):
            raw_payload = data.get("payload")
            if isinstance(raw_payload, str):
                text = raw_payload
            elif isinstance(raw_payload, dict):
                text = str(raw_payload.get("text") or raw_payload.get("message") or "")
            else:
                text = str(raw_payload or "")

            if text.strip():
                if msg_id:
                    with self._lock:
                        if msg_id in self._seen_ids:
                            return
                        self._seen_ids.add(msg_id)

                chat = ChatMessage(
                    timestamp=time.time(),
                    from_id=from_id,
                    to_id=to_id,
                    text=text,
                    message_id=msg_id or int(time.time() * 1000),
                    encrypted=False,
                    channel_index=channel_index,
                    channel_name=channel_name,
                    from_short=self._name(from_id),
                    to_short=self._name(to_id) if to_id != BROADCAST_NUM else "broadcast",
                )
                self._emit({"type": "message", **chat.__dict__})
            return

        summary = self._json_activity_summary(msg_type, data)
        if summary:
            self._emit(
                {
                    "type": "activity",
                    "timestamp": time.time(),
                    "from_id": from_id,
                    "channel_index": channel_index,
                    "channel_name": channel_name,
                    "from_short": self._name(from_id),
                    "kind": msg_type,
                    "text": summary,
                }
            )

    def _parse_mesh_packet(self, topic: str, payload: bytes) -> tuple[Any | None, str]:
        """ServiceEnvelope Meshtastic, sinon MeshPacket brut."""
        channel_id = parse_channel_from_meshtastic_topic(topic, self._config.root_topic)
        if not channel_id:
            parts = topic.split("/")
            for idx, part in enumerate(parts):
                if part in ("e", "json", "c") and idx + 1 < len(parts):
                    candidate = parts[idx + 1]
                    if candidate and not candidate.startswith("!"):
                        channel_id = candidate
                    break

        try:
            envelope = mqtt_pb2.ServiceEnvelope()
            envelope.ParseFromString(payload)
            if envelope.channel_id:
                channel_id = envelope.channel_id
            if mesh_packet_has_content(envelope.packet):
                return envelope.packet, channel_id
        except Exception:
            pass

        try:
            mp = mesh_pb2.MeshPacket()
            mp.ParseFromString(payload)
            if mesh_packet_has_content(mp):
                return mp, channel_id
        except Exception:
            pass

        return None, channel_id

    def _emit_text_message(
        self,
        *,
        from_id: int,
        to_id: int,
        msg_id: int,
        text: str,
        encrypted: bool,
        channel_index: int | None,
        channel_name: str,
        mp,
    ) -> None:
        with self._lock:
            if msg_id in self._seen_ids:
                return
            self._seen_ids.add(msg_id)

        chat = ChatMessage(
            timestamp=time.time(),
            from_id=from_id,
            to_id=to_id,
            text=text,
            message_id=msg_id,
            encrypted=encrypted,
            channel_index=channel_index,
            channel_name=channel_name,
            from_short=self._name(from_id),
            to_short=self._name(to_id) if to_id != BROADCAST_NUM else "broadcast",
        )
        self._emit({"type": "message", **chat.__dict__})

        if to_id == self.node_number and mp.want_ack:
            self._send_ack(from_id, msg_id)

    def _on_message_protobuf(self, topic: str, payload: bytes) -> None:
        mp, channel_id = self._parse_mesh_packet(topic, payload)
        if mp is None:
            logger.debug("Protobuf non reconnu sur %s", topic)
            self._emit(
                {
                    "type": "error",
                    "message": (
                        f"MQTT reçu sur {topic} — payload protobuf illisible "
                        f"({len(payload)} octets)"
                    ),
                }
            )
            return

        channel_index = self._channel_name_to_index.get(channel_id)
        encrypted = False

        if packet_needs_decrypt(mp):
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

        if not packet_has_decoded(mp):
            if packet_needs_decrypt(mp):
                return
            port_hint = mp.decoded.portnum or "?"
            self._emit(
                {
                    "type": "error",
                    "message": (
                        f"MQTT reçu sur {topic} (canal {channel_id or '?'}) — "
                        f"type de paquet non affiché (port {port_hint})"
                    ),
                }
            )
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

        if port in (
            portnums_pb2.TEXT_MESSAGE_APP,
            portnums_pb2.TEXT_MESSAGE_COMPRESSED_APP,
        ):
            from_id = getattr(mp, "from")
            to_id = mp.to
            msg_id = mp.id
            ch_name = channel_id
            if channel_index is None and ch_name:
                channel_index = self._channel_name_to_index.get(ch_name)

            if port == portnums_pb2.TEXT_MESSAGE_COMPRESSED_APP:
                text = decompress_text_payload(mp.decoded.payload)
                if not text:
                    self._emit(
                        {
                            "type": "error",
                            "message": (
                                f"Message compressé illisible (canal {channel_id or '?'}) "
                                "— installez unishox2-py3"
                            ),
                        }
                    )
                    return
            else:
                try:
                    text = mp.decoded.payload.decode("utf-8")
                except UnicodeDecodeError:
                    text = mp.decoded.payload.hex()

            self._emit_text_message(
                from_id=from_id,
                to_id=to_id,
                msg_id=msg_id,
                text=text,
                encrypted=encrypted,
                channel_index=channel_index,
                channel_name=ch_name,
                mp=mp,
            )
            return

        from_id = getattr(mp, "from")
        ch_name = channel_id
        if channel_index is None and ch_name:
            channel_index = self._channel_name_to_index.get(ch_name)
        summary = self._protobuf_activity_summary(port, mp)
        if summary:
            self._emit(
                {
                    "type": "activity",
                    "timestamp": time.time(),
                    "from_id": from_id,
                    "channel_index": channel_index,
                    "channel_name": ch_name,
                    "from_short": self._name(from_id),
                    "kind": f"port_{port}",
                    "text": summary,
                }
            )

    def _json_activity_summary(self, msg_type: str, data: dict[str, Any]) -> str:
        payload = data.get("payload")
        if msg_type == "position" and isinstance(payload, dict):
            lat = payload.get("latitude_i")
            lon = payload.get("longitude_i")
            if lat is not None and lon is not None:
                return f"position {lat / 1e7:.5f}, {lon / 1e7:.5f}"
        if msg_type == "telemetry":
            return "télémétrie"
        if msg_type:
            return msg_type.replace("_", " ")
        return ""

    def _protobuf_activity_summary(self, port: int, mp) -> str:
        if port == portnums_pb2.POSITION_APP:
            try:
                pos = mesh_pb2.Position()
                pos.ParseFromString(mp.decoded.payload)
                return f"position {pos.latitude_i / 1e7:.5f}, {pos.longitude_i / 1e7:.5f}"
            except Exception:
                return "position"
        if port == portnums_pb2.TELEMETRY_APP:
            return "télémétrie"
        return f"paquet port {port}"

    def _send_ack(self, destination_id: int, message_id: int) -> None:
        encoded = mesh_pb2.Data()
        encoded.portnum = portnums_pb2.ROUTING_APP
        encoded.request_id = message_id
        encoded.payload = b"\030\000"
        self._publish_packet(destination_id, encoded)

    def get_rx_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "rx_count": self._mqtt_rx_count,
                "last_topic": self._last_mqtt_topic,
                "last_rx_at": self._last_mqtt_rx_at,
            }

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


def decompress_text_payload(payload: bytes) -> str | None:
    """Décompresse TEXT_MESSAGE_COMPRESSED_APP (Unishox2)."""
    if not payload or unishox2 is None:
        return None
    try:
        return unishox2.decompress(payload, MESH_TEXT_MESSAGE_MAX_BYTES)
    except Exception:
        return None


class AsyncMeshtasticBridge:
    """Expose le client MQTT à FastAPI via callback asyncio thread-safe."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._publish: Callable[[dict[str, Any]], None] | None = None
        self.client = MeshtasticMqttClient(self._thread_callback)

    def bind_loop(
        self,
        loop: asyncio.AbstractEventLoop,
        publish: Callable[[dict[str, Any]], None],
    ) -> None:
        self._loop = loop
        self._publish = publish

    def _thread_callback(self, event: dict[str, Any]) -> None:
        if self._loop and self._publish:
            self._loop.call_soon_threadsafe(self._publish, event)
