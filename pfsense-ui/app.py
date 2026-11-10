"""pfSense 스타일 읽기 전용 관리 화면 (NEXUS 통합 환경용).
이시헌 님의 pfSense 설정(config.json: 비밀값 제거본)과 edge 컨테이너의 실제 차단 목록·Suricata 경보·서비스 상태를 pfSense 화면 배치로 보여준다.
진짜 pfSense 가 아니며 설정을 바꾸지는 못한다."""
import json, os, urllib.request, csv, io, html, time
from pathlib import Path
from flask import Flask, request

app = Flask(__name__)
CFG = json.loads(Path("/app/config.json").read_text(encoding="utf-8"))
RUN = Path("/run/edge")
EVE = Path("/var/log/suricata/eve.json")

CSS = """
*{box-sizing:border-box} body{margin:0;font:14px/1.45 -apple-system,Helvetica,Arial,sans-serif;background:#f4f4f4;color:#212529}
nav{background:#212121;color:#fff;display:flex;align-items:center;gap:6px;padding:0 16px;height:50px}
nav .brand{font-weight:700;font-size:18px;margin-right:18px;color:#fff;text-decoration:none}nav .brand span{color:#4a90e2}
nav a{color:#ddd;text-decoration:none;padding:15px 11px}nav a:hover,nav a.on{background:#333;color:#fff}
.wrap{max-width:1200px;margin:18px auto;padding:0 16px}.panel{background:#fff;border:1px solid #ddd;border-radius:3px;margin-bottom:16px}
.panel>h3{margin:0;padding:9px 14px;background:#1e3f75;color:#fff;font-size:14px;font-weight:600;border-radius:3px 3px 0 0}
.panel .body{padding:12px 14px}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:6px 9px;border-bottom:1px solid #eee;font-size:13px;vertical-align:top}
th{background:#f0f2f5}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:900px){.grid{grid-template-columns:1fr}}
.dot{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:6px}.ok{background:#2ecc71}.bad{background:#e74c3c}.na{background:#aaa}
.pass{color:#1a7f37;font-weight:600}.block{color:#c0392b;font-weight:600}.reject{color:#d35400;font-weight:600}.mono{font-family:Menlo,monospace;font-size:12px}
.note{background:#fff8e1;border:1px solid #f0d98c;padding:8px 12px;border-radius:3px;margin-bottom:14px;font-size:12.5px}
.tag{background:#e8eef9;border-radius:3px;padding:1px 6px;font-size:12px}h1{font-size:20px;margin:6px 0 14px}
"""
NAV = [("/", "Status / Dashboard"), ("/services", "Status / Services"), ("/rules", "Firewall / Rules"), ("/nat", "Firewall / NAT"),
       ("/aliases", "Firewall / Aliases"), ("/tables", "Diagnostics / Tables"), ("/suricata", "Services / Suricata")]


def page(title, body):
    nav = "".join(f'<a href="{u}" class="{"on" if request.path == u else ""}">{n}</a>' for u, n in NAV)
    nav += '<a href="http://127.0.0.1:3000" target="_blank">ntopng ↗</a><a href="http://127.0.0.1:2200" target="_blank">HAProxy ↗</a>'
    return (f'<!doctype html><meta charset="utf-8"><title>{html.escape(CFG["system"]["hostname"])} - {html.escape(title)}</title>'
            f'<style>{CSS}</style><nav><a class="brand" href="/">pf<span>Sense</span>-style</a>{nav}</nav>'
            f'<div class="wrap"><div class="note">pfSense 설정(<b>{html.escape(CFG["system"]["hostname"])}.{html.escape(CFG["system"]["domain"])}</b>, config v{html.escape(CFG["system"]["version"])})을 '
            f'읽어 만든 <b>읽기 전용 재현 화면</b>입니다. 실제 pfSense 가 아니며 여기서 설정을 바꿀 수는 없습니다. 차단 목록·경보·서비스 상태는 실제 동작 중인 값입니다.</div>'
            f'<h1>{html.escape(title)}</h1>{body}</div>')


def fetch(url, timeout=3):
    try:
        return urllib.request.urlopen(url, timeout=timeout).read().decode("utf-8", "replace")
    except Exception:
        return None


