# Graylog → n8n Webhook 입력 형식

작성: 진혜정 (D 자동화) / 받는 사람: 김태빈 (C 탐지)
기준: 김태빈 님의 `docs/SECURITY_LOG_SPEC.md` v1.1 (§6 canonical envelope, §7 mock payload). 이 문서는 n8n이 그것을 어떻게 받아 처리하는지 정리한 것입니다.

## 1. 전송 방식
- 방식: HTTP POST, `Content-Type: application/json`
- 주소(시험): `http://<n8n 주소>:5678/webhook-test/nexus-alert`
- 주소(운영): `http://<n8n 주소>:5678/webhook/nexus-alert`
- 헤더: `X-Webhook-Token: <.env 의 WEBHOOK_TOKEN>` (토큰은 문서·채팅에 쓰지 않고 따로 전달)
- Graylog가 헤더를 못 붙이면 `.env`의 `ALLOW_QUERY_TOKEN=1`로 주소의 `?token=<토큰>`도 받을 수 있음(기본 꺼짐, 마지막 수단). 연결 방법은 `docs/graylog-n8n-connect.md`
- 규칙(R1~R12) Event가 생성될 때마다 1건씩 보냅니다.

### 응답 코드
| 상황 | HTTP | 본문 |
|---|---|---|
| 토큰 일치 (접수됨, 처리는 이어서 진행) | 200 | `{"status":"accepted"}` |
| 토큰 틀림 또는 없음 | 401 | `{"status":"unauthorized"}` |

200은 "접수"이며 대응 완료를 뜻하지 않습니다.

## 2. 본문 형식
**표준(권장)**: `SECURITY_LOG_SPEC.md` §6의 envelope (`schema_version` 1.1, `action_level`, `rule`, `alert`, `event`).
n8n이 읽는 값:

| 값 | 쓰임 |
|---|---|
| `rule.id` (R1~R12) | 규칙별 대응 분기 |
| `rule.display_name` | 알림·티켓 제목 (`[NEXUS][R#]` 접두어는 떼고 사용) |
| `action_level` | observe / alert / contain. observe는 Discord 없이 티켓만 |
| `alert.id` | **중복 방지 키**. 같은 값이 다시 오면 한 번만 처리하고 무시 |
| `alert.timestamp`, `alert.priority` | 시각, 심각도(1~5) |
| `event.src_ip` | 티켓을 나누는 기준(출발지). 없거나 `-`이면 `event.user` 기준 |
| `event.user`, `event.decision`, `event.tool_name`, `event.request_id`, `event.session_id`, `event.caller_service`, `event.severity` | 알림 문구·티켓 기록 |
| `event.evidence.*` | 건수(`event_count`, `failed_attempts`, `denied_calls`, `retry_count`, `distinct_users` 중 먼저 있는 값) |

본문·토큰 원문은 받지 않습니다(명세의 비밀값 정책 그대로). 원본 backlog나 prompt/게시글 본문이 섞여 오면 n8n 연결 전에 Graylog 쪽에서 막아야 합니다.

**이전 형식(호환용)**: `rule_id`, `rule_name`, `severity`, `src_ip`, `user`, `first_seen`, `last_seen`, `count`, `graylog_event_id`를 평평하게 담은 JSON도 받습니다. `scripts/test_webhook.sh`가 이 형식을 씁니다.

## 3. 규칙별로 n8n이 하는 일

티켓 유형은 4가지입니다. 탐지로 생기는 3가지는 이상 징후 경보 < 차단 조치 < 침해 인시던트 순으로 승격되고, 4번째 **오탐·해제 요청**은 사람이 상황판에서 등록해 따로 관리합니다. 같은 출발지의 알림은 새 티켓이 아니라 갱신하고, 유형은 더 심각한 쪽으로만 올립니다.

