# NEXUS WORK 포털(Flask) 컨테이너. 코드는 ./portal (stulss/nexus-work) 를 그대로 복사한다.
# Wazuh 에이전트(4.9.0)를 함께 넣어 업로드 폴더·소스·보안 로그의 파일 변경(FIM)을 매니저로 보낸다.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends curl procps ca-certificates lsb-release \
    && ARCH=$(dpkg --print-architecture) \
    && curl -fsSL -o /tmp/wazuh-agent.deb "https://packages.wazuh.com/4.x/apt/pool/main/w/wazuh-agent/wazuh-agent_4.9.0-1_${ARCH}.deb" \
    && WAZUH_MANAGER="wazuh-manager" dpkg -i /tmp/wazuh-agent.deb && rm -f /tmp/wazuh-agent.deb \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY portal/requirements.txt .
RUN pip install -r requirements.txt
COPY portal/ /app/
COPY docker/portal/entrypoint.sh /entrypoint.sh
COPY docker/portal/wazuh-agent-setup.py /opt/wazuh-agent-setup.py
RUN chmod +x /entrypoint.sh && mkdir -p /app/logs /app/instance/uploads
EXPOSE 5070
ENTRYPOINT ["/entrypoint.sh"]
