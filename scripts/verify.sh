#!/bin/bash
# 구성요소 응답 + 공격 한 번(R8)이 알림 DB 까지 도착하는지 확인하는 빠른 점검(약 2분). 비밀값은 출력하지 않는다.
cd "$(dirname "$0")/.."
ok=0; bad=0
chk(){ code=$(curl -s -o /dev/null -m 8 -w '%{http_code}' "$2"); if [[ "$code" =~ ^(200|302|303)$ ]]; then echo "OK   $1 ($code)"; ok=$((ok+1)); else echo "FAIL $1 ($code)"; bad=$((bad+1)); fi; }
chk 포털 http://127.0.0.1:5070/login
chk Graylog http://127.0.0.1:9000/api/system/lbstatus
chk n8n http://127.0.0.1:5678/healthz
chk pfSense화면 http://127.0.0.1:8080
chk HAProxy통계 http://127.0.0.1:2200
chk ntopng http://127.0.0.1:3000
set -a; . ./.env; set +a
./scripts/unblock.sh >/dev/null
before=$(docker exec nexus-mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" nexus -N -e "SELECT COUNT(*) FROM security_incident_alerts" 2>/dev/null)
./scripts/attack.sh r8 2>&1 | tail -1
echo "알림 적재 대기(최대 120초)..."
for i in $(seq 1 24); do
  now=$(docker exec nexus-mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" nexus -N -e "SELECT COUNT(*) FROM security_incident_alerts" 2>/dev/null)
  [ "$now" -gt "$before" ] && break; sleep 5
done
if [ "$now" -gt "$before" ]; then echo "OK   공격 → Graylog → n8n → 알림 DB ($before → $now)"; ok=$((ok+1)); else echo "FAIL 알림이 DB 에 도착하지 않음"; bad=$((bad+1)); fi
echo "결과: 통과 $ok / 실패 $bad"; [ $bad -eq 0 ]
