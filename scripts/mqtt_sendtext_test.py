"""Test direct JSON sendtext Meshtastic (downlink mesh via gateway MQTT).

Prérequis sur la gateway WiFi (!ba69d0fc par défaut) :
  - Module MQTT : JSON enabled ON, root msh/EU_868
  - Canal radio nommé « mqtt » (slot 6) avec downlink ON
  - Downlink ON sur le canal cible (Fr_Balise, D_Ligerien, etc.)
  - Index 0–7 identiques entre MeshQTT et la gateway
  - Redémarrage radio après config

Usage :
  .\\.venv\\Scripts\\python scripts\\mqtt_sendtext_test.py
  .\\.venv\\Scripts\\python scripts\\mqtt_sendtext_test.py --channel-name D_Ligerien --text "Hello"
  .\\.venv\\Scripts\\python scripts\\mqtt_sendtext_test.py --channel 0 --text "Hello Fr_Balise"
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.mqtt_client import mqtt_downlink_json_sendtext_topics  # noqa: E402
from app.settings import load_settings  # noqa: E402

DEFAULT_GATEWAY_HEX = "!ba69d0fc"
DEFAULT_CHANNEL_INDEX = 3  # D_Ligerien dans data/settings.json (exemple)


def _channel_index_from_name(settings: dict, name: str) -> int | None:
    for i, ch in enumerate(settings.get("channels", [])):
        if (ch.get("name") or "").strip() == name.strip():
            return i
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Publie un JSON sendtext Meshtastic")
    parser.add_argument("--broker", help="IP broker (défaut : settings.json)")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--gateway", default=DEFAULT_GATEWAY_HEX, help="Node ID gateway (!hex)")
    parser.add_argument(
        "--channel",
        type=int,
        default=None,
        help="Index canal mesh 0-7 (défaut : 3 ou --channel-name)",
    )
    parser.add_argument(
        "--channel-name",
        help="Nom du canal MeshQTT (ex. Fr_Balise, D_Ligerien) — résout l'index",
    )
    parser.add_argument("--text", default="MeshQTT sendtext test")
    parser.add_argument(
        "--to",
        help="Node ID décimal du destinataire (DM) — ex. 2898726677 pour !acc36f15",
    )
    args = parser.parse_args()

    settings = load_settings()
    broker = args.broker or settings["mqtt"]["broker"]
    root = settings["mqtt"]["root_topic"]

    channel_index = args.channel
    if args.channel_name:
        resolved = _channel_index_from_name(settings, args.channel_name)
        if resolved is None:
            print(f"Canal inconnu : {args.channel_name!r}", file=sys.stderr)
            sys.exit(1)
        channel_index = resolved
    if channel_index is None:
        channel_index = DEFAULT_CHANNEL_INDEX

    gw_hex = args.gateway.strip()
    if not gw_hex.startswith("!"):
        gw_hex = f"!{gw_hex}"
    from_id = int(gw_hex[1:], 16)

    body = {
        "from": from_id,
        "type": "sendtext",
        "payload": args.text,
    }
    if args.to:
        body["to"] = int(args.to)
        body["hopLimit"] = 7
    else:
        body["channel"] = channel_index
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    topics = mqtt_downlink_json_sendtext_topics(root)

    ch_name = ""
    channels = settings.get("channels", [])
    if 0 <= channel_index < len(channels):
        ch_name = channels[channel_index].get("name") or ""

    print(f"Broker : {broker}:{args.port}")
    print(f"Gateway from={from_id} ({gw_hex}), canal mesh index={channel_index}" + (f" ({ch_name})" if ch_name else ""))
    print(f"Payload : {body}")
    print("Topics :")
    for t in topics:
        print(f"  - {t}")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(broker, args.port, 60)
    for topic in topics:
        client.publish(topic, payload, qos=1)
        print(f"Publie -> {topic}")
    time.sleep(0.5)
    client.disconnect()
    print(
        "\n--- Prérequis gateway ---"
        "\n  1) Module MQTT -> JSON enabled = ON"
        "\n  2) Canal RADIO slot 6 nommé « mqtt » -> Downlink ON"
        "\n  3) Canal cible (ex. Fr_Balise, D_Ligerien) -> Downlink ON, même index que MeshQTT"
        "\n  4) Redémarrer la radio après changement de config"
        "\n"
        "\nSi rien sur le mesh : logs série USB [mqtt] sur le Heltec."
        "\nTest protobuf : scripts\\mqtt_protobuf_downlink_test.py --channel <nom>"
    )


if __name__ == "__main__":
    main()
