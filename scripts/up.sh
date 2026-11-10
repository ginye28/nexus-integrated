#!/bin/bash
# NEXUS WORK 통합 환경을 한 번에 띄운다. 처음 실행하면 이미지 내려받기·빌드 때문에 5~10분 걸린다.
set -e
cd "$(dirname "$0")/.."

# 1) Docker Desktop 확인(꺼져 있으면 켠다)
if ! docker info >/dev/null 2>&1; then
  if [ "$(uname)" = Darwin ]; then echo "Docker Desktop 을 켭니다..."; open -a Docker; fi
  for i in $(seq 1 60); do docker info >/dev/null 2>&1 && break; sleep 3; done
fi
docker info >/dev/null 2>&1 || { echo "Docker 가 켜지지 않았습니다. Docker Desktop 을 직접 실행한 뒤 다시 시도하세요."; exit 1; }

# 2) 환경 파일(.env: 비밀값은 이 노트북에서 무작위 생성) · 팀 포털 코드
[ -d portal/.git ] || git clone --depth 1 "${PORTAL_REPO:-https://github.com/stulss/nexus-work.git}" portal
python3 scripts/setup_env.py
chmod +x portal/db/init.sh

# 3) 컨테이너 빌드·기동 (공격 PC 는 시연할 때 attack.sh 가 켠다)
docker compose build portal
docker compose up -d || { echo '일부 컨테이너 시작이 늦어 한 번 더 시도합니다...'; sleep 15; docker compose up -d; }

# 4) 준비될 때까지 대기
echo "포털 대기..."
for i in $(seq 1 60); do [ "$(docker inspect -f '{{.State.Health.Status}}' nexus-portal 2>/dev/null)" = healthy ] && break; sleep 4; done
echo "Graylog 대기(1~2분)..."
for i in $(seq 1 90); do curl -s -o /dev/null -f http://127.0.0.1:9000/api/system/lbstatus && break; sleep 4; done

# 5) Graylog 입력·Stream·탐지 규칙·n8n 알림 → n8n 워크플로 연결
python3 graylog/import_graylog.py
python3 n8n/bootstrap_n8n.py

echo
"$(dirname "$0")/info.sh"
