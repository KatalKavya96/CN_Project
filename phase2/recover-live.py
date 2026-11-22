#!/usr/bin/env python3
"""Restore the normal demo state and write new logs without overwriting saved evidence."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
REMOTE_ROOT = "/Users/ronitsingh/Desktop/CN_Project"
stamp = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%dT%H%M%S")
OUT = ROOT / "evidence/recovery" / stamp
OUT.mkdir(parents=True, exist_ok=False)
env = dict(line.split("=", 1) for line in (ROOT / "phase2/lab.env").read_text().splitlines()
           if line and not line.startswith("#"))
SSH = ["/usr/bin/ssh", "-i", str(Path.home() / ".ssh/id_ed25519_cn_project"),
       "-o", "BatchMode=yes", "-o", "ConnectTimeout=6", "-o", "StrictHostKeyChecking=yes",
       "-o", "UserKnownHostsFile=/private/tmp/cn-project-ronit-known-hosts", "ronitsingh@" + env["MAC2_IP"]]
HELPER = ["sudo", "-n", "/usr/local/sbin/cn-project-admin"]
originals = [p for p in (ROOT / "evidence").rglob("*") if p.is_file() and not p.is_relative_to(OUT)]
before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in originals}
summary = dict(started_utc=datetime.now(timezone.utc).isoformat(), tests={}, evidence_preserved=False)

def run(mac, command, filename, expected=0):
    actual = command if mac == 1 else SSH + ["cd " + shlex.quote(REMOTE_ROOT) + " && " + shlex.join(command)]
    result = subprocess.run(actual, cwd=ROOT, capture_output=True, text=True, timeout=35)
    with (OUT / filename).open("a") as log:
        log.write("\nUTC: " + datetime.now(timezone.utc).isoformat() + f"\nMac {mac}\nCommand: " + shlex.join(command) +
                  f"\nExit: {result.returncode}\n" + result.stdout + "\n" + result.stderr + "\n")
    if expected is not None and result.returncode != expected:
        raise RuntimeError(f"Mac {mac}, {filename}: exit {result.returncode}")
    return result

def admin(mac, action):
    return run(mac, HELPER + [action], f"mac{mac}-restoration.txt")

def probe(mac, edge=None):
    filename = f"mac{mac}-" + ("standby" if edge else "primary") + "-https.txt"
    seen = set()
    for _ in range(8):
        command = ["/usr/bin/curl", "--noproxy", "*", "--http1.1", "--connect-timeout", "4", "--max-time", "12", "-sS", "-i"]
        if edge:
            command += ["--resolve", "app.cn-project.test:8443:" + edge]
        result = run(mac, command + ["https://app.cn-project.test:8443/api/status"], filename)
        assert result.stdout.startswith("HTTP/1.1 200"), "Expected HTTP 200"
        assert "X-Edge: " + ("mac1" if edge else "mac2") in result.stdout
        seen.update(line.split(":", 1)[1].strip() for line in result.stdout.splitlines() if line.lower().startswith("x-backend:"))
    assert seen == {"A", "B"}, "Missing healthy backend: " + repr(seen)
    summary["tests"][f"mac{mac}_" + ("standby" if edge else "primary")] = "PASS: default-trust HTTPS with A/B"

try:
    print("Restoring DNS, backends and normal firewall state...", flush=True)
    for mac in (1, 2):
        run(mac, ["/usr/bin/pmset", "-g", "batt"], f"mac{mac}-power.txt")
        for action in ("dns-primary", "dns-start", "firewall-off", "cache-flush"):
            admin(mac, action)
        run(mac, ["/usr/bin/python3", "phase2/services.py", "start", "b" if mac == 1 else "a"], f"mac{mac}-restoration.txt")
        run(mac, ["/sbin/ifconfig", "en0"], f"mac{mac}-inventory.txt")
        run(mac, ["/sbin/route", "-n", "get", "default"], f"mac{mac}-inventory.txt")
        run(mac, ["/sbin/ping", "-c", "3", env["MAC2_IP"] if mac == 1 else env["MAC1_IP"]], f"mac{mac}-ping.txt")
        for server in (env["MAC1_IP"], env["MAC2_IP"]):
            for name in ("app.cn-project.test", "api.cn-project.test"):
                answer = run(mac, ["/usr/bin/dig", "@" + server, name, "+time=2", "+tries=1"], f"mac{mac}-dns.txt")
                rows = [line.split()[-1] for line in answer.stdout.splitlines() if line.startswith(name + ".") and "\tA\t" in line]
                assert env["MAC2_IP"] in rows, "Unexpected project DNS answer"
        summary["tests"][f"mac{mac}_dns_and_lan"] = "PASS"
        port = "3002" if mac == 1 else "3001"
        for path in ("/", "/api/status"):
            response = run(mac, ["/usr/bin/curl", "--noproxy", "*", "--max-time", "5", "-sS", "-i",
                                 "http://127.0.0.1:" + port + path], f"mac{mac}-backend-endpoints.txt")
            assert "200 OK" in response.stdout
        response = run(mac, ["/usr/bin/curl", "--noproxy", "*", "--max-time", "5", "-sS", "-I",
                             "http://127.0.0.1:" + port + "/api/status"], f"mac{mac}-backend-endpoints.txt")
        assert "200 OK" in response.stdout
        summary["tests"][f"mac{mac}_backend_endpoints"] = "PASS: GET /, GET /api/status, HEAD"
    time.sleep(6)
    print("Verifying both edges and both client trust stores...", flush=True)
    for mac in (1, 2):
        probe(mac)
        probe(mac, env["MAC1_IP"])
        for name in ("app.cn-project.test", "api.cn-project.test"):
            result = run(mac, ["/usr/bin/curl", "--noproxy", "*", "--connect-timeout", "4", "--max-time", "12", "-v",
                               "https://" + name + ":8443/api/status"], f"mac{mac}-plain-trust.txt")
            assert "SSL certificate verify ok." in result.stderr
            assert "< HTTP/1.1 200" in result.stderr
        run(mac, HELPER + ["firewall-status"], f"mac{mac}-firewall-final.txt")
        summary["tests"][f"mac{mac}_both_hostnames_plain_https"] = "PASS"
    summary["status"] = "LIVE SETUP RESTORED AND VERIFIED ON BOTH MACS"
    print(summary["status"], flush=True)
finally:
    after = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in before}
    summary["evidence_preserved"] = before == after
    summary["original_files_checked"] = len(before)
    summary["finished_utc"] = datetime.now(timezone.utc).isoformat()
    (OUT / "recovery-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (OUT / "preserved-evidence-hashes.json").write_text(json.dumps(before, indent=2) + "\n")
    print("Original evidence unchanged:", summary["evidence_preserved"], "Files:", len(before), flush=True)
    print("New logs:", OUT, flush=True)
    if not summary["evidence_preserved"]:
        raise RuntimeError("An existing evidence file changed")
