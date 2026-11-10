#!/bin/bash
# 시연용 공격 PC(192.168.3.11) 차단을 즉시 풀어 다시 공격 시연을 할 수 있게 한다(edge 는 5초 안에 반영).
cd "$(dirname "$0")/.."; set -a; . ./.env; set +a
docker exec nexus-mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" nexus -e \
  "UPDATE blocked_ips SET blocked_until = NOW() - INTERVAL 1 SECOND WHERE ip_address='192.168.3.11' AND blocked_until > NOW()" 2>/dev/null
sleep 8; echo "공격 PC 차단 해제 요청 완료"
