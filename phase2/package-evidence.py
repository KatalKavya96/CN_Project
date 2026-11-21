#!/usr/bin/env python3
"""Index original course evidence and export real packet analysis; never invent results."""
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "evidence/submission"
OUT.mkdir(parents=True, exist_ok=True)
env = dict(line.split("=", 1) for line in (ROOT / "phase2/lab.env").read_text().splitlines()
           if line and not line.startswith("#"))
P1 = "evidence/phase-1/failures-2026-11-22/"
P2 = "evidence/phase-2/"
FINAL = P2 + "final/"
CUT = P2 + "final-cutover-recheck/"

def entry(code, title, status, note, files):
    return dict(code=code, title=title, status=status, note=note, files=files)

items = [
    entry("P1-A", "Private LAN and topology", "Recorded", "Inventory includes IPv4, /19 mask, gateway, en0 and MAC. The wrong-DNS logs also contain actual successful peer pings in both directions.",
          ["docs/architecture.md", P2+"baseline/mac1-final-inventory.txt", P2+"baseline/mac2-final-inventory.txt", P1+"wrong-dns-mac1.txt", P1+"wrong-dns-mac2.txt"]),
    entry("P1-B", "Private DNS and two client resolvers", "Recorded", "Both clients' scoped resolvers list primary and backup. Both private names have DNS proof; the final by-name requests use the OS resolver.",
          [FINAL+"mac1-resolver.txt", FINAL+"mac2-resolver.txt", FINAL+"baseline-os-lookups.txt", P2+"dns-failover/backup-api-direct.txt", P2+"dns-failover/backup-direct.txt"]),
    entry("P1-C", "Backend source, interfaces, ports and endpoints", "Source and status evidence", "Both sources implement / and /api/status and bind to 0.0.0.0. Direct status responses for A and B are saved. Fresh /, /api/status and HEAD evidence for B is collected here. A separate direct-root A capture needs Ronit's live connection; it is not fabricated.",
          ["backend-a/app.py", "backend-b/app.py", FINAL+"isolation-allowed-edge.txt", "evidence/submission/backend-b-current.txt"]),
    entry("P1-D", "Reverse proxy and load balancing", "Recorded", "By-name HTTP 200 responses from both clients show A/B upstreams and X-Edge mac2.",
          [FINAL+"baseline-by-name.txt", P2+"baseline/mac2-upstream-log.txt", "phase2/render.sh"]),
    entry("P1-E", "Default-trust HTTPS on both Macs", "Recorded", "These final curl commands use neither --cacert nor -k. Both logs show hostname match, SSL certificate verify ok, HTTP 200 and exit 0.",
          [FINAL+"default-trust-mac1-verified.txt", FINAL+"default-trust-mac2-verified.txt", "tls/generated/server.ext"]),
    entry("P1-F", "Cache-Control, ETags and conditional 304", "Recorded", "Saved real headers include max-age=60 and matching 304 responses from both backends. A validator sent to the other backend can correctly return 200.",
          [P2+"baseline/cache-headers.txt", P2+"baseline/conditional-attempt-1.txt", P2+"baseline/conditional-attempt-2.txt"]),
    entry("P1-G", "DNS, TCP, TLS and reliable transport", "Recorded", "Use the original pcap plus the generated packet tables. Frames 1-2 are DNS, 3-5 the TCP handshake, 6 ClientHello/SNI, and 9 ServerHello. Client TCP port is 50549 and edge port 8443. TLS 1.3 encrypts later handshake messages; curl separately proves certificate verification.",
          [P2+"baseline/dns-tcp-tls-current.pcap", "evidence/submission/protocol-flow.tsv", "evidence/submission/dns-packets.tsv", "evidence/submission/tcp-reliability.tsv", "evidence/submission/tls-packets.tsv", FINAL+"default-trust-mac1-verified.txt"]),
    entry("P1-F1", "Wrong client DNS server", "Recorded: client-scoped", "An isolated resolver on each client forwards to unavailable 127.0.0.2:53. Queries fail while ping and DNS-independent verified HTTPS work. Global macOS DNS preferences are unchanged.",
          [P1+"wrong-dns-mac1.txt", P1+"wrong-dns-mac2.txt"]),
    entry("P1-F2", "Wrong IP in project DNS", "Recorded", "The real project records point to Mac 1 while its edge is stopped: DNS succeeds, TCP fails. The correct edge still works with --resolve. Records and standby are restored.",
          [P1+"wrong-record-mac1.txt", P1+"wrong-record-mac2.txt", P1+"wrong-record-restoration.txt"]),
    entry("P1-F3", "One backend stopped", "Recorded", "Both clients get B-only successful requests while A is stopped, then A/B after restart.",
          [FINAL+"backend-a-down-by-name.txt", FINAL+"backend-a-restored-by-name.txt"]),
    entry("P1-F4", "Both backends stopped", "Recorded", "Both clients resolve DNS and verify TLS but receive HTTP 502. Restoration returns both clients to HTTP 200 and A/B.",
          [P1+"both-backends-down-mac1.txt", P1+"both-backends-down-mac2.txt", P1+"both-backends-restoration.txt"]),
    entry("P1-F5", "Wrong destination port", "Recorded", "Correct domain and IP with wrong port 8444 gives TCP connection refusal; this is not a DNS or certificate failure.",
          [P2+"troubleshooting/wrong-port-dns-bypassed.txt"]),
    entry("P2-A", "Backup DNS with primary stopped", "Recorded", "A direct query confirms primary unavailability, then both flushed OS clients resolve and complete HTTPS through backup DNS. Primary is restored.",
          [FINAL+"primary-stopped-direct-query.txt", FINAL+"primary-down-os-lookup.txt", FINAL+"primary-down-by-name-https.txt", FINAL+"backup-query-log.txt", FINAL+"primary-restored.txt"]),
    entry("P2-B", "TTL, changed records and cache flushing", "Recorded", "The isolated client cache shows an exact countdown. Real macOS clients also retain old answers, refresh after expiry and adopt changed records immediately after flush. The first exact-35-second check failed; the measured-refresh recheck passed. Both observations are retained.",
          [P2+"ttl/client-cache-and-cutover.txt", CUT+"cutover-immediate-os-cache.txt", CUT+"cutover-after-ttl-os-cache.txt", CUT+"cutover-fresh-client-flush.txt", CUT+"summary.txt"]),
    entry("P2-C", "Backend isolation and rollback", "Recorded: two-Mac scope", "Direct Mac 1-to-A traffic is blocked; edge-to-A/B and both clients' HTTPS continue. PF counters and rollback are saved. Independent rejection by B requires an unrelated third source IP, unavailable here.",
          [FINAL+"isolation-rules.txt", FINAL+"isolation-blocked-client.txt", FINAL+"isolation-allowed-edge.txt", FINAL+"isolation-https-by-name.txt", FINAL+"isolation-counters.txt", FINAL+"isolation-rollback.txt"]),
    entry("P2-D", "Backend HA and SPOF explanation", "Recorded", "Passive detection and retry maintain B-only service during A failure, then restore A/B. Process failure is distinguished from host failure; the edge and shared LAN failure points are documented.",
          [FINAL+"backend-a-down-by-name.txt", FINAL+"backend-a-restored-by-name.txt", "docs/architecture.md", "docs/phase2-report.md"]),
    entry("P2-E", "Standby edge and DNS cutover", "Recorded", "Actual by-name clients first use mac2, then a flushed client uses mac1, then the expired client adopts mac1. These final requests do not use --resolve. DNS is restored to mac2.",
          [CUT+"cutover-authoritative.txt", CUT+"cutover-immediate-by-name.txt", CUT+"cutover-fresh-client-by-name.txt", CUT+"cutover-after-ttl-by-name.txt", CUT+"cutover-restored-by-name.txt", CUT+"dns-failover-cutover.pcap"]),
    entry("P2-F", "Faculty-injected troubleshooting", "Prepared; evaluation pending", "Real wrong-port and wrong-hostname drills plus diagnostics on both Macs are saved. The faculty's live injected fault and the students' spoken diagnosis cannot be pre-recorded as completed.",
          [P2+"troubleshooting/wrong-port-dns-bypassed.txt", P2+"troubleshooting/wrong-tls-hostname.txt", FINAL+"diagnostics-mac1.txt", FINAL+"diagnostics-mac2.txt", "phase2/diagnose.sh"]),
    entry("DOC-A", "Architecture and request flow", "Prepared", "Network topology, combined roles, current and historical addresses, ports, protocol mapping and SPOFs.",
          ["docs/architecture.md", "docs/request-flow.md"]),
    entry("DOC-B", "Configuration bundle and backend launch", "Prepared", "Configuration sources, generated local edge config, firewall template, rollback and TLS setup notes. No private key material is included.",
          ["evidence/submission/configuration-bundle.txt", "phase2/README.md", "phase2/render.sh", "phase2/install-admin.sh", "phase2/admin-control.sh", "phase2/services.py"]),
    entry("DOC-C", "Phase 2 final report", "Prepared", "Changes from Phase 1, expected/observed behavior, troubleshooting findings and learning paragraphs for all six extensions.",
          ["docs/phase2-report.md", P2+"acceptance-summary.md"]),
    entry("DOC-D", "Final presentation and individual viva", "Prepared; performance pending", "The full 11-step role-by-role guide and viva questions are available. Both students must participate and answer during the evaluation.",
          ["docs/tomorrow-demo.md", "docs/runbook.md", "docs/viva.md"]),
]

