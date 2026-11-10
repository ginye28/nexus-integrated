#!/usr/bin/env python3
"""Suricata 경보(eve.json)를 pfSense 의 'alertsystemlog' 와 같은 모양의 syslog(local1.notice)로 Graylog 1514/udp 에 보낸다."""
import json, os, socket, time
from datetime import datetime

DEST = (os.environ.get("SYSLOG_HOST", "graylog"), int(os.environ.get("SYSLOG_PORT", "1514")))
PATH = "/var/log/suricata/eve.json"
PRI = 17 * 8 + 5  # local1.notice (pfSense Suricata 설정과 동일)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

while not os.path.exists(PATH):
    time.sleep(1)
f = open(PATH, "r", encoding="utf-8", errors="replace")
f.seek(0, os.SEEK_END)
host = os.environ.get("SYSLOG_HOSTNAME", "pfSense-kry")
while True:
    line = f.readline()
    if not line:
        time.sleep(0.5)
        continue
    try:
        e = json.loads(line)
    except ValueError:
        continue
    if e.get("event_type") != "alert":
        continue
    a = e["alert"]
    msg = (f"[1:{a.get('signature_id')}:{a.get('rev')}] {a.get('signature')} "
           f"[Classification: {a.get('category')}] [Priority: {a.get('severity')}] "
           f"{{{e.get('proto')}}} {e.get('src_ip')}:{e.get('src_port', 0)} -> {e.get('dest_ip')}:{e.get('dest_port', 0)}")
    ts = datetime.now().strftime("%b %d %H:%M:%S")
    try:
        sock.sendto(f"<{PRI}>{ts} {host} suricata[1]: {msg}".encode("utf-8", "replace"), DEST)
    except OSError:
        pass
