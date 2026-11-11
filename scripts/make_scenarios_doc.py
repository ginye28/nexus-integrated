#!/usr/bin/env python3
"""docs/results/*.json(시나리오 실측 원본)에서 docs/SCENARIOS.md 를 다시 만든다. 사용: python3 scripts/make_scenarios_doc.py"""
import json, glob, os
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
R = {}
for f in sorted(glob.glob(str(ROOT / "docs/results/*.json"))):
    d = json.load(open(f, encoding="utf-8")); R[d["scenario"]] = (d, os.path.basename(f))
ORDER = [n for n in ["r8", "r3", "r2", "r1", "r1lock", "scan", "decoy"] if n in R]
exp = {
 "r8": ("`python3 scripts/scenario.py r8`", "404 경로 스캔 35회 → Graylog R8 → n8n 티켓·Discord → AI-XDR 평가. 단순 스캔이라 **정상(BENIGN) 판정, 차단 없음**이 기대 결과", "R8 단독 스캔은 낮은 위험으로 보는 것이 정책에 맞다(오탐 방지)"),
 "r3": ("`python3 scripts/scenario.py r3 --approve`", "AI 에게 기밀 문서를 3번 요청 → R3(AI Tool 권한 거부)·R11(반복 거부) → n8n 강제 로그아웃·티켓 → AI-XDR **악성 판정·IP 차단 권고** → 관리자 승인 → 공격 PC **403 차단** → 복구", "전체 체인(공격→수집→탐지→자동 대응→AI 판정→승인→차단→복구) 한 번에 확인"),
 "r2": ("`python3 scripts/scenario.py r2`", "챗봇에 프롬프트 인젝션 → 포털이 즉시 403 → R2 → AI-XDR 악성 판정(승인 대기)", "승인은 하지 않음(`--approve` 를 붙이면 승인·차단까지)"),
 "r1": ("`python3 scripts/scenario.py r1`", "han 로그인 6회 실패 → 포털 잠금(`account_locked`) → Graylog R1·R6 → n8n 이 `account_locked` 를 \"잠금 결과 기록\"으로 분류", "R1 은 '잠금 결과 기록' 이라 AI-XDR 평가 대상이 아님. 승인으로 계정을 잠그는 경로는 아래 **R1LOCK**"),
 "r1lock": ("`python3 scripts/scenario.py r1lock`", "han 이 4회 실패 후 성공(계정 침해 의심) ×2 → Graylog R1 → AI-XDR **MALICIOUS(80점·신뢰도 0.80 이상)** → 승인 대기 → 관리자 승인(`approve_response`) → n8n **계정 잠금(15분)** → 올바른 비밀번호로도 로그인 거부 → 해제 후 정상 로그인", "팀 포털의 R1 승인 API 는 포털이 dry-run 일 때만 열리므로, 이 시나리오는 시험 동안만 포털을 dry-run 으로 바꾸고 끝나면 되돌립니다. 같은 공격 PC 의 열린 티켓에 다른 계정이 섞여 있으면 계획이 만들어지지 않아 시작 전에 열린 티켓을 정식 절차(close)로 닫습니다"),
 "scan": ("`python3 scripts/scenario.py scan`", "스캐너 User-Agent 4종(Nikto·sqlmap·Nmap·masscan) 요청 → Suricata(ET SCAN) 경보 → Graylog `suricata`", "IDS 는 탐지 전용(차단 안 함)"),
 "decoy": ("`python3 scripts/scenario.py decoy`", "미끼 경로 `/.env` 접근 → 허니팟 이벤트 → 디코이 티켓 → **즉시 자동 차단(2번째 요청부터 403)**", "AI-XDR 평가를 거치지 않는 즉시 차단 경로(앱 내장)"),
}
L = ["# 시나리오 재현 절차와 실측 결과\n",
 "각 시나리오를 **공격 → 로그 수집 → 탐지 → n8n 자동 대응(·AI-XDR 판정) → (승인) 차단·잠금 → 복구** 순서로 `scripts/scenario.py` 가 실행하고 시간을 잽니다. 결과는 `docs/results/*.json` 에 원본이 남고, 이 문서는 `python3 scripts/make_scenarios_doc.py` 로 다시 만들 수 있습니다.\n",
 "- 측정일: 2026-11-10~11, MacBook(Apple 칩, Docker 메모리 약 8GB), 이 저장소 구성 그대로. 시간은 모두 **공격 시작을 0초로 한 경과 시간**입니다.\n- 사전 조건: `./scripts/up.sh` 완료, `./scripts/verify.sh` 통과, `.env` 에 `GROQ_API_KEY`. 각 시나리오는 시작 때 공격 PC(192.168.3.11) 차단을 풀고, 끝날 때도 풉니다(복구).\n- 같은 명령을 다시 실행하면 같은 흐름이 재현됩니다(AI 판정 점수와 시간은 ±수 초·수 점 달라질 수 있음).\n",
 "## 한눈에\n", "| 시나리오 | 공격(초) | Graylog 규칙 발동 | 알림 DB 적재 | AI-XDR 평가 | 승인 후 결과 | 복구 |", "|---|---|---|---|---|---|---|"]
