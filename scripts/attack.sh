#!/bin/bash
# 공격 PC 컨테이너에서 시연용 공격을 보낸다. 사용: scripts/attack.sh r8|r1|r2|r3|all
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
docker compose --profile attack up -d attacker >/dev/null
docker compose exec -T -e SEED_KIM_PW="$SEED_KIM_PW" attacker python /attacks/attack.py "${1:-all}"
