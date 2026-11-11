#!/bin/bash
# 팀 포털의 자동 시험(pytest)을 일회용 컨테이너에서 돌린다. 스택(MySQL)이 떠 있어야 하며 nexus_test DB 만 건드린다.
# 사용: ./scripts/test.sh            (전체, 약 2분)   ./scripts/test.sh tests/test_ai_xdr.py -q   (일부)
cd "$(dirname "$0")/.."
docker run --rm --network nexus-integrated_lan --env-file .env -e DB_HOST=mysql -e DB_PORT=3307 \
  -e PYTHONDONTWRITEBYTECODE=1 -e DB_NAME=nexus_test -e XDR_RESPONSE_MODE=dry-run -e XDR_IP_BLOCK_ENABLED=0 -e XDR_AUTO_ENABLED=0 -v "$PWD/portal":/app:ro -w /app python:3.12-slim sh -c \
  "apt-get update -qq >/dev/null 2>&1; apt-get install -y -qq git >/dev/null 2>&1
   pip install -q -r requirements.txt pytest >/dev/null 2>&1
   cp -r /app /tmp/a && cd /tmp/a && git config --global --add safe.directory '*'
   python -m pytest -q -p no:cacheprovider ${*:-}"