recoveries = sorted((ROOT / "evidence/recovery").glob("*/recovery-summary.json"))
recovery = None
for candidate in reversed(recoveries):
    snapshot = json.loads(candidate.read_text())
    if snapshot.get("status") == "LIVE SETUP RESTORED AND VERIFIED ON BOTH MACS" and snapshot.get("evidence_preserved"):
        recovery = candidate.parent
        break
if recovery is not None:
    prefix = str(recovery.relative_to(ROOT)) + "/"
    for item in items:
        if item["code"] == "P1-A":
            item["files"] += [prefix + f"mac{mac}-{kind}.txt" for mac in (1, 2) for kind in ("inventory", "ping")]
        elif item["code"] == "P1-B":
            item["files"] += [prefix + "mac1-dns.txt", prefix + "mac2-dns.txt"]
        elif item["code"] == "P1-C":
            item["status"] = "Recorded"
            item["note"] = "Both backends bind to 0.0.0.0 and implement / and /api/status. The recovery logs record successful direct GET /, GET /api/status and HEAD on the correct local backend port from each service host."
            item["files"] += [prefix + "mac1-backend-endpoints.txt", prefix + "mac2-backend-endpoints.txt"]
        elif item["code"] == "P1-E":
            item["files"] += [prefix + "mac1-plain-trust.txt", prefix + "mac2-plain-trust.txt"]
        elif item["code"] == "P1-D":
            item["files"] += [prefix + "mac1-primary-https.txt", prefix + "mac2-primary-https.txt"]