| 규칙 | action_level | 대응(예정) | 티켓 유형 |
|---|---|---|---|
| R1 계정 침해 의심 | contain | 계정 잠금, Discord, 티켓 | 차단 조치 |
| R2 직접 인젝션 차단 | alert | Discord, 티켓 | 이상 징후 경보 |
| R3 AI Tool 권한 위반 | contain | 세션 종료, AI Tool 제한, Discord, 티켓 | 침해 인시던트 |
| R4 비정상 내부 API 호출 | contain | `decision=ALLOW`(방어 전 성공): 내부 API 토큰 폐기, Discord, 티켓 → 침해 인시던트 / `DENY`(방어 후 차단): Discord, 티켓 → 차단 조치 | 위 참고 |
| R5 계정 스프레이, R6 잠금 후 재시도, R8 404 스캔, R9 관리자 접근 거부, R10 기밀 접근 거부 | alert | Discord, 티켓 | 이상 징후 경보 |
| R7 심야 로그인 | observe | 티켓만(Discord 없음) | 이상 징후 경보 |
| R11 AI Tool 반복 위반, R12 콘텐츠 기반 위험 Tool 호출 | contain | R3과 동일(세션 종료, AI Tool 제한, Discord, 티켓) | 침해 인시던트 |

위 표의 R5~R12 대응은 진혜정이 `action_level`과 명세의 우선순위를 보고 정한 **초안**입니다. 실제 대응(계정 잠금·세션 종료 등)은 아직 "대응 자리"만 있고 구현 전입니다(홍주형 님의 DB 정보 필요).

티켓 필드: `id, src_ip, type, stage, severity, signals, rules, users, count, first_seen, last_seen, status, responses`. `stage`는 이상 징후 경보 = 접수 → 모니터링 → 승격 / 차단 조치·침해 인시던트 = 접수 → 조치 중 → 해제·복구 → 종료 / 오탐·해제 요청 = 요청 → 종료(승인자 `approver`).

## 3-1. 상황판용 API (진혜정 내부용)
모두 `X-Webhook-Token` 헤더 필요. 토큰이 없거나 틀리면 401.

| 주소 | 방식 | 설명 |
|---|---|---|
| `/webhook/nexus-tickets` | GET | 티켓 목록, 요약, 화이트리스트, 최근 건너뛴 알림 |
| `/webhook/nexus-ticket-action` | POST | 아래 동작 수행 |

`nexus-ticket-action` 본문 (`action` 값별):
- `close` : `{"action":"close","ticket_id":"NX-0001","note":"..."}` → 티켓 종료(조치 완료)
- `false_positive` : `{"action":"false_positive","ticket_id":"NX-0001","whitelist":true}` → 오탐으로 종료, `whitelist`가 true면 그 IP를 화이트리스트에 추가
- `whitelist_add` / `whitelist_remove` : `{"action":"whitelist_add","ip":"10.0.0.5"}`
- `request_release` : `{"action":"request_release","user":"kim","ticket_id":"NX-0001","reason":"..."}` → 4번째 티켓 유형 **오탐·해제 요청** 생성(`ticket_id`는 선택, 연결할 티켓)
- `release` : `{"action":"release","ticket_id":"NX-0001","user":"kim"}` → 계정 잠금 해제(`locked_until = NULL`). 오탐·해제 요청 티켓에 쓰면 성공 시 그 티켓이 "해제 승인"으로 종료됨
- `lock` : `{"action":"lock","ticket_id":"NX-0001","user":"hongjh"}` → 사람이 승인하는 잠금(고정 계정 포함, `LOCK_MINUTES` 동안)
  - `user`는 그 티켓에 연결된 계정만 가능(아니면 400 `user_not_in_ticket`), 계정 이름 형식 검사, `RESPONSE_MODE`가 `live`일 때만 DB 실행(기본 dry-run은 기록만, 요청 헤더 `X-Response-Mode`가 우선). 결과는 티켓의 대응 기록에 남고 상황판에서 버튼으로 실행
- 응답 코드: 200 성공, 400 잘못된 요청, 404 대상 없음, 409 이미 종료됨, 502 DB 조치 실패

**화이트리스트**: 해당 출발지 IP의 알림은 티켓·Discord·대응 없이 건너뜁니다(최근 50건은 기록). 설정 방법은 `.env`의 `WHITELIST_IPS`(쉼표 구분, 재시작 필요) 또는 상황판에서 추가·해제(즉시 적용, 되돌릴 수 있음).
종료된 티켓의 IP에서 다시 알림이 오면 새 티켓 번호로 만들고, 종료된 티켓은 기록으로 남습니다.

## 3-2. 대응 실행 (계정 잠금·세션 종료)

