#!/usr/bin/env python3
"""증빙 화면 캡처(선택). 로그인이 필요한 화면은 .env 의 계정으로 이 PC 안에서만 로그인한다(비밀번호는 화면·출력에 남지 않음).
사용: pip install playwright && python3 scripts/capture.py   (Google Chrome 이 설치돼 있어야 함)
결과: docs/screenshots/*.png
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
ENV = {}
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        ENV[k] = v
OUT = ROOT / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)


def dismiss(page):
    """첫 접속 때 뜨는 안내 창(Graylog 사용 통계 동의, n8n 체크리스트)을 닫는다. 동의 요청은 '취소'(거부)를 고른다."""
    for sel in ('button:has-text("Cancel")', '[aria-label="Close"]', 'button.close', 'button:has-text("Got it")'):
        try:
            page.locator(sel).first.click(timeout=1500)
        except Exception:
            pass


def shot(page, name, full=False):
    page.wait_for_timeout(2500)
    dismiss(page)
    page.wait_for_timeout(800)
    page.screenshot(path=str(OUT / name), full_page=full)
    print("저장:", name)


with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, locale="ko-KR")
    page = ctx.new_page()

    # 포털 관리자 → AI-XDR 평가 목록
    page.goto("http://127.0.0.1:5070/login")
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', ENV["SEED_ADMIN_PW"])
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    page.goto("http://127.0.0.1:5070/admin/xdr")
    shot(page, "01_portal_admin_xdr.png")

    # pfSense 스타일 화면, HAProxy 통계, ntopng
    page.goto("http://127.0.0.1:8080/")
    shot(page, "02_pfsense_style_dashboard.png")
    page.goto("http://127.0.0.1:2200/")
    shot(page, "03_haproxy_stats.png")
    page.goto("http://127.0.0.1:3000/")
    shot(page, "04_ntopng.png")

    # Graylog 로그인 → 경보(Alerts & Events), 검색
    page.goto("http://127.0.0.1:9000/")
    page.wait_for_selector("input", timeout=30000)
    page.locator("input").first.fill("admin")
    page.locator('input[type="password"]').first.fill(ENV["GRAYLOG_ROOT_PASSWORD"])
    page.keyboard.press("Enter")
    page.wait_for_load_state("networkidle")
    page.goto("http://127.0.0.1:9000/alerts")
    shot(page, "05_graylog_alerts.png")
    page.goto("http://127.0.0.1:9000/search?q=event_type%3Anot_found+OR+event_type%3Aagent_tool_call+OR+event_type%3Aprompt_injection_detected&rangetype=relative&relative=3600")
    shot(page, "06_graylog_search.png")

    # n8n 로그인 → 워크플로 실행 기록
    page.goto("http://127.0.0.1:5678/signin")
    page.wait_for_selector('input[type="email"], input[name="emailOrLdapLoginId"], input', timeout=30000)
    page.locator("input").first.fill(ENV["N8N_OWNER_EMAIL"])
    page.locator('input[type="password"]').first.fill(ENV["N8N_OWNER_PASSWORD"])
    page.keyboard.press("Enter")
    page.wait_for_load_state("networkidle")
    page.goto("http://127.0.0.1:5678/workflow/NXv3AiXdr27Qp6Lm/executions")
    page.wait_for_timeout(2500)
    page.mouse.click(393, 105)  # 'Production Checklist' 안내 창 닫기
    shot(page, "07_n8n_executions.png")
    page.goto("http://127.0.0.1:5678/workflow/NXv3AiXdr27Qp6Lm")
    page.wait_for_timeout(2500)
    page.mouse.click(393, 105)
    shot(page, "08_n8n_workflow.png")
    b.close()
