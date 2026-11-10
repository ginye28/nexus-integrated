#!/bin/sh
# pfBlockerNG 목록을 받아 HAProxy 차단 파일로 만든다 (pfSense config 의 GeoBlock_CRK · PRI1 와 같은 출처).
#   GeoBlock_CRK : ipdeny.com 의 중국(cn)·러시아(ru)·북한(kp) 국가 대역
#   PRI1         : abuse.ch Feodo·SSLBL, CINS, Emerging Threats, Talos, Spamhaus DROP
# (pfSense 에서는 PRI1 을 LAN 아웃바운드에 적용하지만, 이 컨테이너 구조에서는 들어오는 요청에만 적용한다)
DIR=/run/edge
TMP=$DIR/lists.tmp; mkdir -p "$TMP"
ips() { grep -Eo '([0-9]{1,3}\.){3}[0-9]{1,3}(/[0-9]{1,2})?' ; }
get() { wget -q -T 20 -O - "$1" 2>/dev/null; }

geo() {
  : > "$TMP/geo"
  for cc in cn ru kp; do get "https://www.ipdeny.com/ipblocks/data/countries/$cc.zone" | ips >> "$TMP/geo"; done
  [ -s "$TMP/geo" ] && sort -u "$TMP/geo" > "$DIR/geoblock.txt" && echo "[edge] GeoBlock(CN/RU/KP) $(wc -l < "$DIR/geoblock.txt") 대역"
}
pri1() {
  : > "$TMP/pri1"
  get https://feodotracker.abuse.ch/downloads/ipblocklist_recommended.txt | grep -v '^#' | ips >> "$TMP/pri1"
  get https://sslbl.abuse.ch/blacklist/sslipblacklist.txt | grep -v '^#' | ips >> "$TMP/pri1"
  get https://cinsarmy.com/list/ci-badguys.txt | ips >> "$TMP/pri1"
  get https://rules.emergingthreats.net/fwrules/emerging-Block-IPs.txt | grep -v '^#' | ips >> "$TMP/pri1"
  get https://rules.emergingthreats.net/blockrules/compromised-ips.txt | grep -v '^#' | ips >> "$TMP/pri1"
  get https://talosintelligence.com/documents/ip-blacklist | ips >> "$TMP/pri1"
  get https://www.spamhaus.org/drop/drop_v4.json | grep -Eo '"cidr":"[^"]+"' | ips >> "$TMP/pri1"
  # 사설 대역(도커 내부망)은 목록에 있어도 제외한다
  [ -s "$TMP/pri1" ] && sort -u "$TMP/pri1" | grep -Ev '^(10\.|127\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)' > "$DIR/pri1.txt" \
    && echo "[edge] PRI1 위협 목록 $(wc -l < "$DIR/pri1.txt") 건"
}
touch "$DIR/pri1.txt"
n=0
while true; do
  if [ $((n % 24)) -eq 0 ]; then geo; fi   # 하루 1번(GeoBlock: EveryDay)
  pri1                                        # 1시간마다(PRI1: 01hour)
  if [ -s "$DIR/geoblock.txt" ] || [ -s "$DIR/pri1.txt" ]; then kill -USR2 1 2>/dev/null; fi
  n=$((n+1)); sleep 3600
done