def read_list(name):
    f = RUN / name
    if not f.exists():
        return []
    return [l.strip() for l in f.read_text(errors="replace").splitlines() if l.strip() and not l.startswith("#")]


def service_status():
    haproxy = fetch("http://edge:2200/;csv")
    ntop = fetch("http://edge:3000/", 3)
    st = []
    ha_ok = False
    if haproxy:
        rows = list(csv.reader(io.StringIO(haproxy.lstrip("# "))))
        hdr = rows[0] if rows else []
        for r in rows[1:]:
            if len(r) > 17 and r[1] == "portal1" and "status" in hdr and r[hdr.index("status")].startswith("UP"):
                ha_ok = True
    st.append(("haproxy", "TCP/HTTP(S) Load Balancer", bool(haproxy), "백엔드 portal1 " + ("UP" if ha_ok else "DOWN") if haproxy else "응답 없음"))
    recent = EVE.exists() and (time.time() - EVE.stat().st_mtime) < 86400 * 7
    st.append(("suricata", "Suricata IDS/IPS Daemon (WAN, 탐지 전용)", EVE.exists(), "eve.json 감시 중" if EVE.exists() else "로그 없음"))
    st.append(("ntopng", "ntopng Network Traffic Monitor", ntop is not None, "웹 화면 응답" if ntop is not None else "응답 없음"))
    st.append(("pfb_filter", "pfBlockerNG firewall filter service", (RUN / "geoblock.txt").exists(),
               f"GeoBlock {len(read_list('geoblock.txt'))}대역 · PRI1 {len(read_list('pri1.txt'))}건"))
    st.append(("pfb_dnsbl", "pfBlockerNG DNSBL service", None, "이 환경에서는 사용하지 않음"))
    return st


def table(headers, rows):
    return "<table><tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>" + "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</table>"


def ep(d):
    if not d:
        return "any"
    s = d.get("address") or d.get("network") or ("any" if "any" in d else "")
    if d.get("port"):
        s += f":{d['port']}"
    return html.escape(s or "any")


@app.route("/")
def dash():
    sysi = CFG["system"]
    info = table(["항목", "값"], [["Name", f'{sysi["hostname"]}.{sysi["domain"]}'], ["Version", f'config {sysi["version"]}'],
                                ["Timezone", sysi["timezone"]], ["DNS", ", ".join(sysi["dns"])],
                                ["Remote syslog", ", ".join(x for x in CFG["syslog"]["remote"] if x)]])
    def ipof(i):
        return "192.168.3.2/24 (원본: DHCP)" if i["ipaddr"] == "dhcp" else i["ipaddr"] + ("/" + i["subnet"] if i["subnet"] else "")
    ifs = table(["Interface", "NIC", "IP"], [[i["name"].upper(), i["if"], ipof(i)] for i in CFG["interfaces"]])
    svc = table(["", "Service", "Description", "Status"], [[f'<span class="dot {"ok" if ok else ("na" if ok is None else "bad")}"></span>', n, d, m] for n, d, ok, m in service_status()])
    blk = table(["테이블", "항목 수"], [["XDR_BLOCKED_IPS (포털 피드)", len(read_list("xdr_blocked_ips.txt"))], ["NEXUS_AUTO_BLOCK", len(read_list("nexus_auto_block.txt"))],
                                      ["pfB_GeoBlock_CRK (CN·RU·KP)", len(read_list("geoblock.txt"))], ["pfB_PRI1_v4", len(read_list("pri1.txt"))]])
    return page("Status / Dashboard", f'<div class="grid"><div class="panel"><h3>System Information</h3><div class="body">{info}</div></div>'
                f'<div class="panel"><h3>Interfaces</h3><div class="body">{ifs}</div></div>'
                f'<div class="panel"><h3>Services Status</h3><div class="body">{svc}</div></div>'
                f'<div class="panel"><h3>Firewall Tables</h3><div class="body">{blk}</div></div></div>' + suricata_panel(8))


@app.route("/services")
def services():
    rows = [[f'<span class="dot {"ok" if ok else ("na" if ok is None else "bad")}"></span>', n, d, m] for n, d, ok, m in service_status()]
    return page("Status / Services", '<div class="panel"><h3>Services</h3><div class="body">' + table(["", "Service", "Description", "상태"], rows) + "</div></div>")


