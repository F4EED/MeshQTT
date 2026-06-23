"""Vérifie Mosquitto sur le Pi après setup."""
from __future__ import annotations

import sys

import paramiko

HOST = "192.168.1.66"
USER = "mosquitto"
PASSWORD = "mosquitto"

CMDS = [
    "systemctl is-active mosquitto",
    "systemctl is-active meshtastic-mqtt-capture",
    "ss -tlnp | grep 1883 || true",
    "ls -la /var/lib/meshtastic-mqtt-capture/ 2>/dev/null || true",
    "tail -3 /var/lib/meshtastic-mqtt-capture/meshtastic-$(date +%Y%m%d).log 2>/dev/null || echo '(capture vide pour l instant)'",
    "sudo cat /etc/mosquitto/conf.d/meshtastic.conf 2>/dev/null || echo 'conf absente'",
]


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=15, look_for_keys=False, allow_agent=False)
    try:
        for cmd in CMDS:
            print(">>>", cmd)
            _, stdout, stderr = client.exec_command(cmd, timeout=30)
            out = stdout.read().decode("utf-8", "replace").rstrip()
            err = stderr.read().decode("utf-8", "replace").rstrip()
            if out:
                print(out)
            if err:
                print("ERR:", err)
            print("---")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
