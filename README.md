# NEXUS WORK — 진혜정 개인 포트폴리오 저장소

> 사내 업무 포털(그룹웨어·ERP·AI 챗봇)을 공격에서 지키는 **탐지 → 자동 대응(SOAR) → AI 판정(AI-XDR)** 팀 프로젝트(4조)를, 노트북 한 대의 Docker 로 **혼자 설치·실행·재현·수정**할 수 있게 만든 통합 환경입니다.

| | |
|---|---|
| **팀 원본 저장소** | https://github.com/stulss/nexus-work (포털 코드·재현 패키지. 이 저장소는 설치 때 이 주소를 내려받아 씁니다) |
| **팀원** | 진혜정(팀장) · 홍주형(부팀장) · 이시헌 · 김태빈 |
| **프로젝트 기간** | 2026-10-19 ~ 2026-11-06 (활동일지 기준, 리허설 11/5, 본발표 11/6) · 통합 환경 정리 11/9~11/10 |
| **본인 역할** | **진혜정 — 팀장 · 역할 D (자동화·상황판)**: n8n 자동 대응 워크플로(계정 잠금·강제 로그아웃·티켓 4종·화이트리스트·해제 절차), 공격 시연(Kali), 통합 점검 주관, 기획서·문서 정리, AI-XDR 판정·시간대 정책(Time-Gate) 설계와 Groq 모델 교체 |
| **이 저장소에서 한 일** | 팀 4명의 구성(포털·pfSense·Graylog·Wazuh·Suricata·ntopng·n8n·AI-XDR·Discord)을 한 대에서 같은 흐름으로 돌리는 Docker 환경, 시나리오 재현·실측 스크립트, 점검·시험 스크립트, 유지보수 가이드 |

- 팀원별 상세 기여와 근거 → [docs/CONTRIBUTIONS.md](docs/CONTRIBUTIONS.md)
- 시나리오 재현 절차·실측 결과 → [docs/SCENARIOS.md](docs/SCENARIOS.md)
- 문제 → 원인 → 해결, 개선점, 느낀 점 → [docs/IMPROVEMENTS.md](docs/IMPROVEMENTS.md)
- 이력서 프로젝트 항목·자기소개서 문단 → [docs/portfolio/](docs/portfolio/)
- 팀원 코드·자료는 출처(이름)를 표시했고, `config/`·`portal/` 안의 파일은 팀 저장소의 것입니다.
- 이 저장소에는 비밀번호·API 키·토큰·웹훅 주소가 없습니다. 실제 값은 `.env`(커밋 제외)에만 있고, 항목 목록은 [.env.example](.env.example) 입니다.

## 처음부터 설치하기 (새 PC, 약 15분)

**준비물**: macOS 또는 Linux(Windows 는 WSL2 + Docker Desktop), Docker Desktop(또는 Docker Engine + Compose v2), `git`, `python3`(3.9+), `curl`. Docker 에 **메모리 8GB 이상**을 주세요(Graylog·OpenSearch·Wazuh 때문). 빈 포트: 5070, 5678, 9000, 3307, 3000, 8080, 2200.

```bash
git clone https://github.com/ginye28/nexus-integrated.git
cd nexus-integrated
./scripts/up.sh          # ① 팀 포털 코드 내려받기 ② .env 생성(비밀값 무작위) ③ 이미지 빌드·기동 ④ Graylog 규칙·n8n 워크플로 자동 적용 (처음 5~10분)
./scripts/info.sh        # 접속 주소와 계정 보기 (비밀번호는 .env 에서 읽어 화면에만 표시)
./scripts/verify.sh      # 설치 확인: 응답 6개 + 공격 1회가 알림 DB 에 도착하는지 → "통과 7 / 실패 0"
```