def collect(command):
    started = datetime.now(timezone.utc).isoformat()
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=12)
        return f"UTC: {started}\nCommand: {shlex.join(command)}\nExit: {result.returncode}\n{result.stdout}\n{result.stderr}\n"
    except subprocess.TimeoutExpired:
        return f"UTC: {started}\nCommand: {shlex.join(command)}\nTIMEOUT after 12 seconds\n"

backend_commands = [["/usr/bin/curl", "--noproxy", "*", "--max-time", "5", "-sS", "-i", "http://127.0.0.1:3002" + path]
                    for path in ("/", "/api/status")]
backend_commands.append(["/usr/bin/curl", "--noproxy", "*", "--max-time", "5", "-sS", "-I", "http://127.0.0.1:3002/api/status"])
if not (OUT / "backend-b-current.txt").exists():
    (OUT / "backend-b-current.txt").write_text("\n".join(collect(command) for command in backend_commands))

tshark = "/Applications/Wireshark.app/Contents/MacOS/tshark"
pcap = str(ROOT / (P2 + "baseline/dns-tcp-tls-current.pcap"))
exports = {
    "protocol-flow.tsv": (None, ["frame.number", "_ws.col.Protocol", "ip.src", "tcp.srcport", "ip.dst", "tcp.dstport", "tcp.seq", "tcp.ack", "_ws.col.Info"]),
    "dns-packets.tsv": ("dns", ["frame.number", "ip.src", "udp.srcport", "ip.dst", "udp.dstport", "dns.qry.name", "dns.a", "dns.resp.ttl", "_ws.col.Info"]),
    "tcp-reliability.tsv": ("tcp.stream == 0", ["frame.number", "tcp.srcport", "tcp.dstport", "tcp.seq", "tcp.ack", "tcp.len", "tcp.window_size", "_ws.col.Info"]),
    "tls-packets.tsv": ("tls", ["frame.number", "tls.handshake.type", "tls.handshake.extensions_server_name", "tls.record.content_type", "_ws.col.Info"]),
}
for name, (display_filter, fields) in exports.items():
    command = [tshark, "-r", pcap, "-n", "-T", "fields", "-E", "header=y"]
    if display_filter:
        command += ["-Y", display_filter]
    for field in fields:
        command += ["-e", field]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    (OUT / name).write_text(result.stdout)

