#!/bin/bash
# 사용: key.sh ret | key.sh down down ret
for k in "$@"; do (printf "sendkey $k\n"; sleep 0.4) | nc -w2 127.0.0.1 4556 >/dev/null; done
