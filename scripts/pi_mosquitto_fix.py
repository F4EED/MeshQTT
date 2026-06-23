"""Corrige la config Mosquitto sur le Pi et redémarre les services."""
import paramiko

FIX = r"""
sudo tee /etc/mosquitto/conf.d/meshtastic.conf >/dev/null <<'EOF'
# Meshtastic — écoute sur tout le LAN
listener 1883 0.0.0.0
allow_anonymous true
connection_messages true
EOF
sudo systemctl reset-failed mosquitto
sudo systemctl restart mosquitto
sleep 2
sudo systemctl enable meshtastic-mqtt-capture
sudo systemctl restart meshtastic-mqtt-capture
systemctl is-active mosquitto
systemctl is-active meshtastic-mqtt-capture
ss -tlnp | grep 1883 || true
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.1.66", username="mosquitto", password="mosquitto", timeout=15, look_for_keys=False, allow_agent=False)
_, o, e = c.exec_command(FIX, timeout=60)
print(o.read().decode("utf-8", "replace"))
err = e.read().decode("utf-8", "replace")
if err:
    print("ERR:", err)
c.close()