configs = ["dns/project.conf", "dns/backup-project.conf", "edge/nginx.conf", "phase2/lab.env", "phase2/render.sh",
           "phase2/install-admin.sh", "phase2/admin-control.sh", "tls/generated/server.ext"]
bundle = ["PUBLIC CONFIGURATION SOURCES - private keys and certificate material are excluded.\n"
          "The installed managed DNS is generated by install-admin.sh; static dns/*.conf are reference configs.\n"]
for name in configs:
    bundle.append("\n=== " + name + " ===\n" + (ROOT / name).read_text())
bundle.append("\n=== Mac 1 actual generated nginx config ===\n" + (ROOT / ".runtime/nginx.conf").read_text())
(OUT / "configuration-bundle.txt").write_text("\n".join(bundle))

now = datetime.now(timezone.utc).isoformat()
manifest = dict(assembled_utc=now, note="Original tests retain their original collection dates. Generated HTML displays log excerpts, not terminal screenshots.", requirements=items, files={})
for item in items:
    for name in item["files"]:
        path = ROOT / name
        if not path.is_file():
            raise FileNotFoundError(name)
        data = path.read_bytes()
        manifest["files"][name] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

def relative(name):
    return os.path.relpath(ROOT / name, OUT)

index = ["# Submission Evidence Index", "", "Assembled 23 November 2026 (IST). Original observations retain their test timestamps.", "",
         "Open [the browsable evidence book](evidence-book.html). This package indexes real exports and packet captures; it does not manufacture screenshots or faculty results.", "",
         "| Requirement | Status | Evidence and explanation |", "| --- | --- | --- |"]
for item in items:
    links = "; ".join(f"[{Path(name).name}]({relative(name)})" for name in item["files"])
    index.append(f'| {item["code"]}: {item["title"]} | {item["status"]} | {links} |')
