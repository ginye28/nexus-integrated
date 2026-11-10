#!/bin/sh
# Suricata IDS (pfSense 패키지와 같은 구성): WAN 인터페이스 감시, 탐지 전용(차단 안 함), 규칙은 ET Open.
# edge 컨테이너와 네트워크를 공유하므로 공격 PC → edge 로 들어오는 패킷을 그대로 본다.
set -e
WAN_IF=$(ip -o -4 addr show | awk '/192\.168\.3\./{print $2; exit}')
[ -n "$WAN_IF" ] || WAN_IF=eth0
echo "[suricata] 감시 인터페이스: $WAN_IF"
mkdir -p /var/log/suricata /var/lib/suricata
echo "[suricata] ET Open 규칙 내려받는 중..."
suricata-update --no-test --quiet 2>&1 | tail -3 || echo "[suricata] 규칙 갱신 실패 — 기존 규칙으로 계속"
[ -f /var/lib/suricata/rules/suricata.rules ] || { echo "[suricata] 규칙 파일이 없습니다"; exit 1; }
python3 /opt/forward.py &
exec suricata -c /etc/suricata/suricata.yaml --af-packet="$WAN_IF" -k none -l /var/log/suricata \
  --set vars.address-groups.HOME_NET="[192.168.3.0/24,172.16.50.0/24]"
