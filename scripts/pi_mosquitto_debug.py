"""Diagnostique échec Mosquitto sur Pi."""
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.1.66", username="mosquitto", password="mosquitto", timeout=15, look_for_keys=False, allow_agent=False)
cmds = [
    "sudo journalctl -u mosquitto -n 30 --no-pager",
    "sudo cat /etc/mosquitto/mosquitto.conf",
    "dpkg -l | grep mosquitto",
    "ls -la /var/log/mosquitto/ /var/lib/mosquitto/ 2>/dev/null",
]
for cmd in cmds:
    print(">>>", cmd)
    _, o, e = c.exec_command(cmd, timeout=30)
    print(o.read().decode("utf-8", "replace"))
    err = e.read().decode("utf-8", "replace")
    if err:
        print("ERR:", err)
    print("---")
c.close()
