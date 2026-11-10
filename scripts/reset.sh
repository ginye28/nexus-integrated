#!/bin/bash
# 모든 데이터(DB·Graylog·n8n)를 지우고 처음 상태로 되돌린다. 비밀값(.env)은 유지된다.
cd "$(dirname "$0")/.."
read -r -p "DB·로그·n8n 데이터를 모두 삭제합니다. 계속할까요? (yes 입력) " a
[ "$a" = yes ] || { echo "취소"; exit 0; }
docker compose --profile attack down -v
echo "삭제 완료. ./scripts/up.sh 로 다시 시작하세요."
