#!/bin/bash
# 컨테이너만 멈춘다(데이터는 그대로). 다시 켜려면 ./scripts/up.sh
cd "$(dirname "$0")/.."
docker compose --profile attack down
