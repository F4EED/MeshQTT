"""Test downlink protobuf Meshtastic (tout canal actif, sans canal radio « mqtt »).

Downlink protobuf sur le canal choisi — complément au JSON sendtext.

Usage :
  .\\.venv\\Scripts\\python scripts\\mqtt_protobuf_downlink_test.py --text "Test proto"
  .\\.venv\\Scripts\\python scripts\\mqtt_protobuf_downlink_test.py --channel Fr_Balise
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.mqtt_client import mqtt_publish_topics  # noqa: E402
from app.settings import load_settings  # noqa: E402

try:
    from meshtastic import BROADCAST_NUM
    from meshtastic.protobuf import mesh_pb2, mqtt_pb2, portnums_pb2
except ImportError:
    from meshtastic import BROADCAST_NUM, mesh_pb2, mqtt_pb2, portnums_pb2

DEFAULT_GATEWAY = "!ba69d0fc"
DEFAULT_CHANNEL = "D_Ligerien"
VIRTUAL_NODE = 0xADBA3757


def build_envelope(text: str, channel_id: str, virtual_node: int) -> bytes:
    data = mesh_pb2.Data()
    data.portnum = portnums_pb2.TEXT_MESSAGE_APP
    data.payload = text.encode("utf-8")

    mp = mesh_pb2.MeshPacket()
    mp.id = int(time.time() * 1000) & 0xFFFFFFFF
    setattr(mp, "from", virtual_node)
    mp.to = BROADCAST_NUM
    mp.hop_limit = 3
    mp.decoded.CopyFrom(data)

    env = mqtt_pb2.ServiceEnvelope()
    env.packet.CopyFrom(mp)
    env.channel_id = channel_id
    env.gateway_id = f"!{virtual_node:08x}"
    return env.SerializeToString()


def main() -> None:
    parser = argparse.ArgumentParser(description="Downlink protobuf Meshtastic")
    parser.add_argument("--broker", help="IP broker (defaut settings.json)")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--gateway", default=DEFAULT_GATEWAY)
    parser.add_argument("--channel", default=DEFAULT_CHANNEL, help="Nom canal (Fr_Balise, D_Ligerien, …)")
    parser.add_argument("--text", default="Test protobuf MeshQTT")
    args = parser.parse_args()

    settings = load_settings()
    broker = args.broker or settings["mqtt"]["broker"]
    root = settings["mqtt"]["root_topic"]
    gw = args.gateway if args.gateway.startswith("!") else f"!{args.gateway}"

    payload = build_envelope(args.text, args.channel, VIRTUAL_NODE)
    topic = mqtt_publish_topics(root, args.channel, gw)[0]

    print(f"Broker : {broker}:{args.port}")
    print(f"Topic  : {topic}")
    print(f"Canal  : {args.channel}, gateway suffixe {gw}")
    print(f"gateway_id enveloppe : !{VIRTUAL_NODE:08x} (anti-boucle, != {gw})")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(broker, args.port, 60)
    client.publish(topic, payload, qos=1)
    time.sleep(0.5)
    client.disconnect()
    print(f"Publie. Si rien sur le mesh : downlink ON sur {args.channel} + PSK identique à MeshQTT.")


if __name__ == "__main__":
    main()
