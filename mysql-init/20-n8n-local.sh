#!/bin/bash
# n8n 이 티켓 표 3개만 읽고 쓰는 전용 계정(nexus_n8n_local). 재현 패키지의 local-ticket-db-grants 와 같은 권한이다.
set -euo pipefail
mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --port=3307 <<SQL
CREATE USER IF NOT EXISTS 'nexus_n8n_local'@'%' IDENTIFIED BY '${NEXUS_N8N_LOCAL_DB_PASSWORD}';
GRANT SELECT, INSERT, UPDATE ON \`nexus\`.security_incident_tickets TO 'nexus_n8n_local'@'%';
GRANT SELECT, INSERT, UPDATE ON \`nexus\`.security_incident_alerts  TO 'nexus_n8n_local'@'%';
GRANT SELECT, INSERT, UPDATE ON \`nexus\`.security_discord_rate_limit TO 'nexus_n8n_local'@'%';
FLUSH PRIVILEGES;
SQL
