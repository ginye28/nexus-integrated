#!/bin/bash
# 설치된 pfSense 부팅. WAN=vtnet0(NAT 10.0.2.x), LAN=vtnet1(172.16.50.0/24, 팀 설정 복원 후). 웹 화면은 LAN 쪽 포워딩: https://127.0.0.1:8443
cd "$(dirname "$0")"
exec qemu-system-x86_64 -machine q35 -cpu max -smp 4 -m 2048 -accel tcg,thread=multi \
  -drive file=pfsense.qcow2,if=virtio,format=qcow2 -boot c \
  -netdev user,id=wan -device virtio-net-pci,netdev=wan,mac=52:54:00:aa:00:01 \
  -netdev user,id=lan,net=172.16.50.0/24,host=172.16.50.254,dhcpstart=172.16.50.100,hostfwd=tcp:127.0.0.1:8443-172.16.50.2:443,hostfwd=tcp:127.0.0.1:2222-172.16.50.2:22 -device virtio-net-pci,netdev=lan,mac=52:54:00:aa:00:02 \
  -display none -serial tcp:127.0.0.1:4555,server=on,wait=off -monitor tcp:127.0.0.1:4556,server=on,wait=off