index += ["", "## Scope and remaining live checks", "",
          "- Wrong DNS uses a temporary explicitly configured client resolver, not macOS global DNS preferences.",
          "- The third-source rejection test for Backend B is unavailable in the two-Mac arrangement.",
          ("- Both backend root/status/HEAD endpoints have fresh recovery exports linked above." if recovery else "- Backend A's separate direct-root response needs a live Ronit connection; its source and direct /api/status results are included."),
          "- Faculty-injected fault, spoken presentation and individual viva remain live evaluation tasks.",
          ("- The completed recovery snapshot verifies SSH access, LAN, DNS and plain HTTPS on both Macs. Keep both laptops open and powered; each log retains its observation time." if recovery else "- Ronit's saved IP currently responds to ping but SSH and HTTPS time out. Earlier passing captures are retained as historical evidence, not presented as fresh health checks."),
          "- manifest.json contains source-file sizes and SHA-256 digests; packet tables are generated directly from the original pcap.", ""]
(OUT / "README.md").write_text("\n".join(index))

styles = """body{font-family:system-ui,sans-serif;max-width:1100px;margin:30px auto;padding:0 24px;color:#17212b;background:#fff;line-height:1.5}h1{font-size:26px}h2{font-size:20px;margin-top:36px;border-bottom:1px solid #cbd5df;padding-bottom:8px}a{color:#0759a6}nav{columns:2;border-bottom:1px solid #cbd5df;padding-bottom:20px}nav a{display:block;padding:4px 0}pre{font:12px/1.5 ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f5f7;padding:16px;border-left:3px solid #6b7d8e}details{margin:12px 0}summary{cursor:pointer;font-weight:600}small{color:#4d5b69}.status{font-weight:600}header{border-bottom:2px solid #17212b}footer{margin-top:40px;border-top:1px solid #cbd5df}@media print{nav{columns:2}details{break-inside:avoid}pre{font-size:9px}a{color:inherit}body{margin:0;max-width:none}}"""
parts = ["<!doctype html><html lang='en'><meta charset='utf-8'><title>CN Project submission evidence</title><style>" + styles + "</style><body>",
         "<header><h1>CN Project: Phase 1 and Phase 2 Evidence</h1><p>Kavya Katal and Ronit Singh · two-Mac deployment</p>",
         "<p>Assembled 23 November 2026 IST. Original tests retain their collection dates. These are rendered log excerpts and source links, not terminal screenshots.</p>",
         "<p>Read scope notes: client-scoped wrong DNS; two-host firewall limits; faculty/viva pending; fresh remote checks depend on SSH access.</p></header><nav>"]
for item in items:
    parts.append(f'<a href="#{item["code"]}">{html.escape(item["code"] + " - " + item["title"])}</a>')
parts.append("</nav>")
for item in items:
    parts += [f'<section id="{item["code"]}"><h2>{html.escape(item["code"] + " - " + item["title"])}</h2>',
              '<p class="status">' + html.escape(item["status"]) + '</p><p>' + html.escape(item["note"]) + '</p>']
    for name in item["files"]:
        path = ROOT / name
        parts.append('<p><a href="' + html.escape(relative(name), quote=True) + '">' + html.escape(name) + '</a></p>')
        if path.suffix in (".pcap", ".png"):
            continue
        text = path.read_text(errors="replace")
        # Excerpts retain original ordering and bytes of the selected lines.
        if len(text) > 7000:
            selected = []
            lines = text.splitlines()
            for i, line in enumerate(lines):
                if any(token in line for token in ("UTC:", "Mac ", "Command:", "Exit:", "HTTP/", "X-Backend:", "X-Edge:", "verify ok", "status:", "TTL=", "PASS", "ip_address:")):
                    selected.extend(lines[max(0, i-1):i+2])
            text = "Selected log lines; open the source for the complete output.\n" + "\n".join(selected[:130])
        parts.append('<details><summary>View recorded output or source</summary><pre>' + html.escape(text) + '</pre></details>')
    parts.append("</section>")
parts.append('<footer><p>Generated UTC: ' + html.escape(now) + '. File provenance and hashes: <a href="manifest.json">manifest.json</a>.</p></footer></body></html>')
(OUT / "evidence-book.html").write_text("\n".join(parts))
print("Created evidence index, HTML book, configuration bundle, manifest, and packet exports:", OUT)
print("Requirements indexed:", len(items), "Source artifacts:", len(manifest["files"]))
