#!/bin/bash
# n8n 전용 DB 계정(nexus_n8n_local). 티켓 표 3개는 읽고 쓰며(재현 패키지의 local-ticket-db-grants 와 같음), users 표는 잠금 관련 컬럼만 다룬다.
set -euo pipefail
mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --port=3307 <<SQL
CREATE USER IF NOT EXISTS 'nexus_n8n_local'@'%' IDENTIFIED BY '${NEXUS_N8N_LOCAL_DB_PASSWORD}';
GRANT SELECT, INSERT, UPDATE ON \`nexus\`.security_incident_tickets TO 'nexus_n8n_local'@'%';
GRANT SELECT, INSERT, UPDATE ON \`nexus\`.security_incident_alerts  TO 'nexus_n8n_local'@'%';
GRANT SELECT, INSERT, UPDATE ON \`nexus\`.security_discord_rate_limit TO 'nexus_n8n_local'@'%';
-- 자동 계정 조치(잠금·강제 로그아웃)용: users 표에서 필요한 컬럼만 읽고, 잠금·세션 컬럼만 고칠 수 있다
GRANT SELECT (username, pinned, locked_until, session_version) ON \`nexus\`.users TO 'nexus_n8n_local'@'%';
GRANT UPDATE (locked_until, session_version) ON \`nexus\`.users TO 'nexus_n8n_local'@'%';
FLUSH PRIVILEGES;
SQL
