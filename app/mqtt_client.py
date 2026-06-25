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
MESHTASTIC_PKI_CHANNEL = "PKI"
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


def _topic_has_segment(topic: str, segment: str) -> bool:
    return segment.lower() in (topic or "").lower()


def infer_mqtt_root_from_topic(topic: str) -> str | None:
    """Extrait le root MQTT (msh/REGION ou mesh/REGION — jamais « msh » seul)."""
    tl = (topic or "").lower()
    for marker in ("/2/e/", "/2/json/", "/2/c/"):
        i = tl.find(marker)
        if i >= 0:
            root = topic[:i].rstrip("/")
            parts = [p for p in root.split("/") if p]
            if len(parts) >= 2 and parts[0] in ("msh", "mesh") and parts[1]:
                return f"{parts[0]}/{parts[1]}"
    return None


def mqtt_subscribe_topics(root: str) -> list[str]:
    """Wildcards d'abonnement — root configuré uniquement (msh/EU_868/2/e/# …)."""
    base = mqtt_root_raw(root).rstrip("/")
    topics: list[str] = []
    for json_flag, legacy in ((False, False), (True, False), (False, True)):
        topics.append(mqtt_topic_prefix(base, json=json_flag, legacy=legacy) + "#")
        raw = mqtt_root_raw(root)
        if raw.endswith("/"):
            topics.append(mqtt_topic_prefix(raw, json=json_flag, legacy=legacy) + "#")
    return list(dict.fromkeys(topics))


def mqtt_downlink_protobuf_topic(root: str, channel_name: str, node_name: str) -> str:
    """Topic protobuf downlink — root + /2/e/ (comme mqtt_topic_prefix firmware)."""
    return mqtt_topic_prefix(root, json=False) + f"{channel_name}/{node_name}"


def mqtt_downlink_json_sendtext_topic(root: str) -> str:
    """Topic JSON sendtext — root + /2/json/mqtt (doc Meshtastic)."""
    return mqtt_topic_prefix(root, json=True) + "mqtt"


def mqtt_downlink_json_sendtext_topics(root: str) -> list[str]:
    """Topics JSON sendtext — avec et sans slash final (doc Meshtastic)."""
    topics = [mqtt_downlink_json_sendtext_topic(root)]
    raw = mqtt_root_raw(root).rstrip("/")
    topics.append(f"{raw}/2/json/mqtt/")
    return list(dict.fromkeys(topics))


def mqtt_publish_topics(root: str, channel_name: str, node_name: str) -> list[str]:
    """Topic downlink protobuf — msh/EU_868/2/e/… (sans segment vide //)."""
    tail = f"{channel_name}/{node_name}"
    return [mqtt_topic_prefix(root, json=False) + tail]


def parse_channel_from_meshtastic_topic(topic: str, root: str = "") -> str:
    """Extrait le nom de canal depuis un topic Meshtastic (…/2/json/Canal/!node)."""
    tl = (topic or "").lower()
    for marker in ("/2/json/", "/2/e/", "/2/c/"):
        i = tl.find(marker)
        if i >= 0:
            rest = topic[i + len(marker) :]
            return rest.split("/")[0] if rest else ""
    base = mqtt_root_raw(root).rstrip("/")
    if base and topic.startswith(base):
        rest = topic[len(base) :].lstrip("/")
        for segment in MESHTASTIC_TOPIC_PREFIXES:
            seg = segment.lstrip("/")
            if rest.lower().startswith(seg.lower()):
                rest = rest[len(seg) :].lstrip("/")
                break
        return rest.split("/")[0] if rest else ""
    return ""


def is_meshtastic_downlink_json_topic(topic: str) -> bool:
    """Topic JSON sendtext downlink exact : …/2/json/mqtt (sans /!node après)."""
    tl = (topic or "").lower().rstrip("/")
    marker = "/json/mqtt"
    idx = tl.rfind(marker)
    if idx < 0:
        return False
    return tl[idx + len(marker) :] == ""


def is_meshtastic_json_topic(topic: str, root: str = "") -> bool:
    tl = (topic or "").lower()
    if "/2/json/" not in tl:
        return False
    if is_meshtastic_downlink_json_topic(topic):
        return False
    if tl.startswith("msh/") or tl.startswith("mesh/"):
        return True
    base = mqtt_root_raw(root).rstrip("/")
    return bool(base) and tl.startswith(base.lower())


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
    gateway_id: str = ""
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


