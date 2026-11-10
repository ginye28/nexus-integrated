#!/bin/sh
# DB 가 준비될 때까지 기다린 뒤, 비어 있으면 시험 데이터를 넣고 포털을 실행한다.
set -e
python - <<'PY'
import os, time, pymysql
for i in range(90):
    try:
        pymysql.connect(host=os.environ["DB_HOST"], port=int(os.environ["DB_PORT"]), user="root",
                        password=os.environ["MYSQL_ROOT_PASSWORD"], database=os.environ.get("DB_NAME", "nexus")).close()
        break
    except Exception:
        time.sleep(2)
else:
    raise SystemExit("MySQL 에 연결하지 못했습니다")
PY
if [ ! -f /app/instance/.seeded ]; then
  echo "[entrypoint] 시험 데이터 적재(seed)"
  python scripts/seed.py --db "${DB_NAME:-nexus}"
  python scripts/create_team_admins.py --db "${DB_NAME:-nexus}" || true
  touch /app/instance/.seeded
fi
# Wazuh 에이전트: 매니저(에뮬레이션이라 기동이 느림)가 준비될 때까지 등록을 재시도한 뒤 시작 (실패해도 포털은 계속 기동)
( python /opt/wazuh-agent-setup.py
  for i in $(seq 1 40); do
    /var/ossec/bin/agent-auth -m wazuh-manager >>/tmp/wazuh-auth.log 2>&1 && break
    sleep 15
  done
  /var/ossec/bin/wazuh-control start >/tmp/wazuh-start.log 2>&1 ) &
exec python run.py --host 0.0.0.0 --port 5070
