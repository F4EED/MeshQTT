"""Installe et configure Mosquitto sur le Pi via SSH."""
from __future__ import annotations

import sys
from pathlib import Path

import paramiko

HOST = "192.168.1.66"
USER = "mosquitto"
PASSWORD = "mosquitto"
SCRIPT = Path(__file__).resolve().parent / "pi_mosquitto_setup.sh"


def main() -> int:
    content = SCRIPT.read_text(encoding="utf-8").replace("\r\n", "\n")
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
        sftp = client.open_sftp()
        remote = "/tmp/pi_mosquitto_setup.sh"
        with sftp.file(remote, "w") as f:
            f.write(content)
        sftp.chmod(remote, 0o755)
        sftp.close()

        print("=== Exécution setup sur le Pi ===")
        _, stdout, stderr = client.exec_command(f"bash {remote}", timeout=600)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        code = stdout.channel.recv_exit_status()
        if out:
            sys.stdout.buffer.write(out.encode("utf-8", "replace"))
            sys.stdout.buffer.write(b"\n")
        if err:
            sys.stdout.buffer.write(b"STDERR: ")
            sys.stdout.buffer.write(err.encode("utf-8", "replace"))
            sys.stdout.buffer.write(b"\n")
        print("exit code:", code)
        return code
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