@dataclass
class NodePosition:
    from_id: int
    latitude: float
    longitude: float
    timestamp: float
    channel_index: int | None = None
    channel_name: str = ""
    from_short: str = "?"
    long_name: str = ""
    altitude: float | None = None


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
        self._positions: dict[int, NodePosition] = {}
        self._seen_ids: set[int] = set()
        self._lock = threading.Lock()
        self._channel_name_to_index: dict[str, int] = {}
        self._mqtt_rx_count = 0
        self._last_mqtt_topic = ""
        self._last_mqtt_rx_at: float | None = None
        # None = auto ; True/False = format uplink MQTT observé (protobuf chiffré ou decoded)
        self._uplink_mqtt_encrypted: bool | None = None
        self._last_uplink_topic_by_channel: dict[str, str] = {}
        self._last_uplink_hop_by_channel: dict[str, int] = {}
        # Enveloppe MQTT brute du dernier texte reçu par canal (downlink miroir)
        self._last_uplink_envelope_bytes: dict[str, bytes] = {}
        self._last_uplink_was_encrypted: dict[str, bool] = {}
        self._last_uplink_channel_id: dict[str, str] = {}
        self._last_uplink_gateway_id: dict[str, str] = {}
        self._last_uplink_sender_id: dict[str, str] = {}
        self._last_uplink_root_by_channel: dict[str, str] = {}
        self._inferred_mqtt_root: str | None = None
        self._recent_outbound_texts: dict[str, float] = {}
        self._recent_outbound_direct: dict[tuple[int, str], float] = {}

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
        return "!" + format(self.node_number, "08x")

    def _emit(self, event: dict[str, Any]) -> None:
        self._on_event(event)

    def _rebuild_channel_map(self) -> None:
        self._channel_name_to_index = {
            ch.name: i for i, ch in enumerate(self._config.channels) if ch.name.strip()
        }

    def connect(self, config: MqttConfig, *, announce: bool = True) -> None:
        self.disconnect()
        self._config = config
        self._announce_on_connect = announce
        self._rebuild_channel_map()
        self._uplink_mqtt_encrypted = None
        self._last_uplink_topic_by_channel = {}
        self._last_uplink_hop_by_channel = {}
        self._last_uplink_envelope_bytes = {}
        self._last_uplink_was_encrypted = {}
        self._last_uplink_channel_id = {}
        self._last_uplink_gateway_id = {}
        self._last_uplink_sender_id = {}
        self._last_uplink_root_by_channel = {}
        self._inferred_mqtt_root = None
        self._recent_outbound_texts = {}
        self._recent_outbound_direct = {}
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
        topics = mqtt_publish_topics(self._config.root_topic, channel_name, self.node_name)
        return topics[0]

    def _next_packet_id(self) -> int:
        ts_ms = int(time.time() * 1000)
        rnd = secrets.randbelow(0x10000)
        return ((ts_ms & 0xFFFF) << 16 | rnd) & 0xFFFFFFFF

    def _downlink_data_copy(self, encoded_message, *, encrypt: bool) -> mesh_pb2.Data:
        """Copie Data pour downlink — sans bitfield (compat gateways Meshtastic)."""
        data = mesh_pb2.Data()
        data.portnum = encoded_message.portnum
        data.payload = encoded_message.payload
        if encrypt and encoded_message.request_id:
            data.request_id = encoded_message.request_id
        return data

    def _is_direct_message(self, destination_id: int) -> bool:
        return destination_id != BROADCAST_NUM

    def _note_outbound_text(self, text: str, destination_id: int) -> None:
        expiry = time.time() + 12.0
        self._recent_outbound_texts[text] = expiry
        if self._is_direct_message(destination_id):
            self._recent_outbound_direct[(destination_id, text)] = expiry

    def _is_outbound_echo(self, text: str, to_id: int, from_id: int) -> bool:
        now = time.time()
        if self._recent_outbound_texts.get(text, 0) <= now:
            return False
        if not self._is_direct_message(to_id):
            return True
        if self._recent_outbound_direct.get((to_id, text), 0) <= now:
            return False
        gw = (self._config.gateway_id or "").strip()
        if gw.startswith("!") and from_id == int(gw[1:], 16):
            return True
        return from_id == self.node_number

    def _downlink_envelope_channel_id(self, channel: ChannelConfig, destination_id: int) -> str:
        """ServiceEnvelope.channel_id — PKI pour DM (firmware Meshtastic 2.5+)."""
        if self._is_direct_message(destination_id):
            return MESHTASTIC_PKI_CHANNEL
        return self._downlink_channel_id(channel)

    def _downlink_channel_id(self, channel: ChannelConfig) -> str:
        """channel_id ServiceEnvelope — reprend l'uplink observé (getGlobalId côté radio)."""
        return self._last_uplink_channel_id.get(channel.name, channel.name)

    def _store_uplink_envelope(
        self,
        channel_name: str,
        payload: bytes,
        was_encrypted: bool,
        *,
        sender_id: int | None = None,
    ) -> None:
        if not channel_name:
            return
        self._last_uplink_envelope_bytes[channel_name] = bytes(payload)
        self._last_uplink_was_encrypted[channel_name] = was_encrypted
        if sender_id:
            self._last_uplink_sender_id[channel_name] = f"!{sender_id:08x}"
        try:
            env = mqtt_pb2.ServiceEnvelope()
            env.ParseFromString(payload)
            if env.channel_id:
                self._last_uplink_channel_id[channel_name] = env.channel_id
            if env.gateway_id:
                self._last_uplink_gateway_id[channel_name] = env.gateway_id
                self._remember_gateway_id(env.gateway_id)
        except Exception:
            pass

    def _note_uplink_gateway_from_topic(self, channel_name: str, topic: str) -> None:
        """Complète gateway_id depuis le topic MQTT (JSON ou protobuf)."""
        if not channel_name or not topic:
            return
        parts = topic.split("/")
        if parts and parts[-1].startswith("!"):
            gw = parts[-1]
            self._last_uplink_gateway_id.setdefault(channel_name, gw)
            self._remember_gateway_id(gw)

    def _remember_gateway_id(self, gateway_name: str) -> None:
        """Mémorise l'ID gateway MQTT pour downlink sur tous les canaux."""
        if not gateway_name.startswith("!"):
            return
        for _, ch in self._config.named_channels():
            if ch.name:
                self._last_uplink_gateway_id.setdefault(ch.name, gateway_name)
        self._last_uplink_gateway_id.setdefault(MESHTASTIC_PKI_CHANNEL, gateway_name)
        if self._config.gateway_id == gateway_name:
            return
        self._config.gateway_id = gateway_name
        try:
            from app.settings import load_settings, save_settings

            settings = load_settings()
            if settings.get("mqtt", {}).get("gateway_id") != gateway_name:
                save_settings(
                    {
                        **settings,
                        "mqtt": {**settings["mqtt"], "gateway_id": gateway_name},
                    }
                )
        except Exception as exc:
            logger.debug("Persistance gateway_id ignorée: %s", exc)

    def _seed_downlink_state_for_all_channels(self) -> None:
        """Prépare le downlink sur chaque canal actif (gateway config + JSON par défaut)."""
        gw = (self._config.gateway_id or "").strip()
        if gw:
            for _, ch in self._config.named_channels():
                if ch.name:
                    self._last_uplink_gateway_id.setdefault(ch.name, gw)
            self._last_uplink_gateway_id.setdefault(MESHTASTIC_PKI_CHANNEL, gw)
        for _, ch in self._config.named_channels():
            if ch.name and ch.name not in self._last_uplink_was_encrypted:
                self._last_uplink_was_encrypted[ch.name] = False

    def _gateway_for_channel(self, channel_name: str) -> str:
        gw = self._last_uplink_gateway_id.get(channel_name) or self._config.gateway_id
        if gw:
            return gw
        if self._last_uplink_gateway_id:
            return next(iter(self._last_uplink_gateway_id.values()))
        return ""

    def _gateway_only_topics(self, channel_name: str) -> list[str]:
        return self._publish_topics_for_channel(channel_name)

    def _configured_mqtt_root(self) -> str:
        return mqtt_root_raw(self._config.root_topic).rstrip("/")

    def _json_sendtext_root(self, channel_name: str = "") -> str:
        """Root JSON sendtext — uplink du canal, sinon config msh/EU_868."""
        if channel_name:
            stored = self._last_uplink_root_by_channel.get(channel_name)
            if stored:
                return stored.rstrip("/")
            ref = self._last_uplink_topic_by_channel.get(channel_name)
            if ref:
                inferred = infer_mqtt_root_from_topic(ref)
                if inferred:
                    return inferred.rstrip("/")
        for topic in self._last_uplink_topic_by_channel.values():
            inferred = infer_mqtt_root_from_topic(topic)
            if inferred:
                return inferred.rstrip("/")
        return self._configured_mqtt_root()

    def _effective_mqtt_root(self) -> str:
        """Root effectif — config msh/EU_868, ou inféré si valide (jamais « msh » seul)."""
        cfg = self._configured_mqtt_root()
        inf = (self._inferred_mqtt_root or "").rstrip("/")
        if inf and infer_mqtt_root_from_topic(f"{inf}/2/e/x") == inf:
            return inf
        return cfg

    def _note_topic_alignment(self, topic: str, channel_name: str = "") -> None:
        root = infer_mqtt_root_from_topic(topic)
        if root is not None:
            self._inferred_mqtt_root = root
            if channel_name:
                self._last_uplink_root_by_channel[channel_name] = root.rstrip("/")

    def _root_for_channel(self, channel_name: str) -> str:
        return self._configured_mqtt_root()

    def _publish_topics_for_channel(
        self, channel_name: str, destination_id: int = BROADCAST_NUM
    ) -> list[str]:
        """Downlink protobuf — topic PKI pour DM, sinon canal mesh."""
        if self._is_direct_message(destination_id):
            gw = self._gateway_for_channel(MESHTASTIC_PKI_CHANNEL) or self._gateway_for_channel(
                channel_name
            )
            cfg = self._configured_mqtt_root()
            ref = self._last_uplink_topic_by_channel.get(MESHTASTIC_PKI_CHANNEL)
            if ref and _topic_has_segment(ref, "/2/e/") and gw:
                observed = (infer_mqtt_root_from_topic(ref) or "").rstrip("/")
                if observed == cfg:
                    prefix = ref.rsplit("/", 1)[0]
                    return [f"{prefix}/{gw}"]
            if gw:
                return mqtt_publish_topics(cfg, MESHTASTIC_PKI_CHANNEL, gw)
            return mqtt_publish_topics(cfg, MESHTASTIC_PKI_CHANNEL, self.node_name)

        ref = self._last_uplink_topic_by_channel.get(channel_name)
        gw = self._gateway_for_channel(channel_name)
        ch_id = self._last_uplink_channel_id.get(channel_name, channel_name)
        cfg = self._configured_mqtt_root()

        if ref and _topic_has_segment(ref, "/2/e/"):
            observed = (infer_mqtt_root_from_topic(ref) or "").rstrip("/")
            if observed == cfg and gw:
                prefix = ref.rsplit("/", 1)[0]
                return [f"{prefix}/{gw}"]
            if gw:
                return mqtt_publish_topics(cfg, ch_id, gw)

        if ref and _topic_has_segment(ref, "/2/json/"):
            observed = (infer_mqtt_root_from_topic(ref) or cfg).rstrip("/")
            root = observed if observed == cfg else cfg
            if gw:
                return mqtt_publish_topics(root, ch_id, gw)

        if gw:
            topics = mqtt_publish_topics(cfg, ch_id, gw)
            bare = mqtt_topic_prefix(cfg, json=False) + ch_id
            if bare not in topics:
                topics.append(bare)
            return topics

        return mqtt_publish_topics(cfg, ch_id, self.node_name)

    def _subscribe_topics(self) -> list[str]:
        """Abonnements MQTT — wildcards firmware Meshtastic uniquement."""
        return mqtt_subscribe_topics(self._config.root_topic)

    def _primary_channel_index(self) -> int:
        for i, ch in enumerate(self._config.channels):
            if ch.role == "PRINCIPAL":
                return i
        return 0

    def _effective_channel_key(self, channel_index: int, channel: ChannelConfig) -> str:
        """Clé PSK effective — canal secondaire sans PSK utilise la clé primaire (firmware Meshtastic)."""
        key = str(channel.key or "").strip()
        if key and key not in ("", "AQ=="):
            return key
        if channel_index != self._primary_channel_index():
            primary = self._config.channels[self._primary_channel_index()]
            pk = str(primary.key or "").strip()
            if pk:
                return pk
        return key or "AQ=="

    def _note_uplink_mqtt_format(self, mp) -> None:
        if packet_needs_decrypt(mp) or mp.encrypted:
            self._uplink_mqtt_encrypted = True
        elif packet_has_decoded(mp):
            self._uplink_mqtt_encrypted = False

    def _should_encrypt_downlink(self, channel: ChannelConfig) -> bool:
        """Chiffrer seulement si l'uplink MQTT protobuf chiffré a été observé sur ce canal."""
        if channel.name in self._last_uplink_was_encrypted:
            return self._last_uplink_was_encrypted[channel.name]
        return False

    def _apply_downlink_hops(self, mp) -> None:
        """Hops pour injection MQTT → mesh (format netnutmike : hop_limit seul)."""
        mp.hop_limit = 3
        mp.ClearField("hop_start")

    def _build_downlink_standard(
        self,
        channel: ChannelConfig,
        channel_index: int,
        destination_id: int,
        encoded_message,
        encrypt: bool,
    ) -> bytes:
        """Downlink construit (Connect / netnutmike) — gateway_id ≠ nœud WiFi gateway."""
        channel_id = self._downlink_envelope_channel_id(channel, destination_id)
        payload_data = self._downlink_data_copy(encoded_message, encrypt=encrypt)
        effective_key = self._effective_channel_key(channel_index, channel)

        mesh_packet = mesh_pb2.MeshPacket()
        mesh_packet.id = self._next_packet_id()
        setattr(mesh_packet, "from", self.node_number)
        mesh_packet.to = destination_id
        mesh_packet.want_ack = False
        self._apply_downlink_hops(mesh_packet)

        if encrypt:
            channel_hash, encrypted = encrypt_payload(
                channel.name,
                effective_key,
                mesh_packet.id,
                self.node_number,
                payload_data,
            )
            mesh_packet.channel = channel_hash
            mesh_packet.encrypted = encrypted
            mesh_packet.ClearField("decoded")
        else:
            mesh_packet.channel = 0
            mesh_packet.decoded.CopyFrom(payload_data)
            mesh_packet.ClearField("encrypted")

        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.packet.CopyFrom(mesh_packet)
        envelope.channel_id = channel_id
        envelope.gateway_id = self.node_name
        return envelope.SerializeToString()

    def _build_downlink_from_template(
        self,
        channel: ChannelConfig,
        channel_index: int,
        destination_id: int,
        encoded_message,
        encrypt: bool,
    ) -> bytes | None:
        """Reconstruit le downlink en clonant la dernière enveloppe uplink du canal."""
        raw = self._last_uplink_envelope_bytes.get(channel.name)
        if not raw:
            return None
        if self._last_uplink_was_encrypted.get(channel.name, False) != encrypt:
            return None
        try:
            env = mqtt_pb2.ServiceEnvelope()
            env.ParseFromString(raw)
            p = env.packet

            if encrypt:
                mesh_packet = mesh_pb2.MeshPacket()
                mesh_packet.id = self._next_packet_id()
                setattr(mesh_packet, "from", self.node_number)
                mesh_packet.to = destination_id
                mesh_packet.want_ack = False
                self._apply_downlink_hops(mesh_packet)
                payload_data = self._downlink_data_copy(encoded_message, encrypt=True)
                effective_key = self._effective_channel_key(channel_index, channel)
                channel_hash, encrypted = encrypt_payload(
                    channel.name,
                    effective_key,
                    mesh_packet.id,
                    self.node_number,
                    payload_data,
                )
                mesh_packet.channel = channel_hash
                mesh_packet.encrypted = encrypted
                env.packet.CopyFrom(mesh_packet)
            else:
                # Clone minimal : hops, channel et bitfield identiques à l'uplink reçu
                p.id = self._next_packet_id()
                setattr(p, "from", self.node_number)
                p.to = destination_id
                p.want_ack = False
                p.decoded.payload = encoded_message.payload
                p.decoded.portnum = encoded_message.portnum
                p.ClearField("encrypted")

            # gateway_id ≠ owner.id de la radio WiFi — sinon firmware ignore le downlink
            env.gateway_id = self.node_name
            if not env.channel_id or self._is_direct_message(destination_id):
                env.channel_id = self._downlink_envelope_channel_id(channel, destination_id)
            return env.SerializeToString()
        except Exception as exc:
            logger.debug("Downlink miroir uplink impossible: %s", exc)
            return None

    def _publish_json_sendtext(
        self,
        channel_index: int,
        destination_id: int,
        text: str,
        gateway_name: str,
    ) -> list[str]:
        """Downlink JSON sendtext — mécanisme officiel Meshtastic (firmware → sendToMesh)."""
        from_id = int(gateway_name[1:], 16)
        body: dict[str, Any] = {
            "from": from_id,
            "type": "sendtext",
            "payload": text,
        }
        if self._is_direct_message(destination_id):
            body["to"] = destination_id
            body["hopLimit"] = 7
        else:
            body["channel"] = channel_index
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        ch_name = (
            self._config.channels[channel_index].name
            if 0 <= channel_index < len(self._config.channels)
            else ""
        )
        root = self._configured_mqtt_root()
        ref = self._last_uplink_topic_by_channel.get(ch_name)
        if ref:
            inferred = infer_mqtt_root_from_topic(ref)
            if inferred and inferred.rstrip("/") == root:
                root = inferred.rstrip("/")
        topics = mqtt_downlink_json_sendtext_topics(root)
        for topic in topics:
            self._client.publish(topic, payload, qos=1)
        self._note_outbound_text(text, destination_id)
        logger.info(
            "MQTT JSON sendtext %s body=%s",
            topics[0],
            body,
        )
        return topics

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
            add(self._effective_channel_key(idx, self._config.channels[idx]))
        for i, ch in self._config.named_channels():
            add(ch.key)
            add(self._effective_channel_key(i, ch))
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

        is_text = encoded_message.portnum == portnums_pb2.TEXT_MESSAGE_APP
        text: str | None = None
        if is_text:
            try:
                text = encoded_message.payload.decode("utf-8")
            except UnicodeDecodeError:
                text = None

        json_topics: list[str] = []
        gw_hint = (
            self._gateway_for_channel(MESHTASTIC_PKI_CHANNEL)
            if self._is_direct_message(destination_id)
            else self._gateway_for_channel(channel.name)
        )
        if text and gw_hint and channel.name != "mqtt":
            json_topics = self._publish_json_sendtext(idx, destination_id, text, gw_hint)

        if self._is_direct_message(destination_id):
            to_hex = f"!{destination_id:08x}"
            activity_parts: list[str] = []
            if json_topics:
                activity_parts.append(
                    f"↑ JSON sendtext DM {json_topics[0]} → {to_hex} via {gw_hint}"
                )
                activity_parts.append(
                    "confirmation mesh : réception sur le Tag (PKI), pas l'écho MQTT …/json/PKI/"
                )
            else:
                activity_parts.append(
                    f"DM non publié — gateway_id manquant pour JSON sendtext → {to_hex}"
                )
            self._emit(
                {
                    "type": "activity",
                    "timestamp": time.time(),
                    "from_id": self.node_number,
                    "channel_index": idx,
                    "channel_name": channel.name,
                    "from_short": self._config.short_name,
                    "kind": "sent",
                    "text": " — ".join(activity_parts),
                }
            )
            return

        encrypt_downlink = self._should_encrypt_downlink(channel)
        payload = self._build_downlink_from_template(
            channel, idx, destination_id, encoded_message, encrypt_downlink
        )
        if payload is not None:
            downlink_mode = "miroir uplink" + (" chiffré" if encrypt_downlink else " decoded")
        else:
            payload = self._build_downlink_standard(
                channel, idx, destination_id, encoded_message, encrypt_downlink
            )
            downlink_mode = "standard" + (" chiffré" if encrypt_downlink else " decoded")

        topics = self._publish_topics_for_channel(channel.name, destination_id)
        sender_hint = self._last_uplink_sender_id.get(channel.name, "")
        for topic in topics:
            self._client.publish(topic, payload, qos=1)

        extra_mode = ""
        if not encrypt_downlink and self._last_uplink_was_encrypted.get(channel.name) is True:
            gw_topics = self._gateway_only_topics(channel.name)
            if gw_topics:
                enc_payload = self._build_downlink_standard(
                    channel, idx, destination_id, encoded_message, True
                )
                for topic in gw_topics:
                    self._client.publish(topic, enc_payload, qos=1)
                extra_mode = " + essai chiffré (gateway)"

        logger.info("MQTT downlink %s (%s, %d octets)", topics[0], downlink_mode, len(payload))
        activity_parts: list[str] = []
        if json_topics:
            activity_parts.append(
                f"↑ JSON sendtext {json_topics[0]} via {gw_hint} (canal mesh {idx})"
            )
        activity_parts.append(f"↑ protobuf {topics[0]} ({downlink_mode}{extra_mode})")
        if len(topics) > 1:
            activity_parts.append(f"+{len(topics) - 1} topics protobuf")
        if gw_hint and not json_topics:
            activity_parts.append(f"gateway {gw_hint} (sans JSON sendtext)")
        elif gw_hint and json_topics:
            activity_parts.append(
                f"confirmation mesh : JSON sur …/json/{channel.name}/!{gw_hint.lstrip('!')}"
            )
        if sender_hint and sender_hint != gw_hint:
            activity_parts.append(f"émetteur mesh {sender_hint}")
        self._emit(
            {
                "type": "activity",
                "timestamp": time.time(),
                "from_id": self.node_number,
                "channel_index": idx,
                "channel_name": channel.name,
                "from_short": self._config.short_name,
                "kind": "sent",
                "text": " — ".join(activity_parts),
            }
        )

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
        self._seed_downlink_state_for_all_channels()
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
        if getattr(self, "_announce_on_connect", True):
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

    @staticmethod
    def _coords_valid(latitude: float, longitude: float) -> bool:
        if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
            return False
        return not (latitude == 0.0 and longitude == 0.0)

    def _store_position(
        self,
        *,
        from_id: int,
        latitude: float,
        longitude: float,
        channel_index: int | None,
        channel_name: str,
        altitude: float | None = None,
    ) -> None:
        if not self._coords_valid(latitude, longitude):
            return

        info = self._nodes.get(from_id)
        record = NodePosition(
            from_id=from_id,
            latitude=latitude,
            longitude=longitude,
            timestamp=time.time(),
            channel_index=channel_index,
            channel_name=channel_name,
            from_short=self._name(from_id),
            long_name=info.long_name if info else self._name(from_id, "long"),
            altitude=altitude,
        )
        with self._lock:
            self._positions[from_id] = record
        self._emit({"type": "position", **record.__dict__})

    def _refresh_position_node_names(self, from_id: int) -> None:
        with self._lock:
            pos = self._positions.get(from_id)
            if not pos:
                return
            pos.from_short = self._name(from_id)
            pos.long_name = self._name(from_id, "long")
            payload = pos.__dict__.copy()
        self._emit({"type": "position", **payload})

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
        if _topic_has_segment(topic, "/2/json/") and msg.payload:
            try:
                data = json.loads(msg.payload.decode("utf-8"))
                if isinstance(data, dict):
                    self._on_message_json(topic, msg.payload)
                    return
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass
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

        if is_meshtastic_downlink_json_topic(topic) or msg_type == "sendtext":
            return

        if from_id == self.node_number:
            return

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
            self._refresh_position_node_names(from_id)
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
                if self._is_outbound_echo(text.strip(), to_id, from_id):
                    logger.debug("Écho MQTT ignoré (envoi récent) : %r → %s", text[:40], to_id)
                    return

                if msg_id:
                    with self._lock:
                        if msg_id in self._seen_ids:
                            return
                        self._seen_ids.add(msg_id)

                if channel_name:
                    self._note_topic_alignment(topic, channel_name or "")
                    self._last_uplink_topic_by_channel[channel_name] = topic
                    self._last_uplink_was_encrypted[channel_name] = False
                    self._note_uplink_gateway_from_topic(channel_name, topic)
                    if from_id:
                        self._last_uplink_sender_id[channel_name] = f"!{from_id:08x}"

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

        if msg_type == "position":
            body = data.get("payload")
            if isinstance(body, dict):
                try:
                    lat_i = int(body.get("latitude_i"))
                    lon_i = int(body.get("longitude_i"))
                except (TypeError, ValueError):
                    lat_i = lon_i = None
                if lat_i is not None and lon_i is not None:
                    alt_raw = body.get("altitude")
                    altitude = float(alt_raw) if alt_raw is not None else None
                    self._store_position(
                        from_id=from_id,
                        latitude=lat_i / 1e7,
                        longitude=lon_i / 1e7,
                        channel_index=channel_index,
                        channel_name=channel_name,
                        altitude=altitude,
                    )
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
        if text.strip() and self._is_outbound_echo(text.strip(), to_id, from_id):
            logger.debug("Écho protobuf ignoré (envoi récent) : %r → %s", text[:40], to_id)
            return

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

        from_id = getattr(mp, "from", 0)
        if from_id == self.node_number:
            return

        if from_id and channel_id:
            self._note_topic_alignment(topic, channel_id or "")
            self._last_uplink_topic_by_channel[channel_id] = topic
            self._note_uplink_gateway_from_topic(channel_id, topic)
            if channel_id == MESHTASTIC_PKI_CHANNEL:
                self._last_uplink_was_encrypted[MESHTASTIC_PKI_CHANNEL] = False
            if mp.hop_limit:
                self._last_uplink_hop_by_channel[channel_id] = mp.hop_limit

        self._note_uplink_mqtt_format(mp)
        channel_index = self._channel_name_to_index.get(channel_id)
        encrypted = False
        was_encrypted_on_wire = packet_needs_decrypt(mp) or (
            bool(mp.encrypted) and not packet_has_decoded(mp)
        )

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
            self._refresh_position_node_names(from_id)
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

            if ch_name:
                self._store_uplink_envelope(
                    ch_name, payload, was_encrypted_on_wire, sender_id=from_id
                )

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

        if port == portnums_pb2.POSITION_APP:
            from_id = getattr(mp, "from")
            ch_name = channel_id
            if channel_index is None and ch_name:
                channel_index = self._channel_name_to_index.get(ch_name)
            try:
                pos = mesh_pb2.Position()
                pos.ParseFromString(mp.decoded.payload)
                altitude = float(pos.altitude) if pos.altitude else None
                self._store_position(
                    from_id=from_id,
                    latitude=pos.latitude_i / 1e7,
                    longitude=pos.longitude_i / 1e7,
                    channel_index=channel_index,
                    channel_name=ch_name,
                    altitude=altitude,
                )
            except Exception:
                pass
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

    def get_downlink_debug(self) -> dict[str, Any]:
        """État downlink par canal (gateway MQTT vs émetteur mesh)."""
        channels: dict[str, Any] = {}
        for _, ch in self._config.named_channels():
            name = ch.name
            if not name:
                continue
            idx = self._channel_name_to_index.get(name)
            gw = self._gateway_for_channel(name)
            ch_root = self._configured_mqtt_root()
            json_topics = mqtt_downlink_json_sendtext_topics(ch_root)
            proto_topics = self._publish_topics_for_channel(name)
            gw_decimal = int(gw[1:], 16) if gw.startswith("!") else None
            channels[name] = {
                "gateway_id": gw,
                "sender_id": self._last_uplink_sender_id.get(name, ""),
                "channel_id_envelope": self._last_uplink_channel_id.get(name, name),
                "channel_index": idx,
                "last_uplink_topic": self._last_uplink_topic_by_channel.get(name, ""),
                "last_uplink_root": self._last_uplink_root_by_channel.get(name, ""),
                "uplink_encrypted": self._last_uplink_was_encrypted.get(name),
                "has_envelope_template": name in self._last_uplink_envelope_bytes,
                "json_sendtext_topics": json_topics,
                "protobuf_downlink_topics": proto_topics,
                "json_sendtext_from_decimal": gw_decimal,
            }
        return {
            "virtual_node": self.node_name,
            "config_root_topic": self._config.root_topic,
            "config_gateway_id": self._config.gateway_id,
            "json_sendtext_root": self._json_sendtext_root(),
            "inferred_mqtt_root": self._inferred_mqtt_root,
            "uplink_mqtt_encrypted": self._uplink_mqtt_encrypted,
            "channels": channels,
            "mqtt_channel_required": (
                "Sur la gateway WiFi : canal radio nommé « mqtt » avec downlink ON "
                "+ Module MQTT → JSON enabled ON. Sans ce canal, le JSON sendtext "
                "est ignoré par le firmware (warn série : channel not called mqtt)."
            ),
            "hint": (
                "Downlink identique sur tous les canaux actifs : JSON sendtext (canal radio "
                "« mqtt » slot 6 sur la gateway) + protobuf decoded. Les index 0–7 MeshQTT "
                "doivent correspondre aux slots de la gateway. Confirmation mesh : uplink "
                "JSON sur …/json/{canal}/!gateway."
            ),
        }

    def get_rx_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "rx_count": self._mqtt_rx_count,
                "last_topic": self._last_mqtt_topic,
                "last_rx_at": self._last_mqtt_rx_at,
                "uplink_mqtt_encrypted": self._uplink_mqtt_encrypted,
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

    def get_positions(self) -> list[dict[str, Any]]:
        with self._lock:
            return [p.__dict__ for p in sorted(self._positions.values(), key=lambda p: p.from_id)]


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
