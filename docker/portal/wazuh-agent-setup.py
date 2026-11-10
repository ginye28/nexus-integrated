#!/usr/bin/env python3
"""Wazuh 에이전트 설정: FIM(실시간) 대상과 포털 보안 로그를 추가한다 (팀의 setup_wazuh_code_and_log_monitor.ps1 와 같은 대상)."""
import re
from pathlib import Path

p = Path("/var/ossec/etc/ossec.conf")
s = p.read_text(encoding="utf-8")
if "[NEXUS WORK]" not in s:
    fim = '''
    <!-- [NEXUS WORK] 웹 소스코드·업로드·설정파일 실시간 변경 감시 (FIM) -->
    <directories realtime="yes" report_changes="yes" check_all="yes">/app/app</directories>
    <directories realtime="yes" report_changes="yes" check_all="yes">/app/scripts</directories>
    <directories realtime="yes" check_all="yes">/app/instance/uploads</directories>
    <ignore>/app/__pycache__</ignore>
    <ignore type="sregex">__pycache__</ignore>
'''
    s = s.replace("</syscheck>", fim + "  </syscheck>", 1)
    log = '''
  <!-- [NEXUS WORK] 포털 보안 감사 로그 -->
  <localfile>
    <log_format>syslog</log_format>
    <location>/app/logs/security.jsonl</location>
  </localfile>
'''
    s = s.replace("</ossec_config>", log + "</ossec_config>", 1)
    p.write_text(s, encoding="utf-8")
print("wazuh agent config ok")
