#!/bin/sh
# pfSense URL Table(XDR_BLOCKED_IPS) 처럼 포털 차단 피드를 주기적으로 받아 HAProxy 차단 목록을 갱신한다.
FEED="${XDR_FEED_URL:-http://portal:5070/feeds/xdr-blocked-ips.txt}"
DIR=/run/edge
mkdir -p "$DIR"
[ -f "$DIR/geoblock.txt" ] || cp /etc/edge/geoblock.txt "$DIR/geoblock.txt"
[ -f "$DIR/nexus_auto_block.txt" ] || cp /etc/edge/nexus_auto_block.txt "$DIR/nexus_auto_block.txt"
touch "$DIR/xdr_blocked_ips.txt"
while true; do
  if wget -q -T 4 -O "$DIR/feed.new" "$FEED" 2>/dev/null; then
    # 줄 단위로 정리(빈 줄·주석 제거)
    grep -E '^[0-9a-fA-F:.]+(/[0-9]+)?$' "$DIR/feed.new" | sort -u > "$DIR/feed.clean" || true
    if ! cmp -s "$DIR/feed.clean" "$DIR/xdr_blocked_ips.txt"; then
      cp "$DIR/feed.clean" "$DIR/xdr_blocked_ips.txt"
      echo "[edge] 차단 목록 갱신: $(wc -l < "$DIR/xdr_blocked_ips.txt") 건"
      kill -USR2 1 2>/dev/null || true   # HAProxy master 에 reload 신호
    fi
  fi
  sleep "${SYNC_SECONDS:-5}"
done
