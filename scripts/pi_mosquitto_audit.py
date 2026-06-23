"""Audit Mosquitto sur le Pi (sudo)."""
from __future__ import annotations

import sys

import paramiko

HOST = "192.168.1.66"
USER = "mosquitto"
PASSWORD = "mosquitto"

CMDS = [
    "dpkg -l | grep -i mosquitto || rpm -qa | grep -i mosquitto || true",
    "which mosquitto mosquitto_passwd 2>/dev/null || true",
    "sudo find /etc -name '*mosquitto*' 2>/dev/null | head -30",
    "sudo ls -la /etc/mosquitto/ 2>/dev/null || true",
    "sudo cat /etc/mosquitto/mosquitto.conf 2>/dev/null || true",
    "sudo ls -la /etc/mosquitto/conf.d/ 2>/dev/null || true",
    "sudo sh -c 'for f in /etc/mosquitto/conf.d/*.conf; do echo === $f ===; cat $f; done' 2>/dev/null || true",
    "sudo systemctl list-unit-files | grep -i mosquitto || true",
    "docker ps -a 2>/dev/null || true",
    "ip -4 addr show | grep inet",
    "sudo ufw status 2>/dev/null || true",
]


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        HOST,
        username=USER,
        password=PASSWORD,
        timeout=15,
        look_for_keys=False,
        allow_agent=False,
    )
    try:
        for cmd in CMDS:
            print(f">>> {cmd}")
            _, stdout, stderr = client.exec_command(cmd, timeout=45)
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
