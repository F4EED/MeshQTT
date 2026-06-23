#!/bin/bash
# Installation Mosquitto pour gateway Meshtastic (Pi 192.168.1.66)
set -euo pipefail

echo "=== Mise à jour paquets ==="
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y mosquitto mosquitto-clients

echo "=== Configuration Meshtastic (LAN, sans auth) ==="
sudo mkdir -p /etc/mosquitto/conf.d /var/log/mosquitto /var/lib/meshtastic-mqtt-capture
sudo chown mosquitto:mosquitto /var/log/mosquitto /var/lib/meshtastic-mqtt-capture

sudo tee /etc/mosquitto/conf.d/meshtastic.conf >/dev/null <<'EOF'
# Meshtastic — écoute sur tout le LAN (complète /etc/mosquitto/mosquitto.conf)
listener 1883 0.0.0.0
allow_anonymous true
connection_messages true
EOF

sudo tee /etc/systemd/system/meshtastic-mqtt-capture.service >/dev/null <<'EOF'
[Unit]
Description=Capture MQTT Meshtastic vers fichiers horodatés
After=mosquitto.service
Requires=mosquitto.service

[Service]
Type=simple
User=mosquitto
Group=mosquitto
ExecStart=/usr/local/bin/meshtastic-mqtt-capture.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo tee /usr/local/bin/meshtastic-mqtt-capture.sh >/dev/null <<'EOF'
#!/bin/bash
# Enregistre tous les topics msh/# en JSON-lines (topic + payload base64 + timestamp)
CAPTURE_DIR="/var/lib/meshtastic-mqtt-capture"
ROOT_TOPIC="msh/#"
mkdir -p "$CAPTURE_DIR"
FILE="$CAPTURE_DIR/meshtastic-$(date +%Y%m%d).log"
exec mosquitto_sub -h 127.0.0.1 -p 1883 -t "$ROOT_TOPIC" -v \
  | while IFS= read -r line; do
      ts=$(date -Iseconds)
      printf '%s\t%s\n' "$ts" "$line" >> "$FILE"
    done
EOF

sudo chmod +x /usr/local/bin/meshtastic-mqtt-capture.sh
sudo chown mosquitto:mosquitto /usr/local/bin/meshtastic-mqtt-capture.sh

# Rotation : garder 14 jours
sudo tee /etc/logrotate.d/meshtastic-mqtt-capture >/dev/null <<'EOF'
/var/lib/meshtastic-mqtt-capture/*.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
    copytruncate
}
EOF

echo "=== Démarrage services ==="
sudo systemctl enable mosquitto meshtastic-mqtt-capture
sudo systemctl restart mosquitto
sleep 2
sudo systemctl restart meshtastic-mqtt-capture

echo "=== État ==="
systemctl is-active mosquitto
systemctl is-active meshtastic-mqtt-capture
ss -tlnp | grep 1883 || true
echo "Capture : /var/lib/meshtastic-mqtt-capture/"
ls -la /var/lib/meshtastic-mqtt-capture/ 2>/dev/null || true
