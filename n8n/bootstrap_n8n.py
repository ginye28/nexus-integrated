#!/usr/bin/env python3
"""n8n 준비: 소유자 계정 → 연결 정보(Credentials) → 팀 v3 워크플로 가져오기 → 게시(Publish).

- 워크플로는 팀 재현 패키지의 이식용 템플릿(NEXUS-v3-portable-template-inactive.json)이다.
- 포털·DB 주소는 이 노트북의 컨테이너 이름(portal, mysql)으로 바꾸고, 자격 증명은 .env 의 새 값으로 만든다.
- 템플릿에서 꺼져 있던 자동 조치 노드 5개(Discord 알림, DB 조치 실행, 대응 결과 알림, 계정 조치 실행,
  R5/R6/R8 IP 차단 API)는 팀 운영과 같게 켠다. 끄고 싶으면 .env 에 N8N_AUTO_ACTIONS=0 을 적는다.
  (계정 조치는 users 표의 잠금 컬럼만 고칠 수 있게 좁은 권한을 mysql-init/20-n8n-local.sh 가 준다.)
  '안전 설정(수신)' 노드의 스위치(live_enabled·discord_enabled·ip_block_enabled·response_mode)도 .env 값에 맞춰 켠다.
  IP 자동 차단은 템플릿의 예외 목록(127.0.0.1, 192.168.3.10/.11/.14/.15)에 든 주소를 건드리지 않는다.
- 여러 번 실행해도 안전하다(같은 ID 의 워크플로·연결 정보는 덮어쓴다).
"""
import json
import os
import subprocess
import sys
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "portal" / "repro-package" / "NEXUS-WORK-REPRO-2026-11-09" / "n8n" / "NEXUS-v3-portable-template-inactive.json"
CONTAINER = "nexus-integrated-n8n"
WF_ID = "NXv3AiXdr27Qp6Lm"
AUTO_NODES = {"Discord 알림", "DB 조치 실행", "대응 결과 알림", "계정 조치 실행", "R5/R6/R8 IP 차단 API"}


def load_env():
    env = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k] = v
    return env


ENV = load_env()
BASE = "http://127.0.0.1:5678"


