# 진짜 pfSense VM (QEMU x86 에뮬레이션)
- pfSense CE 2.7.2, 디스크 `pfsense.qcow2`(8GB). 설치 ISO는 지워도 됨.
- 켜기: `./run.sh &` (부팅 약 2분) → https://127.0.0.1:8443 (인증서 경고는 무시) / 끄기: 웹 화면 Power → Halt, 또는 `printf 'quit\n' | nc 127.0.0.1 4556`
- 팀 설정(`_private/pfsense-config.xml`) 복원 완료(2026-11-10). 이제 `./run-restored.sh &` 로 켜고 https://127.0.0.1:8443 (LAN 172.16.50.2, 호스트명 pfSense-kry). 로그인은 팀 설정의 계정.
- 화면 캡처/키 입력 보조: shot.sh, key.sh, type.py (QEMU 모니터 4556 사용)
