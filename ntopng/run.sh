#!/bin/bash
# WAN(192.168.3.0/24) 인터페이스를 /proc/net/route 에서 찾아 ntopng 를 실행한다.
WAN_IF=$(awk '$2=="0003A8C0"{print $1; exit}' /proc/net/route)
WAN_IF=${WAN_IF:-eth0}
echo "[ntopng] 감시 인터페이스: $WAN_IF"
exec /run.sh -i "$WAN_IF" -w 3000 -n 0 --local-networks "192.168.0.0/16,172.16.0.0/12,10.0.0.0/8" --disable-login 1 --community