for n in ORDER:
    d = R[n][0]["steps"]; t = d.get("2_탐지", {})
    if n == "scan": gl = f"Suricata {t.get('Graylog suricata 메시지(최근 5분)')}건 ({round(t.get('경과(초)', 0))}초)"; al = "-"
    elif n == "decoy": gl = f"디코이 티켓 ({round(t.get('경과(초)', 0))}초)"; al = "-"
    else:
        gl = f"{', '.join(t.get('Graylog 발동 규칙', []))} ({t.get('공격 시작→Graylog 이벤트(초)')}초)"
        a = t.get("공격 시작→알림 DB(초)")
        al = f"{', '.join(t.get('알림 DB 적재 규칙', []))} {t.get('새 알림 건수')}건 ({a}초)" if a else "알림 DB 적재 없음"
    a3 = d.get("3_AI-XDR 평가")
    ai = (f"{a3['판정']} {a3['위험도']}점·신뢰도 {a3['신뢰도']} · {a3['상태']} ({a3['공격 시작→평가(초)']}초)" if a3 and "판정" in a3 else ("300초 안에 평가 없음(대상 아님)" if a3 else "-"))
    a4 = d.get("4_승인·차단"); a5 = d.get("4_승인·계정 잠금")
    if a4 and "공격PC 응답" in a4: ap = f"공격 PC {a4['공격PC 응답']} ({a4['승인→공격PC 403(초)']}초)"
    elif a5 and "han 잠금" in a5: ap = f"han 잠금 {a5['han 잠금']}, 올바른 비밀번호 로그인 {a5.get('잠긴 뒤 han 올바른 비밀번호 로그인 응답')} ({a5['승인→잠금 확인(초)']}초)"
    else: ap = "-"
    rc = f"포털 {d['5_복구']['공격PC 포털 접속 코드']} ({d['5_복구']['소요(초)']}초)" + (f", han 로그인 {d['5_복구']['해제 뒤 han 로그인 응답']}" if "해제 뒤 han 로그인 응답" in d['5_복구'] else "")
    L.append(f"| {n} | {d['1_공격']['소요(초)']} | {gl} | {al} | {ai} | {ap} | {rc} |")
L.append("")
for n in ORDER:
    d, fn = R[n]; cmd, e, note = exp[n]
    L += [f"## {n.upper()} — {d['desc']}\n", f"- **명령**: {cmd}\n- **기대 결과**: {e}\n- **참고**: {note}\n- **실측 원본**: [`docs/results/{fn}`](results/{fn})\n", "| 단계 | 실측 |\n|---|---|"]
    for k, v in d["steps"].items(): L.append(f"| {k.split('_', 1)[1]} | {json.dumps(v, ensure_ascii=False)} |")
    L.append("")
L.append("""## 캡처

화면 캡처는 `docs/screenshots/` (비밀번호·토큰이 보이지 않는 화면만):

| 파일 | 내용 |
|---|---|
| `01_portal_admin_xdr.png` | 관리자 화면의 AI-XDR 평가 목록(위험도·신뢰도·근거·권고, 승인 버튼) |
| `02_pfsense_style_dashboard.png` | pfSense 스타일 화면(서비스 상태·차단 목록) |
| `03_haproxy_stats.png` | 경계 장비(HAProxy) 통계 |
| `04_ntopng.png` | ntopng 트래픽 화면 |
| `05_graylog_alerts.png`, `06_graylog_search.png` | Graylog 경보(R1~R12)와 로그 검색 |
| `07_n8n_executions.png`, `08_n8n_workflow.png` | n8n 실행 기록과 워크플로 |

캡처 다시 만들기: `pip install playwright && python3 scripts/capture.py` (Google Chrome 필요).

## 새 PC 설치 시험 (2026-11-11, 최신 저장소 기준)

깨끗한 `git clone` → README 대로 `./scripts/up.sh` (볼륨 분리, 처음에는 `.env` 에 Groq 키 없음):

| 확인 | 결과 |
|---|---|
| `up.sh` 완주(이미지 빌드·기동·Graylog 규칙·n8n 워크플로 적용) | 첫 시도에 성공, 재시도 메시지 없음 |
| `verify.sh` | 통과 7 / 실패 0 (공격 → Graylog → n8n → 알림 DB 0→1건) |
| Groq 키를 넣은 뒤 `scenario.py r3 --approve` | R3 탐지 → AI-XDR MALICIOUS 80점 → 승인 → 공격 PC 403 → 복구 성공 |
| `scenario.py r1lock` | R1 탐지 → MALICIOUS 80점 → `approve_response` → han 잠금(True) → 복구 성공 |
| (참고, 11/10) 키 없이 `r2` / `r3 --approve` | `REVIEW_REQUIRED`(판정 불가) / R3·R11 미발생 → **AI 시나리오는 Groq 키 필요** |

이 시험에서 시나리오 스크립트가 이전 시나리오의 늦은 평가를 잘못 고르는 문제를 찾아 고쳤습니다(기대 규칙의 평가만 선택).

## 측정 방법과 한계

- Graylog 규칙 발동 시각은 Graylog 이벤트 API 의 타임스탬프, 알림 DB 적재는 `security_incident_alerts` 에 새 행이 생긴 시각(2초 간격 확인)입니다.
- AI-XDR 평가는 n8n 이 1분 단위로 이벤트를 모은 뒤 Groq 으로 판정하므로 약 40~120초가 걸립니다(`GROQ_API_KEY` 가 없으면 판정 불가).
- 승인→차단은 edge 가 5초마다 차단 목록을 동기화하는 구조입니다. 로그인 응답 `401` 은 잠긴 계정의 로그인 화면(실패), `200` 은 성공 후 이동한 화면입니다.
- Discord 전송은 n8n 실행 기록의 노드 성공 여부로 확인했고, Discord 앱 화면은 캡처하지 않았습니다(웹훅 주소 노출 방지).
- **하지 않은 것**: 실제 Kali·Windows 에이전트, 서버 3대 분리, 진짜 pfSense 경유 트래픽.
""")
(ROOT / "docs" / "SCENARIOS.md").write_text("\n".join(L), encoding="utf-8")
print("docs/SCENARIOS.md 갱신:", ORDER)
