#!/bin/bash
# pfSense CE 설치용 부팅 (x86 에뮬레이션이라 느립니다). 시리얼 4555, 모니터 4556
cd "$(dirname "$0")"
exec qemu-system-x86_64 -machine q35 -cpu max -smp 4 -m 2048 -accel tcg,thread=multi \
  -drive file=pfsense.qcow2,if=virtio,format=qcow2 \
  -drive file=pfSense-CE-2.7.2-RELEASE-amd64.iso,media=cdrom,if=ide \
  -boot d \
  -netdev user,id=wan,hostfwd=tcp:127.0.0.1:8443-:443 -device virtio-net-pci,netdev=wan \
  -netdev user,id=lan,net=192.168.3.0/24,dhcpstart=192.168.3.50 -device virtio-net-pci,netdev=lan \
  -display none -serial tcp:127.0.0.1:4555,server=on,wait=off -monitor tcp:127.0.0.1:4556,server=on,wait=off
