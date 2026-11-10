#!/bin/sh
mkdir -p /run/edge
cp -n /etc/edge/geoblock.txt /run/edge/geoblock.txt
cp -n /etc/edge/nexus_auto_block.txt /run/edge/nexus_auto_block.txt
touch /run/edge/xdr_blocked_ips.txt /run/edge/pri1.txt
/etc/edge/fetch-lists.sh &
/etc/edge/sync-blocklists.sh &
exec haproxy -W -db -f /usr/local/etc/haproxy/haproxy.cfg
