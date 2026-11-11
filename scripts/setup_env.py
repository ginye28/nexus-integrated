#!/usr/bin/env python3
"""처음 한 번 .env 를 만든다(비밀값은 이 노트북에서 무작위로 생성). 이미 있으면 빠진 값만 채운다."""
import hashlib, secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
f = ROOT / ".env"
cur = {}
if f.exists():
    for line in f.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); cur[k] = v

def tok(n=24): return secrets.token_urlsafe(n)
def pw(): return "Nx" + secrets.token_urlsafe(14) + "9!"

defaults = {
    # --- MySQL / 포털 ---
    "MYSQL_ROOT_PASSWORD": tok(), "NEXUS_APP_PASSWORD": tok(), "NEXUS_CONF_PASSWORD": tok(),
    "NEXUS_N8N_LOCAL_DB_PASSWORD": tok(), "SECRET_KEY": tok(40),
    "SEED_KIM_PW": pw(), "SEED_LEE_PW": pw(), "SEED_ADMIN_PW": pw(),
    "LAB_INTERNAL_API_TOKEN": "nxapi_" + tok(), "LAB_INTERNAL_API_FLAG": "FLAG{" + secrets.token_hex(12) + "}",
    # --- AI ---  Groq 키가 있으면 아래에 직접 넣는다(없으면 내장 판정으로 동작)
    "GROQ_API_KEY": "", "GROQ_MODEL": "openai/gpt-oss-120b", "AI_PROVIDER": "auto", "XDR_AI_PROVIDER": "auto",
    # --- AI-XDR 동작: demo = 관리자 승인 시 실제로 IP 차단(이 노트북 안의 공격 PC 컨테이너만 대상), safe = 기록만(dry-run)
    "NEXUS_XDR_MODE": "demo",
    # AI 판정이 이 점수·신뢰도 이상일 때만 승인 대기(R1 계정 잠금)·자동 차단 후보가 된다(팀 포털 .env.example 기본값)
    "XDR_AUTO_MIN_SCORE": "80", "XDR_AUTO_MIN_CONFIDENCE": "0.80",
    # --- Graylog ---
    "GRAYLOG_ROOT_PASSWORD": pw(), "GRAYLOG_PASSWORD_SECRET": tok(48),
    # --- n8n ---
    "N8N_ENCRYPTION_KEY": tok(32), "N8N_OWNER_EMAIL": "admin@nexus.local", "N8N_OWNER_PASSWORD": pw(),
    "N8N_WEBHOOK_TOKEN": tok(), "N8N_WEBHOOK_HEADER": "x-webhook-token",
    "DISCORD_WEBHOOK_URL": "",
}
new = {**defaults, **{k: v for k, v in cur.items() if v != "" or k not in defaults}}
demo = new.get("NEXUS_XDR_MODE", "demo") == "demo"
new["XDR_RESPONSE_MODE"] = "live" if demo else "dry-run"
new["XDR_IP_BLOCK_ENABLED"] = "1" if demo else "0"
sha = hashlib.sha256(new["GRAYLOG_ROOT_PASSWORD"].encode()).hexdigest()
new["GRAYLOG_ROOT_PASSWORD_SHA2"] = sha
lines = ["# NEXUS 통합 환경 — 비밀값 포함. 공유·커밋 금지(.gitignore 처리됨)."]
lines += [f"{k}={v}" for k, v in new.items()]
f.write_text("\n".join(lines) + "\n", encoding="utf-8")
f.chmod(0o600)
print(".env 준비 완료 (", len(new), "개 항목 )")
