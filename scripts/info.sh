#!/bin/bash
# 접속 주소와 계정 안내(비밀번호는 .env 에서 읽어 이 화면에만 표시한다)
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
cat <<TXT
==================== NEXUS WORK 통합 환경 ====================
포털(경계 장비 경유)   http://127.0.0.1:5070         ← 팀이 발표에서 쓴 주소(pfSense WAN 5070 에 해당)
  관리자               admin / $SEED_ADMIN_PW
  직원(시연 계정)      kim, han, park / $SEED_KIM_PW
  팀장                 lee, choi / $SEED_LEE_PW
  팀원 관리자          hongjh, leesh, kimtb, jinhj / 1234  (처음 로그인 후 변경)
AI-XDR 대시보드        http://127.0.0.1:5070/admin/xdr  (admin 으로 로그인)
Graylog               http://127.0.0.1:9000         admin / $GRAYLOG_ROOT_PASSWORD
n8n                   http://127.0.0.1:5678         $N8N_OWNER_EMAIL / $N8N_OWNER_PASSWORD
pfSense 스타일 화면    http://127.0.0.1:8080         (읽기 전용: 서비스·방화벽 규칙·NAT·별칭·차단 목록·Suricata 경보)
HAProxy 통계           http://127.0.0.1:2200
ntopng(트래픽 모니터)  http://127.0.0.1:3000         (로그인 없음)
Suricata 경보          Graylog 에서 검색어 suricata (syslog 1514)
Wazuh FIM 경보         Graylog 에서 검색어 ossec (UDP 5140)
공격 시연              ./scripts/attack.sh r8 | r1 | r2 | r3 | scan | all   (공격 PC 192.168.3.11 → 경계 장비 → 포털)
AI 판정(Groq)          .env 의 GROQ_API_KEY 한 줄만 고치고  docker compose up -d portal  (파일 전체를 덮어쓰지 말 것)
Discord 알림           AI-XDR 평가 결과가 DISCORD_WEBHOOK_URL 채널로 전송됨 (주소 바꾸면 python3 n8n/bootstrap_n8n.py 후 docker compose up -d portal)
AI-XDR 동작 모드       NEXUS_XDR_MODE=$NEXUS_XDR_MODE  (demo=관리자 승인 시 실제 IP 차단 / safe=기록만)
==============================================================
TXT
