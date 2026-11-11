#!/usr/bin/env python3
"""시나리오 1개를 '공격 → 로그 수집 → 탐지 → n8n·AI-XDR 대응 → (승인) 차단 → 복구' 순서로 실행하고 시간을 잰다.

사용: python3 scripts/scenario.py r8 [--approve]      (r8 | r1 | r2 | r3 | scan | decoy)
결과: 화면에 단계별 시간·건수를 출력하고 docs/results/<시나리오>-<시각>.json 에 저장한다.
--approve : AI-XDR 평가가 IP 차단을 권고하면 관리자(admin) 로그인으로 '차단 승인'까지 누르고, 차단·복구를 확인한다.
비밀값(.env)은 읽기만 하며 결과 파일에는 쓰지 않는다.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = {}
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        ENV[k] = v

ATTACKER_IP = "192.168.3.11"
# 시나리오 → (공격 명령, 알림 DB 에 기대하는 규칙, 설명)
SCENARIOS = {
    "r8": ("r8", {"R8"}, "404 경로 스캔 35회"),
    "r1": ("r1", {"R1", "R6"}, "han 계정 로그인 6회 실패(잠금 → 잠금 후 재시도)"),
    "r2": ("r2", {"R2"}, "챗봇 프롬프트 인젝션"),
    "r3": ("r3", {"R3", "R11"}, "AI 에게 기밀 문서 요청 3회"),
    "r1lock": ("r1c", {"R1"}, "han 4회 실패 후 성공(계정 침해 의심) → 관리자 승인 → 계정 잠금"),
    "scan": ("scan", set(), "스캐너 User-Agent 4종 (Suricata 경보)"),
    "decoy": (None, set(), "미끼 경로(/.env) 접근 (포털 허니팟)"),
}


def sh(*cmd, check=True, timeout=600):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=ROOT)
    if check and r.returncode:
        raise RuntimeError(f"{cmd[:3]} 실패: {r.stderr[-300:]}")
    return r.stdout


def sql(q):
    out = subprocess.run(
        ["docker", "exec", "-e", "MYSQL_PWD=" + ENV["MYSQL_ROOT_PASSWORD"], "nexus-mysql",
         "mysql", "-uroot", "-N", "-B", "nexus", "-e", q],
        capture_output=True, text=True, timeout=60).stdout
    return [l.split("\t") for l in out.strip().splitlines() if l.strip()]


def attacker_http(path, ua=None):
    """공격 PC 컨테이너 안에서 포털로 GET 요청을 보내 상태 코드를 돌려준다."""
    code = ("import urllib.request,urllib.error,sys\n"
            "try:\n r=urllib.request.urlopen(urllib.request.Request('http://edge:5070%s'),timeout=10);print(r.status)\n"
            "except urllib.error.HTTPError as e:\n print(e.code)\n"
            "except Exception as e:\n print('ERR')\n") % path
    out = subprocess.run(["docker", "compose", "exec", "-T", "attacker", "python", "-c", code],
                         capture_output=True, text=True, timeout=60, cwd=ROOT).stdout.strip()
    return out.splitlines()[-1] if out else "ERR"


def graylog_count(query, seconds):
    req = urllib.request.Request(
        "http://127.0.0.1:9000/api/search/universal/relative?" + urllib.parse.urlencode(
            {"query": query, "range": seconds, "limit": 1}),
        headers={"Accept": "application/json", "X-Requested-By": "scenario"})
    import base64
    tok = base64.b64encode(("admin:" + ENV["GRAYLOG_ROOT_PASSWORD"]).encode()).decode()
    req.add_header("Authorization", "Basic " + tok)
    try:
        return json.load(urllib.request.urlopen(req, timeout=20)).get("total_results", 0)
    except Exception:
        return -1


def portal_mode(mode):
    """포털 컨테이너를 XDR_RESPONSE_MODE=mode 로 다시 만든다(팀 포털의 R1 승인 API 는 dry-run 에서만 열린다). 건강해질 때까지 기다린다."""
    env = dict(os.environ, XDR_RESPONSE_MODE=mode)
    subprocess.run(["docker", "compose", "up", "-d", "portal"], capture_output=True, text=True, cwd=ROOT, env=env, timeout=300)
    for _ in range(40):
        st = subprocess.run(["docker", "inspect", "-f", "{{.State.Health.Status}}", "nexus-portal"], capture_output=True, text=True).stdout.strip()
        if st == "healthy":
            break
        time.sleep(4)
    time.sleep(5)


def n8n_ticket_action(payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request("http://127.0.0.1:5678/webhook/nexus-ticket-action", body, method="POST",
                                 headers={"Content-Type": "application/json", ENV["N8N_WEBHOOK_HEADER"]: ENV["N8N_WEBHOOK_TOKEN"]})
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        return resp.status, resp.read().decode()[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]


def graylog_events(since_utc):
    """since_utc(epoch 초) 이후 Graylog 이벤트의 (규칙 ID 목록, 첫 이벤트까지 걸린 초 계산용 최초 시각)을 돌려준다."""
    import base64
    body = json.dumps({"query": "", "page": 1, "per_page": 100, "timerange": {"type": "relative", "range": 900}}).encode()
    req = urllib.request.Request("http://127.0.0.1:9000/api/events/search", body, method="POST",
                                 headers={"Content-Type": "application/json", "X-Requested-By": "scenario",
                                          "Authorization": "Basic " + base64.b64encode(("admin:" + ENV["GRAYLOG_ROOT_PASSWORD"]).encode()).decode()})
    try:
        evs = json.load(urllib.request.urlopen(req, timeout=20)).get("events", [])
    except Exception:
        return set(), None
    rules, first = set(), None
    for e in evs:
        ev = e["event"]
        ts = datetime.fromisoformat(ev["timestamp"].replace("Z", "+00:00")).timestamp()
        if ts < since_utc - 1:
            continue
        m = re.search(r"\[(R\d+)\]", ev.get("message", ""))
        rid = m.group(1) if m else ("DECOY" if "DECOY" in ev.get("message", "") else None)
        if rid:
            rules.add(rid)
            first = ts if first is None else min(first, ts)
    return rules, first


class Portal:
    def __init__(self):
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def req(self, method, path, data=None):
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        try:
            r = self.op.open(urllib.request.Request("http://127.0.0.1:5070" + path, body, method=method), timeout=20)
        except urllib.error.HTTPError as e:
            r = e
        return r.status, r.read().decode("utf-8", "replace")

    def csrf(self, page):
        return (re.search(r'name="csrf_token" value="([^"]+)"', self.req("GET", page)[1]) or [None, ""])[1]

    def login(self, user, pw):
        return self.req("POST", "/login", {"username": user, "password": pw, "csrf_token": self.csrf("/login")})[0]


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    approve = "--approve" in sys.argv
    if name not in SCENARIOS:
        sys.exit("사용: scenario.py " + "|".join(SCENARIOS) + " [--approve]")
    attack, rules, desc = SCENARIOS[name]
    res = {"scenario": name, "desc": desc, "started": datetime.now().isoformat(timespec="seconds"), "steps": {}}
    print(f"== 시나리오 {name}: {desc}")

    # 0) 준비: 이전 시험으로 막힌 공격 PC 풀기 + 기준값
    sh("./scripts/unblock.sh", check=False)
    base_alert = int(sql("SELECT COUNT(*) FROM security_incident_alerts")[0][0])
    base_assess = int(sql("SELECT COUNT(*) FROM security_xdr_assessments")[0][0])
    base_assess_ids = {r[0] for r in sql("SELECT assessment_id FROM security_xdr_assessments")}
    if name == "r1lock":
        # 같은 공격 PC(IP)의 티켓에 여러 계정이 섞여 있으면 'han 한 명'이 아니라 계정 잠금 계획이 만들어지지 않는다 → 열린 티켓을 먼저 닫는다
        for (tid,) in sql(f"SELECT id FROM security_incident_tickets WHERE src_ip='{ATTACKER_IP}' AND status='open'"):
            code, _t = n8n_ticket_action({"action": "close", "ticket_id": "NX-DB-%06d" % int(tid), "note": "시나리오 시작 전 정리"})
            print(f"[0] 이전 티켓 NX-DB-{int(tid):06d} 닫기 → HTTP {code}")
    pre = attacker_http("/")
    res["steps"]["0_사전"] = {"공격PC 포털 접속 코드": pre, "알림 건수": base_alert, "평가 건수": base_assess}
    print(f"[0] 사전: 공격 PC → 포털 {pre}, 알림 {base_alert}건, AI 평가 {base_assess}건")

    # 1) 공격
    t0 = time.time()
    if attack:
        out = sh("./scripts/attack.sh", attack, timeout=300)
        sample = [l for l in out.splitlines() if "->" in l][-3:]
    else:
        codes = [attacker_http("/.env") for _ in range(2)]
        sample = ["미끼 경로 /.env 응답: " + ",".join(codes)]
    t_attack = time.time() - t0
    res["steps"]["1_공격"] = {"소요(초)": round(t_attack, 1), "출력": sample}
    print(f"[1] 공격 완료 {t_attack:.0f}초 | " + " / ".join(sample))

    # 2) 탐지: Graylog 이벤트(규칙 발동) → n8n 웹훅 → 알림 DB 적재
    t_event = t_alert = None
    gl_rules, new_rules = set(), set()
    deadline = time.time() + 120
    while time.time() < deadline:
        gl_rules, first = graylog_events(t0)
        if first and t_event is None:
            t_event = first - t0
        cnt = int(sql("SELECT COUNT(*) FROM security_incident_alerts")[0][0])
        if cnt > base_alert and t_alert is None:
            t_alert = time.time() - t0
            rows = sql("SELECT rule_id FROM security_incident_alerts ORDER BY occurred_at DESC LIMIT 200")
            new_rules = {r[0] for r in rows[:cnt - base_alert]}
        if name == "scan":
            n = graylog_count("suricata", 300)
            if n > 0:
                break
        elif name == "decoy":
            if sql("SELECT 1 FROM security_incident_tickets WHERE ticket_key LIKE 'decoy:%' AND last_seen > NOW() - INTERVAL 2 MINUTE"):
                break
        elif (not rules or rules <= gl_rules) and t_alert is not None:
            break
        time.sleep(2)
    if name == "scan":
        n = graylog_count("suricata", 300)
        res["steps"]["2_탐지"] = {"Graylog suricata 메시지(최근 5분)": n, "경과(초)": round(time.time() - t0, 1)}
        print(f"[2] 탐지: Graylog 에서 Suricata 메시지 {n}건 확인 ({time.time() - t0:.0f}초)")
    elif name == "decoy":
        rows = sql("SELECT ticket_key FROM security_incident_tickets WHERE ticket_key LIKE 'decoy:%' ORDER BY last_seen DESC LIMIT 1")
        res["steps"]["2_탐지"] = {"디코이 티켓": rows[0][0] if rows else None, "경과(초)": round(time.time() - t0, 1)}
        print(f"[2] 탐지: 디코이 티켓 {rows[0][0] if rows else '없음'} ({time.time() - t0:.0f}초)")
    else:
        res["steps"]["2_탐지"] = {"Graylog 발동 규칙": sorted(gl_rules), "공격 시작→Graylog 이벤트(초)": round(t_event, 1) if t_event is not None else None,
                                "알림 DB 적재 규칙": sorted(new_rules), "새 알림 건수": int(sql('SELECT COUNT(*) FROM security_incident_alerts')[0][0]) - base_alert,
                                "공격 시작→알림 DB(초)": round(t_alert, 1) if t_alert else None}
        print(f"[2] 탐지: Graylog 규칙 {sorted(gl_rules)} ({t_event and round(t_event)}초) → 알림 DB {sorted(new_rules)} 새 알림 {res['steps']['2_탐지']['새 알림 건수']}건 ({t_alert and round(t_alert)}초)")

    # 3) n8n 자동 대응 → AI-XDR 평가(1분 집계 뒤)
    assess = None
    if name not in ("scan", "decoy"):
        deadline = time.time() + 300
        while time.time() < deadline:
            rows = sql("SELECT assessment_id, verdict, threat_score, confidence, status, recommended_actions, policy_mode, incident_ticket_id FROM security_xdr_assessments WHERE src_ip = '192.168.3.11' ORDER BY created_at DESC LIMIT 5")
            fresh = [r for r in rows if r[0] not in base_assess_ids]
            if fresh:
                assess = fresh[0]
                break
            time.sleep(5)
        if assess:
            res["steps"]["3_AI-XDR 평가"] = {"판정": assess[1], "위험도": assess[2], "신뢰도": assess[3], "상태": assess[4],
                                          "권고": assess[5], "정책": assess[6], "공격 시작→평가(초)": round(time.time() - t0, 1)}
            print(f"[3] AI-XDR 평가: {assess[1]} 위험도 {assess[2]} 신뢰도 {assess[3]} 상태 {assess[4]} ({time.time() - t0:.0f}초)")
        else:
            res["steps"]["3_AI-XDR 평가"] = {"결과": "300초 안에 새 평가 없음"}
            print("[3] AI-XDR 평가: 300초 안에 새 평가 없음")

    # 4') R1 계정 잠금 승인 (r1lock): 상황판이 하는 것과 같은 요청(approve_response)을 n8n 에 보낸다
    if name == "r1lock":
        if assess and assess[4] == "PENDING" and assess[7]:
            t1 = time.time()
            ticket = "NX-DB-%06d" % int(assess[7])
            code, text = 0, ""
            for _ in range(12):
                code, text = n8n_ticket_action({"action": "approve_response", "ticket_id": ticket, "assessment_id": assess[0]})
                if code != 404:  # 404(no_pending_action) = 아직 n8n 이 승인 계획을 저장하기 전
                    break
                time.sleep(10)
            locked = None
            for _ in range(30):
                r = sql("SELECT locked_until, locked_until > NOW() FROM users WHERE username='han'")
                locked = r[0] if r else None
                if os.environ.get("SCEN_DEBUG"):
                    print("   poll:", r)
                if locked and locked[1] == "1":
                    break
                time.sleep(2)
            blocked_login = Portal().login("han", ENV["SEED_KIM_PW"]) if locked and locked[1] == "1" else None
            res["steps"]["4_승인·계정 잠금"] = {"잠긴 뒤 han 올바른 비밀번호 로그인 응답": blocked_login, "티켓": ticket, "승인 응답": code, "응답 본문": text,
                                            "han 잠금": bool(locked and locked[1] == "1"), "잠금 해제 시각": locked[0] if locked else None,
                                            "승인→잠금 확인(초)": round(time.time() - t1, 1)}
            print(f"[4] 승인(approve_response) 응답 {code} → han 잠금 {bool(locked and locked[1] == '1')} ({time.time() - t1:.0f}초)")
        else:
            res["steps"]["4_승인·계정 잠금"] = {"건너뜀": "승인 대기 중인 R1 평가가 없음", "평가": list(assess) if assess else None}
            print("[4] 승인 건너뜀: 승인 대기 중인 R1 평가가 없음 →", assess)

    # 4) 관리자 승인 → 차단 (--approve)
    if approve and assess and "block_ip" in (assess[5] or "") and assess[4] == "PENDING":
        t1 = time.time()
        p = Portal()
        lg = p.login("admin", ENV["SEED_ADMIN_PW"])
        s, _ = p.req("POST", f"/admin/xdr/assessments/{assess[0]}/decision",
                     {"decision": "APPROVED_BLOCK_IP", "csrf_token": p.csrf("/admin/xdr")})
        blocked = None
        for _ in range(20):
            blocked = attacker_http("/")
            if blocked == "403":
                break
            time.sleep(1)
        res["steps"]["4_승인·차단"] = {"로그인": lg, "승인 응답": s, "승인→공격PC 403(초)": round(time.time() - t1, 1), "공격PC 응답": blocked}
        print(f"[4] 승인(admin) 응답 {s} → 공격 PC 응답 {blocked} ({time.time() - t1:.0f}초)")
    elif approve:
        res["steps"]["4_승인·차단"] = {"건너뜀": "승인 대기 중인 IP 차단 권고 평가가 없음"}
        print("[4] 승인 건너뜀: 승인 대기 중인 IP 차단 권고 평가가 없음")

    # 5) 복구
    t2 = time.time()
    sh("./scripts/unblock.sh", check=False)
    after = attacker_http("/")
    res["steps"]["5_복구"] = {"공격PC 포털 접속 코드": after, "소요(초)": round(time.time() - t2, 1)}
    print(f"[5] 복구: 차단 해제 후 공격 PC → 포털 {after} ({time.time() - t2:.0f}초)")
    if name in ("r1", "r1lock"):
        sql("UPDATE users SET locked_until=NULL WHERE username='han'")
        left = sql("SELECT locked_until FROM users WHERE username='han'")
        res["steps"]["5_복구"]["han 잠금 해제"] = (left[0][0] in ("NULL", "") if left else None)
        res["steps"]["5_복구"]["해제 뒤 han 로그인 응답"] = Portal().login("han", ENV["SEED_KIM_PW"])
        print("    (R1 시험으로 잠긴 han 계정도 해제)")

    out = ROOT / "docs" / "results"
    out.mkdir(parents=True, exist_ok=True)
    f = out / f"{name}-{datetime.now():%Y%m%d-%H%M%S}.json"
    f.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print("결과 저장:", f.relative_to(ROOT))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "r1lock":
        print("(R1 승인 API 는 포털이 dry-run 일 때만 열리므로 시험 동안 포털을 dry-run 으로 바꿉니다. 끝나면 원래 모드로 되돌립니다)")
        portal_mode("dry-run")
        try:
            main()
        finally:
            portal_mode(ENV.get("XDR_RESPONSE_MODE", "live"))
            print("포털 모드 복원:", ENV.get("XDR_RESPONSE_MODE", "live"))
    else:
        main()