@app.route("/rules")
def rules():
    out = ""
    for iface in ("wan", "lan", "openvpn"):
        rs = [r for r in CFG["rules"] if r["interface"] == iface]
        if not rs:
            continue
        rows = [[f'<span class="{r["type"]}">{r["type"].upper()}</span>', (r["protocol"] or "*").upper(), ep(r["src"]), ep(r["dst"]), "✔ log" if r["log"] else "", html.escape(html.unescape(r["descr"]))] for r in rs]
        out += f'<div class="panel"><h3>Firewall / Rules / {iface.upper()}</h3><div class="body">' + table(["Action", "Proto", "Source", "Destination", "Log", "Description"], rows) + "</div></div>"
    return page("Firewall / Rules", out)


@app.route("/nat")
def nat():
    rows = [[n["interface"].upper(), (n["protocol"] or "*").upper(), ep(n["src"]), ep(n["dst"]), f'{n["target"]}:{n["local_port"]}', html.escape(html.unescape(n["descr"]))] for n in CFG["nat"] if n["interface"]]
    return page("Firewall / NAT / Port Forward", '<div class="panel"><h3>Port Forward</h3><div class="body">' + table(["If", "Proto", "Source", "Dest", "NAT IP : Port", "Description"], rows) + "</div></div>")


ALIAS_FILES = {"XDR_BLOCKED_IPS": "xdr_blocked_ips.txt", "NEXUS_AUTO_BLOCK": "nexus_auto_block.txt", "pfB_GeoBlock_CRK_v4": "geoblock.txt", "pfB_PRI1_v4": "pri1.txt"}


@app.route("/aliases")
def aliases():
    rows = []
    for a in CFG["aliases"]:
        f = ALIAS_FILES.get(a["name"])
        cnt = len(read_list(f)) if f else (len((a["address"] or "").split()) if a["address"] else "")
        rows.append([f'<a href="/tables?name={a["name"]}">{html.escape(a["name"])}</a>', a["type"], html.escape((a["url"] or a["address"])[:70]), cnt, html.escape(a["descr"])])
    return page("Firewall / Aliases", '<div class="panel"><h3>IP Aliases</h3><div class="body">' + table(["Name", "Type", "Values / URL", "현재 항목 수", "Description"], rows) + "</div></div>")


@app.route("/tables")
def tables():
    name = request.args.get("name", "XDR_BLOCKED_IPS")
    f = ALIAS_FILES.get(name, "xdr_blocked_ips.txt")
    items = read_list(f)
    shown = items[:300]
    tabs = " ".join(f'<a class="tag" href="/tables?name={n}">{n}</a>' for n in ALIAS_FILES)
    body = f'<p>{tabs}</p><div class="panel"><h3>Diagnostics / Tables / {html.escape(name)} ({len(items)}건)</h3><div class="body mono">' + ("<br>".join(html.escape(i) for i in shown) or "(비어 있음)") + ("<br>… 외 %d건" % (len(items) - 300) if len(items) > 300 else "") + "</div></div>"
    return page("Diagnostics / Tables", body)


def alerts(n):
    if not EVE.exists():
        return []
    out = []
    try:
        for line in EVE.read_text(errors="replace").splitlines()[-5000:]:
            if '"event_type":"alert"' not in line:
                continue
            e = json.loads(line); a = e["alert"]
            out.append([e["timestamp"][:19].replace("T", " "), f'<span class="tag">P{a.get("severity")}</span>', html.escape(a.get("signature", "")),
                        html.escape(a.get("category", "")), f'{e.get("src_ip")}:{e.get("src_port", "")}', f'{e.get("dest_ip")}:{e.get("dest_port", "")}'])
    except Exception:
        pass
    return out[-n:][::-1]


def suricata_panel(n):
    rows = alerts(n)
    return '<div class="panel"><h3>Suricata Alerts (WAN)</h3><div class="body">' + (table(["시각", "우선순위", "Signature", "Class", "Source", "Destination"], rows) if rows else "경보 없음") + "</div></div>"


@app.route("/suricata")
def suricata():
    return page("Services / Suricata / Alerts", suricata_panel(100))


app.run(host="0.0.0.0", port=8080)