**Groq API 키(무료, https://console.groq.com)를 `.env` 의 `GROQ_API_KEY` 에 넣으면** AI 판정과 AI 시나리오가 완전히 동작합니다. 키가 없어도 설치·`verify.sh`·R1·R2·R8·스캐너·디코이 시나리오는 되지만, AI-XDR 은 `REVIEW_REQUIRED`(판정 불가)로 나오고 **R3·R11·R12(AI 에이전트 도구 거부)와 `r3 --approve` 시나리오는 재현되지 않습니다**(깨끗한 설치로 확인). Discord 알림은 `DISCORD_WEBHOOK_URL`(선택). 한 줄만 고친 뒤 `docker compose up -d portal` 과 `python3 n8n/bootstrap_n8n.py`.
**.env 를 파일째 덮어쓰지 마세요**(DB·Graylog 비밀번호가 사라집니다).

### 구성별 실행·주소·기본 설정

| 구성 | 실행 명령 | 접속 주소·포트 | 기본 설정(자동 적용) |
|---|---|---|---|
| 서버(웹·DB) | `docker compose up -d mysql portal` | 포털 `http://127.0.0.1:5070` (경계 장비 경유), DB `127.0.0.1:3307` | 시드 계정·테이블은 `portal/db/init.sh`, 비밀번호는 `.env` |
| pfSense 역할(경계) | `docker compose up -d edge pfsense-ui` | HAProxy 통계 `:2200`, pfSense 스타일 화면 `:8080` | 차단 순서 GeoBlock → 위협목록 → 포털 피드 → 자동차단, 설정은 `edge/`·`pfsense-ui/config.json` |
| 진짜 pfSense (선택) | `pfsense-vm/run-restored.sh` | `https://127.0.0.1:8443` | QEMU 에뮬레이션, 설치·설정 복원 방법은 [pfsense-vm/README.md](pfsense-vm/README.md) (Docker 와 미연결) |
| Graylog2 | `docker compose up -d mongo opensearch graylog` → `python3 graylog/import_graylog.py` | `http://127.0.0.1:9000` (admin / `.env`) | GELF·Syslog 입력, Stream 3개, 탐지 규칙 R1~R12, n8n 알림 — 원본 `config/graylog/` |
| Wazuh | `docker compose up -d wazuh-manager` | 매니저 컨테이너(에이전트는 포털 컨테이너 안) | FIM 소스·업로드 폴더, 경보 → Graylog UDP 5140 — `wazuh/ossec.conf`, `config/wazuh/` |
| Suricata / ntopng | `docker compose up -d suricata ntopng` | ntopng `http://127.0.0.1:3000` | ET Open 규칙, 경보 → Graylog syslog 1514 |
| n8n | `docker compose up -d n8n` → `python3 n8n/bootstrap_n8n.py` | `http://127.0.0.1:5678` (`.env` 의 계정) | 소유자·연결 정보·v3 워크플로 가져오기+게시, 웹훅 `/webhook/nexus-alert` (헤더 `x-webhook-token`) — 원본 `config/n8n/` |
| 공격 PC | `./scripts/attack.sh r8 \| r1 \| r2 \| r3 \| scan` | 192.168.3.11 컨테이너 | Kali 대신 파이썬 컨테이너(출처 IP 분리용) |

종료·초기화: `./scripts/down.sh`(데이터 유지) / `./scripts/reset.sh`(전부 삭제).

### 직접 확인해 보기 (선생님 확인용 1~2개 시나리오)

```bash
python3 scripts/scenario.py r8                # 404 경로 스캔 → 탐지 → n8n → AI-XDR 평가 → 복구  (약 2분)
python3 scripts/scenario.py r3 --approve      # AI 기밀 문서 요청 → 탐지 → AI 판정 → 관리자 승인 → 공격 PC 403 차단 → 복구 (약 3분)
```

### 혼자서는 하지 않은 것 (예외)

- **R1 의심 계정 잠금(관리자 승인 → 계정 잠금)**: 팀원(관리자) 협업이 필요한 승인 경로라 이 저장소에서는 SQL·권한까지만 확인했습니다.
- **서버 3대(.10/.14/.15) 분리 배치, 실제 Kali·Windows 에이전트**: 팀 장비가 필요해 한 대의 컨테이너로 대체했습니다(Wazuh 윈도우 이벤트는 제외).
- **진짜 pfSense 와 Docker 연결·패키지 동작**: VM 은 따로 부팅·설정 복원까지만 확인했습니다.

---

## 시작하기

```bash
./scripts/up.sh        # 처음에는 5~10분 (이미지 내려받기·빌드). 끝나면 접속 정보가 출력됩니다
./scripts/info.sh      # 접속 주소·계정 다시 보기
```

| 서비스 | 주소 |
|---|---|
| 포털 (경계 장비 경유) | http://127.0.0.1:5070 |
| AI-XDR 대시보드 | http://127.0.0.1:5070/admin/xdr (admin 로그인) |
| Graylog | http://127.0.0.1:9000 |
| n8n | http://127.0.0.1:5678 |

계정·비밀번호는 `.env`(처음 실행 때 이 노트북에서 무작위 생성)에 있고 `./scripts/info.sh`로 볼 수 있습니다.

## 시연하기 (팀 발표와 같은 순서)

```bash
./scripts/attack.sh r8    # 404 경로 스캔 35회        → Graylog R8 경보 → n8n 티켓
./scripts/attack.sh r1    # han 로그인 6회 실패(잠금)  → R1(계정 침해 의심)·R6(잠금 후 재시도)
./scripts/attack.sh r2    # 챗봇 프롬프트 인젝션       → R2 (포털이 즉시 차단 403)
./scripts/attack.sh r3    # 기밀 문서 AI 요청 3회      → R3·R11 (Groq 키 필요)
./scripts/attack.sh scan  # 스캐너 UA(Nikto·sqlmap·Nmap)  → Suricata 경보
```

1. 공격이 포털 로그(GELF) → Graylog 로 들어가고 규칙 경보가 생깁니다(약 15~30초).
2. n8n 이 경보를 받아 **출발지 IP별 티켓**에 연결하고, 1분마다 모인 이벤트를 AI-XDR 로 보냅니다.
3. `/admin/xdr` 에서 위험도·신뢰도·근거·권고를 보고 **관리자가 승인**하면 IP 가 차단 목록에 올라갑니다.
4. edge 가 5초 안에 목록을 받아 해당 IP(공격 PC)를 막습니다 → 다시 공격 요청을 보내면 403.
   (`blocked_ips` 표의 `blocked_until` 이 지나면 피드에서 빠져 자동 해제)

## 팀 구성과 이 환경의 대응

| 팀이 만든 것 | 이 환경에서 | 확인 방법 |
|---|---|---|
| 포털(Flask)·MySQL·AI-XDR | 그대로(팀 저장소 코드) | http://127.0.0.1:5070 , `/admin/xdr` |
| pfSense: WAN 5070 → HAProxy → 포털, 차단 순서(GeoBlock → 위협목록 → 포털 피드 → 자동차단) | `edge` 컨테이너(HAProxy). **진짜 pfSense 는 아님**(x86 FreeBSD 라 애플 칩에 설치 불가). 이시헌 님 설정 XML 에서 규칙·NAT·별칭·로그 대상을 읽어 반영 | HAProxy 통계 http://127.0.0.1:2200 |
| pfSense 관리 화면 | `pfsense-ui` 컨테이너가 **pfSense 스타일 읽기 전용 화면**을 제공(대시보드·서비스 상태·방화벽 규칙·NAT·별칭·차단 목록·Suricata 경보). 규칙·NAT·별칭은 이시헌 님 설정(비밀값 제거본), 차단 목록·경보·서비스 상태는 실제 값. 설정 변경은 불가 | http://127.0.0.1:8080 |
| pfBlockerNG GeoBlock(중국·러시아·북한)·PRI1 위협 목록 | 같은 출처(ipdeny, abuse.ch, Emerging Threats 등)에서 받아 적용(GeoBlock 하루 1번, 위협목록 1시간마다). PRI1 은 원본이 LAN 아웃바운드용이라 여기서는 들어오는 요청에 적용 | `docker logs nexus-edge` |
| Suricata(WAN, 탐지 전용, ET Open) | `suricata` 컨테이너가 edge 와 같은 네트워크에서 패킷 감시, 경보를 syslog(local1.notice)로 Graylog 1514 에 전송 | `./scripts/attack.sh scan` → Graylog 검색 `suricata` |
| ntopng(WAN) | `ntopng` 컨테이너(로그인 없음) | http://127.0.0.1:3000 |
| Wazuh(FIM) | 매니저 컨테이너 + 포털 컨테이너 안 에이전트. 소스·업로드 폴더 변경(rule 550/553/554)을 Graylog 5140 으로 전달 | 업로드 폴더에 파일 만들고 Graylog 검색 `ossec` |
| Graylog R1~R12 → n8n | 팀 재현 패키지 + 규칙별 HTTP 알림 | http://127.0.0.1:9000 |
| n8n v3 워크플로 | 팀 템플릿 그대로(+아래 변경) | http://127.0.0.1:5678 |
| Discord 알림 | AI-XDR 평가 결과를 `.env` 의 `DISCORD_WEBHOOK_URL` 채널에 **임베드 카드**로 전송. 색 띠는 심각도별: 🔴 악성/위험도 80↑, 🟠 의심/50↑, 🟡 20↑, 🟢 정상/낮음, ⚪ 검토 필요 | 공격 후 2~3분 안에 채널 확인 |
| 디코이(허니팟) Discord 알림 | 포털이 같은 웹훅으로 직접 전송 | 미끼 경로(예: `/.env`) 접근 |

## 꼭 알아둘 점

- **진짜 pfSense 는 아닙니다.** 대신 pfSense 스타일 읽기 전용 화면(8080)을 만들었습니다. 같은 동작(전달·차단·로그)을 컨테이너로 재현한 것입니다. 이시헌 님 XML 은 `_private/` 에 보관만 합니다.
- **Groq 키**: `.env` 의 `GROQ_API_KEY` 가 있어야 AI 판정과 R3·R11·R12(AI Tool 거부)가 동작합니다. 키를 바꿀 때는 그 한 줄만 고치세요(파일 전체를 덮어쓰면 DB·Graylog 비밀번호가 사라집니다).
- **AI-XDR 차단 모드** `NEXUS_XDR_MODE=demo`: 관리자가 승인하면 실제로 차단합니다(자동 차단은 꺼져 있음). `safe` 는 기록만.
- **n8n 자동 조치(팀 운영과 같게 켜 둠)**: 템플릿에서 꺼져 있던 노드 5개(Discord 알림, DB 조치 실행, 대응 결과 알림, 계정 조치 실행, R5/R6/R8 IP 차단 API)와 '안전 설정(수신)' 스위치(live·Discord·IP 차단)를 `n8n/bootstrap_n8n.py` 가 켭니다. 끄려면 `.env` 에 `N8N_AUTO_ACTIONS=0` 을 적고 `python3 n8n/bootstrap_n8n.py` 를 다시 실행하세요.
  - R5/R6/R8 자동 IP 차단은 15분간 차단하며, 템플릿의 예외 목록(127.0.0.1, 192.168.3.10·.11·.14·.15)은 차단하지 않습니다. **시연용 공격 PC(192.168.3.11)도 예외 목록에 있어서 자동 차단되지 않고**, 관리자 승인(`/admin/xdr`)으로만 차단됩니다.
  - 계정 잠금·강제 로그아웃은 `users` 표의 `locked_until`·`session_version` 컬럼만 고칠 수 있는 좁은 DB 권한으로 동작합니다(비밀번호 컬럼은 읽지 못함). 고정 계정(`pinned`)은 잠기지 않습니다.
  - 켠 뒤 확인: R8 → 알림·Discord 전송, 예외 목록 밖 IP 의 R8 알림 → 15분 차단, R3 → 강제 로그아웃(`session_version` 증가)+결과 알림. 관리자 승인이 필요한 R1 의심 계정 잠금 경로는 실행해 보지 않았습니다.
- **n8n 변경점(팀 템플릿 대비)**: 빠진 `webhookId` 보충, 포털·DB 주소를 컨테이너 이름으로 변경, MySQL 노드 자동 재시도(경보가 동시에 올 때 교착 방지), Discord 분기 활성화와 임베드 형식.
- **공격 PC**: Kali 대신 같은 대역(192.168.3.11)의 파이썬 컨테이너(출처 IP 가 분리돼야 IP 차단을 시연할 수 있음).
- **Wazuh 매니저**는 공식 이미지가 x86 전용이라 에뮬레이션으로 실행됩니다(처음 1~2분 느림, 메모리 약 1GB). 매니저를 다시 만들면 포털을 재시작해 에이전트를 다시 등록해야 합니다.
- Wazuh 인덱서·대시보드, pfSense VPN·DHCP 등은 포함하지 않았습니다.

## 폴더

```
compose.yaml            전체 구성 (mysql, portal, edge, attacker, mongo, opensearch, graylog, n8n)
portal/                 팀 저장소 stulss/nexus-work (포털 코드, repro-package 포함) — 수정하지 않음(db/init.sh 실행 권한만 부여)
edge/                   pfSense 대체 장비 설정 (haproxy.cfg, 차단 목록·GeoBlock 갱신 스크립트)
suricata/ ntopng/ wazuh/   각 컨테이너 실행 스크립트·설정
graylog/import_graylog.py   입력·Stream·R1~R12·n8n 알림 적용(여러 번 실행해도 안전)
n8n/bootstrap_n8n.py        소유자·연결 정보·워크플로 가져오기와 게시
attacker/attack.py          시연용 공격 스크립트
scripts/                up.sh down.sh reset.sh info.sh attack.sh setup_env.py
_private/               pfSense 설정 백업(관리자 해시·인증서 포함) — 공유·커밋 금지
.env                    비밀값 (공유·커밋 금지)
```

## 자주 쓰는 명령

```bash
./scripts/down.sh                       # 멈추기(데이터 유지)
./scripts/up.sh                         # 다시 켜기 (이미 있으면 빠르게 복구)
./scripts/reset.sh                      # 모든 데이터 삭제 후 초기화
docker compose logs -f portal edge n8n  # 로그 보기
docker compose exec mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --port=3307 nexus   # DB 확인(.env 에서 로드 후)
```

## 문제가 생기면

- **Graylog 가 안 열림**: 처음에는 1~2분 걸립니다. `docker compose logs graylog`.
- **n8n 웹훅이 404**: 게시된 워크플로의 웹훅은 기동 후 20~40초 뒤에 등록됩니다.
- **포트 충돌**(5070·5678·9000·3307): 같은 포트를 쓰는 다른 프로그램(예전 실습 컨테이너 등)을 끄세요.
- 이전 실습 컨테이너(`gl-graylog`, `nexus-n8n` 등)는 건드리지 않았고 이름·볼륨이 겹치지 않습니다.

## 유지보수 가이드

**어디를 고치면 되나**

| 바꾸고 싶은 것 | 파일 |
|---|---|
| 포털·AI-XDR 동작(팀 코드) | `portal/` (팀 저장소 clone, 아래 "포털 코드 변경 올리기" 참고) → `docker compose build portal && docker compose up -d portal` |
| 경계 장비 차단 순서·포트 | `edge/haproxy.cfg`, `edge/*.sh` → `docker compose up -d --build edge` |
| Graylog 탐지 규칙·알림 연결 | `graylog/import_graylog.py` (규칙 원본은 `portal/repro-package/.../graylog`) → `python3 graylog/import_graylog.py` |
| n8n 워크플로 | 원본은 `portal/repro-package/.../n8n/*.json`, 연결 정보·주소 치환은 `n8n/bootstrap_n8n.py` → `python3 n8n/bootstrap_n8n.py` |
| pfSense 스타일 화면 | `pfsense-ui/` |
| 진짜 pfSense VM(독립 실행, Docker 와 미연결) | `pfsense-vm/README.md` |

**점검 명령**

```bash
./scripts/verify.sh     # 구성요소 응답 6개 + 공격 1회가 알림 DB 까지 도착하는지 (약 2분)
./scripts/test.sh       # 팀 포털 자동 시험 전체 (약 2분, nexus_test DB 만 사용)
./scripts/unblock.sh    # 관리자 승인으로 차단된 공격 PC(192.168.3.11) 즉시 해제
```

**알려진 점검 결과 (2026-11-10)**: `test.sh` 는 1562개 중 1548개 통과, 14개 실패. 실패는 팀 포털 시험이 최신 코드(예: `/admin/api/incidents-live` 경로 추가, 결재 체인 변경)를 따라가지 못한 것 위주이며 이 통합 환경 때문이 아니다.
다만 `test_n8n_account`(n8n DB 권한 목록)는 이 환경이 `mysql-init/20-n8n-local.sh` 로 로컬 n8n 용 권한을 더 주기 때문에 다를 수 있다.

**포털 코드 변경 올리기 (팀 저장소에 직접 올리지 않기)**

```bash
# 1) 한 번만: 팀 저장소를 개인 계정으로 포크하고 portal/ 이 그 포크를 가리키게 한다
gh repo fork stulss/nexus-work --clone=false
cd portal && git remote rename origin upstream && git remote add origin https://github.com/<내계정>/nexus-work.git
# 2) 변경은 브랜치에서 → 개인 포크로 push
git switch -c my-change && git commit -am "..." && git push -u origin my-change
# 3) 팀 최신 반영: git fetch upstream && git merge upstream/main
```

새 PC 에서 처음부터 받을 때 개인 포크를 쓰려면 `PORTAL_REPO=https://github.com/<내계정>/nexus-work.git ./scripts/up.sh`.
`.env`, `_private/`(pfSense 설정 XML 등), `pfsense-vm/*.qcow2` 는 `.gitignore` 로 제외되어 있다.
