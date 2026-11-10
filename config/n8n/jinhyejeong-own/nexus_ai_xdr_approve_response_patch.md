# 주간 "승인 후 집행" 패치 (approve_response)

> **업데이트**: 이 문서의 패치는 이미 `docs/NEXUS_탐지_알림_수신_v3_AI-XDR_통합본.json`에 전부 반영되어 있습니다. 그 파일을 n8n에 임포트하면 아래 내용을 수작업으로 넣을 필요가 없습니다. 이 문서는 "무엇이, 왜 바뀌었는지" 참고용으로만 남겨둡니다.

적용 대상: `NEXUS 탐지 알림 수신 v2 - 최종 후보 (DRY-RUN)` (김태빈 공유본)

## 설계 다시 잡은 점

처음엔 MySQL `security_incident_tickets`에 컬럼을 추가해야 한다고 봤는데, 다시 보니 **DB 스키마를 안 건드려도 됨**. 이미 이 워크플로우가 화이트리스트(`sd.whitelist`)·건너뜀 기록(`sd.skipped`)·구 티켓(`sd.tickets`)을 n8n 워크플로우 메모리(`$getWorkflowStaticData('global')`)에 들고 있는 패턴을 그대로 쓰면 됨. "승인 대기 중인 조치 계획"도 똑같이 메모리에 `sd.pendingActions[ticket_key]`로 들고 있다가, 승인 버튼이 눌리면 그걸 꺼내서 **이미 있는 "계정 조치 실행?" → "계정 조치 실행"(MySQL) → "계정 조치 확인" → "계정 조치 결과·응답"** 경로로 그대로 흘려보내는 구조. 새 노드도, 새 연결도, DB 마이그레이션도 필요 없고 **코드 노드 3개 안의 내용만 추가**하면 됨.

**업데이트**: 처음엔 계정 잠금(`lock`, R1 계열)만 지원하고 세션 종료·AI Tool 제한(`session_ai`, R3/R11/R12)은 결과 판정 로직이 잠금/해제 전용이라 501로 막아뒀는데, `계정 조치 결과·응답` 노드에 `session_logout` 판정 분기를 하나 더 추가해서 지금은 두 종류 다 지원합니다(통합본 JSON에 반영됨).

---

## 패치 1 — `대응 준비(DB 조치)` 노드

기존 jsCode의 **`if (!steps.length) { ... }` 블록과 `return steps.map(...)` 사이**에 아래를 추가:

```js
if (d.pending_approval === true && !live) {
  const sdp = $getWorkflowStaticData('global');
  sdp.pendingActions = sdp.pendingActions || {};
  const liveStep = steps.find(s => s.sql);
  if (liveStep && okUser) {
    sdp.pendingActions[d.ticket_key] = { ...liveStep, ticket_id: d.ticket_id, ticket_key: d.ticket_key,
      rule_id: d.rule_id, user, response_group: d.response_group, saved_at: new Date().toISOString() };
  }
}
```

(`d.pending_approval`은 오늘 만든 `Time-Gate·자동집행 판정` 노드가 이미 내보내는 필드 — 주간이고 `auto_response_allowed===true`일 때 true)

---

## 패치 2 — `티켓 처리·화이트리스트` 노드

`if (dbTicketMatch) { ... }` 블록이 끝나는 `}` 바로 다음, `if (b.action === 'close' || ...)` 바로 **앞**에 추가:

```js
if (b.action === 'approve_response') {
  const sdp = $getWorkflowStaticData('global');
  sdp.pendingActions = sdp.pendingActions || {};
  const key = String(b.ticket_key || '').trim();
  const plan = sdp.pendingActions[key];
  if (!plan) return res(404, { status: 'no_pending_action' });
  if (plan.response_group === 'session_ai') return res(501, { status: 'not_supported_yet', note: '세션 종료·AI Tool 제한 승인은 다음 단계에서 지원' });
  delete sdp.pendingActions[key];
  return [{ json: { http: 200, body: null, db: {
    ticket_id: plan.ticket_id, ticket_key: plan.ticket_key, rule_id: plan.rule_id, user: plan.user,
    kind: 'lock', mode: 'live', by: '상황판(승인)', step: plan.step, undo: plan.undo,
    execute: true, sql: plan.sql, params: plan.params, verify_sql: plan.verify_sql
  } } }];
}
```

그리고 함수 맨 끝 fallback 줄을 이렇게 교체(allowed 목록에 `approve_response` 추가):

```js
return res(400, { status: 'bad_action', allowed: ['close', 'false_positive', 'release', 'lock', 'request_release', 'whitelist_add', 'whitelist_remove', 'approve_response'] });
```

---

## 패치 3 — `티켓 목록 만들기` 노드 (상황판에 "승인 대기" 배지 표시용)

`return [{ json: { http: 200, body: { ... } } }];` **바로 위**에 추가:

```js
const pendingMap = sd.pendingActions || {};
for (const t of all) t.pending_approval = !!pendingMap[t.ticket_key];
```

(이러면 상황판 GET 응답의 각 티켓 객체에 `pending_approval: true/false`가 붙어서, 프론트에서 "승인 대기" 배지와 승인 버튼을 바로 그릴 수 있음)

---

## 사용 흐름

1. 주간(08~20시)에 R1 계열 이벤트 발생 → AI 판정 + Time-Gate 통과 → `live_enabled=false`지만 `pending_approval=true` → "계정 잠금" 조치 계획이 `sd.pendingActions[ticket_key]`에 저장됨 (DB 조치는 아직 안 나감, 티켓은 평소처럼 기록됨)
2. 관제사가 상황판(GET `/webhook/nexus-tickets`)에서 `pending_approval: true`인 티켓 확인
3. 상황판이 POST `/webhook/nexus-ticket-action`에 `{"ticket_key": "...", "action": "approve_response"}` 전송
4. 기존 "계정 조치 실행?" → "계정 조치 실행"(MySQL) → "계정 조치 확인" → "계정 조치 결과·응답" 경로를 그대로 타고 실제 잠금 SQL 실행, 결과가 티켓 응답(`응답(처리 결과)`)으로 돌아옴

## 테스트 방법 (김태빈 님)

1. 위 3개 패치를 해당 Code 노드에 붙여넣기
2. R1 계열 테스트 이벤트를 `주간 시간대(08~20시)`에 맞춰 전송 (또는 Time-Gate 노드의 `isDaytime` 계산을 잠깐 `true`로 고정해서 테스트)
3. 상황판 GET 호출해서 해당 티켓에 `pending_approval: true` 뜨는지 확인
4. `approve_response` POST 보내서 실제로 해당 계정이 잠기는지, 상황판 응답이 정상 오는지 확인
5. 세션 종료(session_ai) 케이스로 같은 버튼을 누르면 501 `not_supported_yet`이 와야 정상(의도된 제한)