| 규칙 | 대응 | 바꾸는 DB 열 | 상태 |
|---|---|---|---|
| R1 | 계정 잠금 | `users.locked_until` (15분, `LOCK_MINUTES`) | 구현, **시험용 DB로 검증** |
| R3, R11, R12 | 세션 종료(강제 로그아웃) | `users.session_version` + 1 | 구현, 시험용 DB로 검증 |
| R3, R11, R12 | AI Tool 제한 | AI 제한 열(미정) | AI 연동 단계에서 구현 |
| R4 | 내부 API 토큰 폐기 | (미정) | AI 연동 단계에서 구현 |

- **실행 방식**: 기본은 `dry-run`(DB를 바꾸지 않고 "하려던 조치"만 티켓에 기록). `.env`의 `RESPONSE_MODE=live`로 바꾸면 실제 실행. 요청 헤더 `X-Response-Mode: live|dry-run`이 있으면 그 값이 우선이고, 시험 헤더 `X-Dry-Run: 1`만 있으면 dry-run입니다.
- **안전장치**: SQL은 고정 문장에 값을 자리표시자로만 넣고, 계정 이름은 영문자로 시작하는 형식만 허용합니다. `pinned = 1`(최상위 고정) 계정은 잠그지 않고 세션 종료만 하며(결과 "일부 적용"), 잠금은 사람이 승인합니다(홍주형 님 권장안, 10/20 확정). 시각은 SQL의 `NOW()`(DB 시계, UTC)만 씁니다. **보호 계정**(`.env`의 `PROTECTED_USERS`, 쉼표 구분. 시험·강사님 계정 등)은 고정 계정과 같이 R1이 와도 잠그지 않고 세션 종료만 하며(결과 "일부 적용"), 잠금은 상황판의 "잠금(승인)"으로 사람이 합니다. 목록은 기본 비어 있고 바꾸려면 `.env` 수정 후 `docker compose up -d n8n`. DB 계정은 `locked_until`·`session_version` 두 열만 수정할 수 있게 제한합니다(`docs/db-columns-for-n8n.md`).
- **결과 기록**: 조치 뒤 읽기 전용 조회로 실제 상태를 확인하고 결과(적용, 변경 없음, 건너뜀, 오류, 미실행)를 티켓의 `responses`에 남깁니다. 상황판의 "대응 기록" 열에 보입니다. 실행했을 때만 Discord로 결과를 한 번 더 알립니다.
- **현재 연결**: n8n 자격 증명 "NEXUS 포털 DB (n8n 전용 계정)"는 `scripts/use_db.sh`로 바꿉니다. `portal`은 실제 포털 DB(10/20 연결, `jinhj` 시험 계정으로 잠금·해제·세션 종료 확인), `test`는 시험용 DB(`docker compose --profile test up -d nexus-test-db`)입니다. 기본 `RESPONSE_MODE=dry-run`이라 실제 DB는 `live`로 지정할 때만 바뀝니다.

## 4. 시험 방법
- 표준 형식 mock(명세 §7의 R1~R12): `node scripts/send_mock.js R3` / `node scripts/send_mock.js all`
  - 기본은 **시험 모드**(`X-Dry-Run: 1` 헤더)라 Discord로는 보내지 않고 티켓·대응 경로만 탑니다. Discord까지 보내려면 `--discord`를 붙입니다.
  - 보낼 때마다 `alert.id`를 새로 붙이므로 중복 방지에 걸리지 않습니다.
- 대응을 실제로 실행: `node scripts/send_mock.js R1 --live` (연결된 DB가 바뀜. 시험용 DB에서만 하세요)
- 이전 형식: `scripts/test_webhook.sh R1 prod`

## 5. 확인이 필요한 점 (김태빈님께)
- Graylog의 HTTP 알림에서 **`X-Webhook-Token` 헤더를 붙일 수 있는지**(설치 버전·에디션 확인). 안 되면 대안(주소의 쿼리 값 등)을 같이 정해야 합니다. 토큰이 없으면 n8n이 401로 거부합니다.
- 명세 §6대로 custom HTTP body template을 쓸 수 있는지. 안 되면 기본 payload(backlog 0)를 n8n이 변환해야 하고, 그 경우 실제 payload 한 건을 공유해 주세요.
- n8n 최종 주소(현재 진혜정 맥북, 설계상 172.16.50.30)는 이시헌 님과 연결표 기준으로 확정 후 알려 드리겠습니다.
