#!/usr/bin/env python3
"""NEXUS Graylog 설정 적용기 (표준 라이브러리만 사용).

팀 재현 패키지(portal/repro-package/.../graylog)의 입력·Stream·탐지 규칙(R1~R12)을 새 Graylog 에 넣고,
각 규칙마다 n8n 웹훅으로 보내는 HTTP 알림(Notification)을 만들어 연결한다.
- 여러 번 실행해도 안전하다: 같은 이름이 이미 있으면 건너뛴다.
- 필요한 환경변수(.env): GRAYLOG_URL, GRAYLOG_ROOT_PASSWORD, N8N_WEBHOOK_URL, N8N_WEBHOOK_TOKEN
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "portal" / "repro-package" / "NEXUS-WORK-REPRO-2026-11-09" / "graylog"


def load_env():
    env = dict(os.environ)
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip())
    return env


ENV = load_env()
BASE = ENV.get("GRAYLOG_URL", "http://127.0.0.1:9000").rstrip("/") + "/api"
AUTH = "Basic " + base64.b64encode(f"admin:{ENV['GRAYLOG_ROOT_PASSWORD']}".encode()).decode()


def api(method, path, body=None, retries=1):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={
        "Authorization": AUTH, "X-Requested-By": "nexus-integrated-import",
        "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:600]
        raise SystemExit(f"Graylog API 오류 {method} {path} -> HTTP {e.code}: {detail}")


def wait_ready():
    for _ in range(120):
        try:
            api("GET", "/system")
            return
        except SystemExit:
            time.sleep(3)
        except Exception:
            time.sleep(3)
    raise SystemExit("Graylog 가 준비되지 않았습니다")


# ---------- 규칙별 n8n 웹훅 본문 (schema_version 1.1 envelope) ----------
RULE_META = {  # stable_name, action_level
    "R1": ("ACCOUNT_COMPROMISE", "contain"), "R2": ("DIRECT_PROMPT_INJECTION_BLOCKED", "alert"),
    "R3": ("AI_TOOL_PERMISSION_DENIED", "contain"), "R4": ("UNEXPECTED_INTERNAL_API_CALL", "alert"),
    "R5": ("ACCOUNT_SPRAY", "alert"), "R6": ("POST_LOCK_RETRY", "alert"),
    "R7": ("OFF_HOURS_LOGIN_SUCCESS", "observe"), "R8": ("NOT_FOUND_SCAN", "alert"),
    "R9": ("ADMIN_PATH_ACCESS_DENIED", "alert"), "R10": ("DIRECT_CONFIDENTIAL_ACCESS_DENIED", "alert"),
    "R11": ("REPEATED_AI_TOOL_PERMISSION_DENIAL", "contain"), "R12": ("CONTENT_TRIGGERED_PROTECTED_TOOL_DENIAL", "contain"),
}
# 필드 정의에 없는 값은 규칙 정의(n8n 정규화 코드의 기대값)에 맞춰 고정값으로 채운다.
FIXED_EVENT = {
    "R5": {"event_type": "login_failure", "decision": "DENY", "severity": "medium"},
    "R6": {"event_type": "post_lock_retry_detected", "decision": "WARN", "severity": "high"},
    "R7": {"event_type": "login_success", "decision": "ALLOW", "severity": "info"},
    "R8": {"event_type": "not_found", "decision": "INFO", "severity": "info"},
    "R9": {"event_type": "authz_deny", "decision": "DENY", "severity": "medium"},
    "R10": {"event_type": "authz_deny", "decision": "DENY", "severity": "medium"},
    "R2": {"decision": "DENY", "severity": "high"},
    "R3": {"decision": "DENY", "severity": "high"},
    "R11": {"decision": "DENY", "severity": "high"},
    "R12": {"decision": "DENY", "severity": "high"},
}
ALLOWED = ["event_type", "injection_type", "source_type", "source_component", "trigger_source", "user", "role",
           "src_ip", "request_id", "session_id", "tool_name", "resource_class", "resource_id", "trigger_resource_id",
           "pattern_id", "decision", "reason", "severity", "path", "resource", "required", "count",
           "window_seconds", "failed_attempts", "lock_request_id", "trigger_event_type"]


def body_template(rule_id, field_spec):
    stable, action = RULE_META[rule_id]
    fixed = FIXED_EVENT.get(rule_id, {})
    parts = []
    for key in ALLOWED:
        if key in fixed and key not in field_spec:
            parts.append(f'"{key}":"{fixed[key]}"')
        elif key in fixed and key in ("decision", "severity"):
            parts.append(f'"{key}":"{fixed[key]}"')   # 규칙이 정한 값을 우선한다
        elif key in field_spec:
            parts.append(f'"{key}":"${{event.fields.{key}}}"')
    if rule_id == "R1":  # 심각도는 이벤트 종류에 따라 다르다(n8n 기대값: 침해의심 high / 잠금 medium)
        parts = [p for p in parts if not p.startswith('"severity"')]
        parts.append('"severity":"${if event.fields.event_type==\'account_locked\'}medium${else}high${end}"')
    if rule_id == "R4":
        parts = [p for p in parts if not p.startswith('"severity"')]
        parts.append('"severity":"${if event.fields.severity}${event.fields.severity}${else}medium${end}"')
    event = ",".join(parts)
    return (
        '{"schema_version":"1.1","action_level":"%s",'
        '"rule":{"id":"%s","stable_name":"%s","display_name":"${event_definition_title}"},'
        '"alert":{"id":"${event.id}","event_definition_id":"${event_definition_id}",'
        '"title":"${event_definition_title}","timestamp":"${event.timestamp}","priority":${event.priority},'
        '"key":"${event.key}"},'
        '"event":{%s}}' % (action, rule_id, stable, event)
    )


def main():
    wait_ready()
    inputs = json.loads((PKG / "inputs.json").read_text(encoding="utf-8"))["inputs"]
    streams = json.loads((PKG / "streams.json").read_text(encoding="utf-8"))["streams"]
    definitions = json.loads((PKG / "event_definitions.json").read_text(encoding="utf-8"))["event_definitions"]

    # 1) Inputs
    existing = {i["title"]: i["id"] for i in api("GET", "/system/inputs").get("inputs", [])}
    input_ids = {}
    for inp in inputs:
        if inp["title"] in existing:
            input_ids[inp["key"]] = existing[inp["title"]]
            print(f"= 입력 이미 있음: {inp['title']}")
            continue
        body = {"title": inp["title"], "type": inp["type"], "global": True, "configuration": inp["configuration"]}
        input_ids[inp["key"]] = api("POST", "/system/inputs", body).get("id")
        print(f"+ 입력 생성: {inp['title']} ({inp['configuration']['port']}/udp)")

    # 2) Streams
    index_sets = api("GET", "/system/indices/index_sets").get("index_sets", [])
    default_set = next((s["id"] for s in index_sets if s.get("default")), index_sets[0]["id"])
    existing_streams = {s["title"]: s["id"] for s in api("GET", "/streams").get("streams", [])}
    stream_ids = {}
    for st in streams:
        if st["title"] in existing_streams:
            stream_ids[st["title"]] = existing_streams[st["title"]]
            print(f"= Stream 이미 있음: {st['title']}")
            continue
        created = api("POST", "/streams", {
            "title": st["title"], "description": st["description"], "matching_type": st["matching_type"],
            "index_set_id": default_set, "remove_matches_from_default_stream": st["remove_matches_from_default_stream"]})
        sid = created.get("stream_id") or created.get("id")
        for rule in st["rules"]:
            value = input_ids[rule["input_ref"]] if rule.get("input_ref") else rule["value"]
            api("POST", f"/streams/{sid}/rules", {"field": rule["field"], "type": rule["type"], "value": value,
                                                  "inverted": rule["inverted"]})
        if not st.get("disabled"):
            api("POST", f"/streams/{sid}/resume")
        stream_ids[st["title"]] = sid
        print(f"+ Stream 생성: {st['title']} (규칙 {len(st['rules'])}개)")

    # 3) n8n 알림 + 4) Event Definitions
    n8n_url = ENV.get("N8N_WEBHOOK_URL", "http://n8n:5678/webhook/nexus-alert")
    token = ENV.get("N8N_WEBHOOK_TOKEN", "")
    header = ENV.get("N8N_WEBHOOK_HEADER", "x-webhook-token")
    # Graylog 는 허용 목록(URL Whitelist)에 없는 주소로는 HTTP 알림을 보내지 않는다
    wl = api("GET", "/system/urlwhitelist")
    entries = wl.get("entries", [])
    if not any(e.get("value") == n8n_url for e in entries):
        entries.append({"id": "nexus-n8n-webhook", "title": "NEXUS n8n webhook", "type": "literal", "value": n8n_url})
        api("PUT", "/system/urlwhitelist", {"entries": entries, "disabled": False})
        print("+ URL 허용 목록 추가:", n8n_url)
    existing_notifs = {n["title"]: n["id"] for n in api("GET", "/events/notifications?per_page=200").get("notifications", [])}
    existing_defs = {d["title"] for d in api("GET", "/events/definitions?per_page=200").get("event_definitions", [])}
    for d in definitions:
        rule_id = d["rule_id"]
        notif_ids = []
        if rule_id in RULE_META:
            title = f"[NEXUS][{rule_id}] n8n 전달"
            payload = {
                "title": title, "description": f"{rule_id} 경보를 n8n 웹훅으로 전달",
                "config": {
                    "type": "http-notification-v2", "url": n8n_url, "method": "POST", "content_type": "JSON",
                    "api_key": header, "api_key_as_header": True, "api_secret": {"set_value": token},
                    "skip_tls_verification": False, "time_zone": "Asia/Seoul",
                    "body_template": body_template(rule_id, d.get("field_spec", {})),
                }}
            if title in existing_notifs:
                api("PUT", f"/events/notifications/{existing_notifs[title]}", {**payload, "id": existing_notifs[title]})
                notif_ids.append(existing_notifs[title])
            else:
                notif_ids.append(api("POST", "/events/notifications", payload)["id"])
                print(f"+ 알림 생성: {title}")
        if d["display_name"] in existing_defs:
            print(f"= 탐지 규칙 이미 있음(알림만 갱신): {d['display_name']}")
            continue
        cfg = json.loads(json.dumps(d["config"]))
        cfg["streams"] = [stream_ids[n] for n in cfg.pop("stream_names", [])]
        storage = [{"type": s["type"], "streams": [stream_ids.get(n, n) for n in s.get("stream_names", [])
                                                 if n in stream_ids]} for s in d.get("storage", [])]
        # "All events" 같은 시스템 Stream 은 ID 로 해석한다
        sys_streams = {s["title"]: s["id"] for s in api("GET", "/streams").get("streams", [])}
        storage = [{"type": s["type"], "streams": [sys_streams.get(n) for n in s0.get("stream_names", []) if sys_streams.get(n)]}
                   for s, s0 in zip(storage, d.get("storage", []))]
        dto = {
            "title": d["display_name"], "description": d["description"], "remediation_steps": d.get("remediation_steps", ""),
            "priority": d["priority"], "alert": d["alert"], "config": cfg, "field_spec": d["field_spec"],
            "key_spec": d["key_spec"], "notification_settings": d["notification_settings"],
            "notifications": [{"notification_id": n} for n in notif_ids], "storage": storage,
        }
        api("POST", "/events/definitions?schedule=true", dto)
        print(f"+ 탐지 규칙 생성: {d['display_name']}")
    print("Graylog 설정 적용 완료")


if __name__ == "__main__":
    main()
