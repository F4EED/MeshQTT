"""Sonar Mosquitto : vérifie qu'un downlink MeshQTT est visible sur le topic gateway."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt
from meshtastic.protobuf import mqtt_pb2, portnums_pb2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.settings import load_settings, settings_to_mqtt_config  # noqa: E402

TEST_TEXT = "probe meshqtt downlink"


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe downlink protobuf sur un canal")
    parser.add_argument("--channel", default="D_Ligerien", help="Nom du canal (Fr_Balise, …)")
    args = parser.parse_args()
    channel = args.channel

    settings = load_settings()
    cfg = settings_to_mqtt_config(settings)
    mesh = settings.get("meshtastic", {})
    node_id = int(mesh.get("node_id") or 0xADBA3757)
    node_name = f"!{node_id:08x}"

    last_uplink: tuple[str, bytes] | None = None

    def on_message(_c, _u, msg) -> None:
        nonlocal last_uplink
        if channel not in (msg.topic or ""):
            return
        last_uplink = (msg.topic, bytes(msg.payload))
        print(f"Uplink capturé: {msg.topic} ({len(msg.payload)} octets)")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = on_message
    client.connect(cfg.broker, cfg.port, 60)
    client.subscribe(f"msh/EU_868/2/e/{channel}/#")
    client.subscribe(f"msh/EU_868//2/e/{channel}/#")
    client.loop_start()

    print(f"Broker {cfg.broker}:{cfg.port} — en attente d'un message sur {channel} (30 s)…")
    deadline = time.time() + 30
    while time.time() < deadline and last_uplink is None:
        time.sleep(0.2)

    if not last_uplink:
        print(f"Aucun uplink reçu — envoyez un message mesh sur {channel} puis relancez.")
        client.loop_stop()
        client.disconnect()
        sys.exit(1)

    topic, raw = last_uplink
    env = mqtt_pb2.ServiceEnvelope()
    env.ParseFromString(raw)
    gw = env.gateway_id or topic.rsplit("/", 1)[-1]
    prefix = topic.rsplit("/", 1)[0]

    env.packet.id = int(time.time() * 1000) & 0xFFFFFFFF
    setattr(env.packet, "from", node_id)
    env.packet.to = 0xFFFFFFFF
    env.packet.decoded.payload = TEST_TEXT.encode("utf-8")
    env.packet.decoded.portnum = portnums_pb2.TEXT_MESSAGE_APP
    env.packet.ClearField("encrypted")
    env.gateway_id = node_name
    payload = env.SerializeToString()

    down_topic = f"{prefix}/{gw}"
    print(f"Publication probe → {down_topic}")
    print(f"  channel_id={env.channel_id!r} gateway_id={env.gateway_id!r} from={node_name}")
    client.publish(down_topic, payload, qos=1)

    print("Écoute 15 s (retransmission MQTT ou mesh visible en uplink)…")
    seen = 0
    t0 = time.time()

    def on_probe(_c, _u, msg) -> None:
        nonlocal seen
        if channel not in (msg.topic or ""):
            return
        if msg.payload == payload:
            return
        seen += 1
        try:
            e = mqtt_pb2.ServiceEnvelope()
            e.ParseFromString(msg.payload)
            text = e.packet.decoded.payload.decode("utf-8", errors="replace")
            print(f"  MQTT vu: {msg.topic} from !{getattr(e.packet, 'from', 0):08x} text={text!r}")
        except Exception:
            print(f"  MQTT vu: {msg.topic} ({len(msg.payload)} octets)")

    client.on_message = on_probe
    time.sleep(15)
    client.loop_stop()
    client.disconnect()
    print(f"Terminé — {seen} autre(s) message(s) MQTT sur {channel} en {time.time() - t0:.0f} s.")
    print("Si 0 et rien sur le mesh : la gateway !a1d7795c ne relaye pas (firmware / config).")


if __name__ == "__main__":
    main()
