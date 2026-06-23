import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.1.66", username="mosquitto", password="mosquitto", timeout=15, look_for_keys=False, allow_agent=False)
_, o, _ = c.exec_command("sudo tail -25 /var/log/mosquitto/mosquitto.log", timeout=20)
print(o.read().decode("utf-8", "replace"))
c.close()