def http(method, path, body=None, cookie=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json", **({"Cookie": cookie} if cookie else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), e.headers


def sh(*args, check=True):
    r = subprocess.run(args, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"명령 실패: {' '.join(args)}\n{r.stdout}\n{r.stderr}")
    return r.stdout + r.stderr


def wait_n8n():
    for _ in range(90):
        try:
            if http("GET", "/healthz")[0] == 200:
                return
        except Exception:
            pass
        time.sleep(2)
    sys.exit("n8n 이 응답하지 않습니다")


def ensure_owner():
    code, body, _ = http("POST", "/rest/owner/setup", {
        "email": ENV["N8N_OWNER_EMAIL"], "firstName": "NEXUS", "lastName": "Admin", "password": ENV["N8N_OWNER_PASSWORD"]})
    print("소유자 계정:", "생성" if code == 200 else f"이미 있음 또는 건너뜀 (HTTP {code})")


def build_files():
    cred = [
        {"id": "NXcredMySqlTicket", "name": "NEXUS Ticket DB (local)", "type": "mySql",
         "data": {"host": "mysql", "port": 3307, "database": "nexus", "user": "nexus_n8n_local",
                  "password": ENV["NEXUS_N8N_LOCAL_DB_PASSWORD"], "ssl": False, "connectTimeout": 10000}},
        {"id": "NXcredBearerPortal", "name": "NEXUS Portal API (Bearer)", "type": "httpBearerAuth",
         "data": {"token": ENV["LAB_INTERNAL_API_TOKEN"]}},
        {"id": "NXcredHeaderWebhook", "name": "NEXUS Webhook Token (Header)", "type": "httpHeaderAuth",
         "data": {"name": ENV.get("N8N_WEBHOOK_HEADER", "x-webhook-token"), "value": ENV["N8N_WEBHOOK_TOKEN"]}},
    ]
    discord = ENV.get("DISCORD_WEBHOOK_URL", "").strip()
    auto_actions = ENV.get("N8N_AUTO_ACTIONS", "1").strip() != "0"
    wf = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    wf["id"] = WF_ID
    wf["active"] = False
    wf["name"] = "NEXUS 탐지 알림 수신 v3 - AI-XDR 통합본 (로컬)" if auto_actions else "NEXUS 탐지 알림 수신 v3 - AI-XDR 통합본 (DRY-RUN)"
    wf["description"] = "팀 재현 패키지 v3 템플릿을 이 노트북용(portal/mysql 컨테이너)으로 연결한 워크플로"
    counts = {"mySql": 0, "httpBearerAuth": 0, "httpHeaderAuth": 0, "url": 0, "discord": 0, "enabled": 0, "switches": 0}
    for n in wf["nodes"]:
        t = n["type"]
        p = n.get("parameters", {})
        if t == "n8n-nodes-base.mySql":
            n["credentials"] = {"mySql": {"id": "NXcredMySqlTicket", "name": "NEXUS Ticket DB (local)"}}
            # 경보가 동시에 들어올 때 MySQL 교착(Deadlock)으로 실행이 실패하는 것을 막기 위해 자동 재시도를 켠다
            n.setdefault("retryOnFail", True)
            n.setdefault("maxTries", 4)
            n.setdefault("waitBetweenTries", 1500)
            counts["mySql"] += 1
        elif t == "n8n-nodes-base.httpRequest" and p.get("genericAuthType") == "httpBearerAuth":
            n["credentials"] = {"httpBearerAuth": {"id": "NXcredBearerPortal", "name": "NEXUS Portal API (Bearer)"}}
            counts["httpBearerAuth"] += 1
        elif t == "n8n-nodes-base.webhook" and p.get("authentication") == "headerAuth":
            # 템플릿에서 빠진 webhookId 를 채운다(없으면 n8n 이 경로 앞에 워크플로 ID 를 붙여 /webhook/nexus-alert 로 받지 못한다)
            n["webhookId"] = str(uuid.uuid5(uuid.NAMESPACE_URL, "nexus-integrated/" + p["path"]))
            n["credentials"] = {"httpHeaderAuth": {"id": "NXcredHeaderWebhook", "name": "NEXUS Webhook Token (Header)"}}
            counts["httpHeaderAuth"] += 1
        # Discord: 발표에서 보여준 "AI-XDR 분석 결과 알림" 분기만 켜고, 글자 메시지 대신 심각도별 색 띠의 임베드 카드로 보낸다
        if discord and n["name"] == "AI-XDR 평가 Discord 메시지 구성":
            p["jsCode"] = patch_embed(p["jsCode"])
            counts["discord"] += 1
        if discord and n["name"] == "AI-XDR 평가 Discord 알림":
            n["type"] = "n8n-nodes-base.httpRequest"
            n["typeVersion"] = 4.2
            n["parameters"] = {"method": "POST", "url": "={{ $env.DISCORD_WEBHOOK_URL }}", "sendBody": True,
                               "specifyBody": "json", "jsonBody": "={{ JSON.stringify($json.discord_payload) }}", "options": {}}
            counts["discord"] += 1
        if discord and n["name"] == "AI-XDR 평가 Discord 활성?":
            p["conditions"]["conditions"][0]["leftValue"] = "={{ true }}"
            counts["discord"] += 1
        if auto_actions and n["name"] == "NEXUS 안전 설정(수신)":
            # 노드만 켜서는 동작하지 않는다. 이 노드의 스위치가 실제 조치(live)·Discord·IP 차단의 허용 여부를 정한다.
            want = {"response_mode": ENV.get("XDR_RESPONSE_MODE", "live") or "live", "live_enabled": True,
                    "discord_enabled": bool(discord), "ip_block_enabled": ENV.get("XDR_IP_BLOCK_ENABLED", "1") == "1"}
            for a in p["assignments"]["assignments"]:
                if a["name"] in want:
                    a["value"] = want[a["name"]]
                    counts["switches"] += 1
        if auto_actions and n["name"] in AUTO_NODES:
            n.pop("disabled", None)
            counts["enabled"] += 1
            if n["type"] == "n8n-nodes-base.discord":
                # Discord 노드는 별도 연결 정보가 필요하므로, 임베드 카드와 같은 웹훅 주소로 HTTP 요청을 보낸다
                n["type"] = "n8n-nodes-base.httpRequest"
                n["typeVersion"] = 4.2
                n.pop("credentials", None)
                n["parameters"] = {"method": "POST", "url": "={{ $env.DISCORD_WEBHOOK_URL }}", "sendBody": True,
                                   "specifyBody": "json",
                                   "jsonBody": "={{ JSON.stringify({ username: 'NEXUS SOC Guardian', content: String($json.message || '').slice(0, 1900) }) }}",
                                   "options": {}}
        if isinstance(p.get("url"), str) and "host.docker.internal:5070" in p["url"]:
            p["url"] = p["url"].replace("host.docker.internal:5070", "portal:5070")
            counts["url"] += 1
    print("워크플로 연결:", counts)
    return cred, wf


EMBED_JS = r"""
// ---- Discord 임베드 카드 (심각도별 색 띠) ----
const sev = (() => {
  if (verdict === 'MALICIOUS' || score >= 80) return { color: 0xE74C3C, label: '심각', icon: '🚨' };
  if (verdict === 'SUSPICIOUS' || score >= 50) return { color: 0xE67E22, label: '높음', icon: '⚠️' };
  if (score >= 20) return { color: 0xF1C40F, label: '보통', icon: '🟡' };
  if (verdict === 'BENIGN') return { color: 0x2ECC71, label: '낮음', icon: '✅' };
  if (verdict === 'REVIEW_REQUIRED' || !Number.isFinite(score)) return { color: 0x95A5A6, label: '검토 필요', icon: '🔎' };
  return { color: 0x2ECC71, label: '낮음', icon: '✅' };
})();
const reasoning = String(row.reasoning || '').trim().slice(0, 300);
const actionLines = [];
actionLines.push(actions.length ? `🤖 AI 권고: **${actions.map(a => actionMap[a] || a).join(' · ')}**` : '🤖 AI 권고: 없음');
const stLine = { PENDING: '⏳ 처리 상태: **승인 대기** — 관리자가 확인 후 승인하면 차단', APPROVED: '✅ 처리 상태: **승인 완료**', NO_ACTION: '➖ 처리 상태: **조치 없음**', AUTO_CANDIDATE: '🤖 처리 상태: **자동 대응 후보**' };
actionLines.push(stLine[status] || `📌 처리 상태: **${statusMap[status] || status || '미확인'}**`);
actionLines.push(`📋 정책: ${policyMap[policyReason] || policyReason || '미기록'}`);
actionLines.push(`${auto ? '✅' : '🔒'} 자동 대응: ${auto ? '허용' : '불가 (항상 관리자 확인 후 차단)'}`);
const embed = {
  title: `${sev.icon} [NEXUS AI-XDR] ${verdictLabel} — ${rules.join(' / ') || '규칙 미확인'} 탐지 (${sev.label})`,
  description: `**${srcIp || '미확인'}** 에서 발생한 \`${eventType || '미확인'}\` 이벤트를 AI가 사건 단위로 평가했습니다.` + (reasoning ? `\n> ${reasoning.replace(/\n+/g, ' ')}` : ''),
  color: sev.color,
  fields: [
    { name: '🎯 탐지 룰', value: `\`${rules.join(' / ') || '미확인'}\``, inline: true },
    { name: '🌐 출발지 IP', value: `\`${srcIp || '미확인'}\``, inline: true },
    { name: '🎫 티켓', value: `\`${ticketId || '미확인'}\``, inline: true },
    { name: '🔥 위험도', value: Number.isFinite(score) ? `**${score}/100**` : '미확인', inline: true },
    { name: '📈 신뢰도', value: Number.isFinite(confidence) ? `**${(confidence * 100).toFixed(0)}%**` : '미확인', inline: true },
    { name: '🧩 이벤트', value: `\`${eventType || '미확인'}\``, inline: true },
    { name: '🛡️ 대응', value: actionLines.join('\n'), inline: false }
  ],
  footer: { text: `NEXUS AI-XDR • 발생 시각: ${occurredAt || '미확인'} • ${assessmentId.slice(0, 8)}` }
};
const discord_payload = { username: 'NEXUS SOC Guardian', embeds: [embed] };
"""


def patch_embed(code):
    marker = "const sd = $getWorkflowStaticData('global');"
    code = code.replace(marker, EMBED_JS + marker, 1)
    return code.replace(r"message: lines.join('\n'), message_ready: ready,", r"message: lines.join('\n'), discord_payload, message_ready: ready,", 1)


def main():
    wait_n8n()
    ensure_owner()
    cred, wf = build_files()
    tmp = ROOT / "n8n" / ".tmp"
    tmp.mkdir(exist_ok=True)
    (tmp / "credentials.json").write_text(json.dumps(cred), encoding="utf-8")
    (tmp / "workflow.json").write_text(json.dumps([wf]), encoding="utf-8")
    sh("docker", "cp", str(tmp / "credentials.json"), f"{CONTAINER}:/tmp/credentials.json")
    sh("docker", "cp", str(tmp / "workflow.json"), f"{CONTAINER}:/tmp/workflow.json")
    print(sh("docker", "exec", CONTAINER, "n8n", "import:credentials", "--input=/tmp/credentials.json").strip()[-300:])
    print(sh("docker", "exec", CONTAINER, "n8n", "import:workflow", "--input=/tmp/workflow.json").strip()[-300:])
    sh("docker", "exec", CONTAINER, "rm", "-f", "/tmp/credentials.json", "/tmp/workflow.json", check=False)
    for f in tmp.glob("*.json"):
        f.unlink()
    tmp.rmdir()
    print(sh("docker", "exec", CONTAINER, "n8n", "publish:workflow", f"--id={WF_ID}").strip()[-300:])
    sh("docker", "restart", CONTAINER)
    wait_n8n()
    # 게시된 워크플로의 웹훅은 기동 후 20~40초 뒤에 등록된다. 인증 없이 보내 404 가 아닐 때까지 기다린다.
    for _ in range(60):
        if http("POST", "/webhook/nexus-alert", {})[0] != 404:
            break
        time.sleep(3)
    else:
        sys.exit("웹훅이 등록되지 않았습니다 (docker logs nexus-integrated-n8n 확인)")
    print("n8n 준비 완료. 웹훅: http://n8n:5678/webhook/nexus-alert (헤더", ENV.get("N8N_WEBHOOK_HEADER", "x-webhook-token") + ")")


if __name__ == "__main__":
    main()
