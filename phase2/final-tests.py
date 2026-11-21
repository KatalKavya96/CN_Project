#!/usr/bin/env python3
"""Test both client/edge Macs with the selected backup DNS and restore service."""
from datetime import datetime, timezone
import argparse
from pathlib import Path
import shlex
import signal
import subprocess
import time
from dns_control import augment_lab, control_commands

ROOT = Path(__file__).resolve().parent.parent
REMOTE_ROOT = "/Users/ronitsingh/Desktop/CN_Project"
parser = argparse.ArgumentParser()
parser.add_argument("--only", choices=["cutover"])
parser.add_argument("--out-dir", default="evidence/phase-2/mac3-dns/final-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"))
args = parser.parse_args()
OUT = ROOT / args.out_dir
OUT.mkdir(parents=True, exist_ok=True)
env = dict(line.split("=", 1) for line in (ROOT / "phase2/lab.env").read_text().splitlines()
           if line and not line.startswith("#"))
env = augment_lab(ROOT, env)
SSH = ["/usr/bin/ssh", "-i", str(Path.home() / ".ssh/id_ed25519_cn_project"),
       "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=yes",
       "-o", "UserKnownHostsFile=/private/tmp/cn-project-ronit-known-hosts", "ronitsingh@" + env["MAC2_IP"]]
HELPER = ["sudo", "-n", "/usr/local/sbin/cn-project-admin"]
failures = []

def run(mac, command, filename, expected=0, timeout=45):
    actual = command if mac == 1 else SSH + ["cd " + shlex.quote(REMOTE_ROOT) + " && " + shlex.join(command)]
    started = datetime.now(timezone.utc).isoformat()
    try:
        result = subprocess.run(actual, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        result = subprocess.CompletedProcess(actual, 124,
            error.stdout.decode() if isinstance(error.stdout, bytes) else error.stdout or "",
            "TIMEOUT after " + str(timeout) + " seconds")
    with (OUT / filename).open("a") as log:
        log.write(f"\nUTC: {started}\nMac {mac}\nCommand: {shlex.join(command)}\nExit: {result.returncode}\n")
        log.write(result.stdout + "\n" + result.stderr + "\n")
    if expected is not None and result.returncode != expected:
        raise RuntimeError(f"Mac {mac}: {filename}: exit {result.returncode}, expected {expected}")
    return result

def admin(mac, action, filename="admin-actions.txt"):
    for target, command in control_commands(env, mac, action):
        result = run(target, command, filename)
    return result

def https(mac, filename, edge=None):
    root = str(ROOT) if mac == 1 else REMOTE_ROOT
    command = ["/usr/bin/curl", "--noproxy", "*", "--http1.1", "--cacert", root + "/.runtime/ca.crt",
               "--connect-timeout", "10", "--max-time", "35", "-sS", "-i"]
    if edge:
        command += ["--resolve", "app.cn-project.test:8443:" + edge]
    return run(mac, command + ["https://app.cn-project.test:8443/api/status"], filename)

def require_edge(mac, edge, filename):
    result = https(mac, filename)
    assert result.stdout.startswith("HTTP/1.1 200"), result.stdout
    assert "X-Edge: " + edge in result.stdout, "Unexpected serving edge"

def balancing(mac, expected, filename):
    seen = set()
    for _ in range(8):
        result = https(mac, filename)
        assert result.stdout.startswith("HTTP/1.1 200"), "HTTP request failed"
        for line in result.stdout.splitlines():
            if line.lower().startswith("x-backend:"):
                seen.add(line.split(":", 1)[1].strip())
    assert seen == expected, "Observed backends " + repr(seen)

def case(name, function):
    print("RUN " + name, flush=True)
    try:
        function()
        print("PASS " + name, flush=True)
    except Exception as error:
        failures.append(name + ": " + str(error))
        print("FAIL " + failures[-1], flush=True)

def baseline():
    for mac in (1, 2):
        admin(mac, "dns-primary")
        admin(mac, "dns-start")
        admin(mac, "firewall-off")
        admin(mac, "cache-flush")
        run(mac, ["/usr/sbin/scutil", "--dns"], f"mac{mac}-resolver.txt")
        run(mac, ["/usr/bin/dscacheutil", "-q", "host", "-a", "name", "app.cn-project.test"], "baseline-os-lookups.txt")
        balancing(mac, {"A", "B"}, "baseline-by-name.txt")

def dns_failover():
    try:
        admin(1, "dns-stop")
        time.sleep(1)
        direct = run(2, ["/usr/bin/dig", "@" + env["MAC1_IP"], "app.cn-project.test", "+time=1", "+tries=1"],
                     "primary-stopped-direct-query.txt", expected=None)
        assert direct.returncode != 0, "Primary DNS still answers"
        for mac in (1, 2):
            admin(mac, "cache-flush", "failover-cache-flush.txt")
            result = run(mac, ["/usr/bin/dscacheutil", "-q", "host", "-a", "name", "app.cn-project.test"],
                         "primary-down-os-lookup.txt")
            assert env["MAC2_IP"] in result.stdout, "OS lookup did not resolve through backup"
            require_edge(mac, "mac2", "primary-down-by-name-https.txt")
        admin(2, "dns-status", "backup-query-log.txt")
    finally:
        admin(1, "dns-start", "primary-restored.txt")
        for mac in (1, 2):
            admin(mac, "cache-flush", "primary-restored.txt")

def cutover():
    try:
        for mac in (1, 2):
            admin(mac, "cache-flush", "cutover-prime.txt")
            require_edge(mac, "mac2", "cutover-prime.txt")
        for mac in (1, 2):
            admin(mac, "dns-standby", "cutover-actions.txt")
        time.sleep(1)
        for server in (env["MAC1_IP"], env["BACKUP_DNS_IP"]):
            result = run(1, ["/usr/bin/dig", "@" + server, "app.cn-project.test", "+time=2", "+tries=1"], "cutover-authoritative.txt")
            assert env["MAC1_IP"] in result.stdout.split("ANSWER SECTION:")[-1]
        for mac in (1, 2):
            run(mac, ["/usr/bin/dscacheutil", "-q", "host", "-a", "name", "app.cn-project.test"], "cutover-immediate-os-cache.txt")
            https(mac, "cutover-immediate-by-name.txt")
        admin(2, "cache-flush", "cutover-fresh-client-flush.txt")
        require_edge(2, "mac1", "cutover-fresh-client-by-name.txt")
        print("Waiting 35 seconds for the 30-second DNS TTL...", flush=True)
        time.sleep(35)
        for mac in (1, 2):
            # Some macOS lookups return one stale answer while triggering refresh.
            # Record polling results instead of assuming one exact OS expiry instant.
            deadline = time.monotonic() + 60
            while True:
                result = run(mac, ["/usr/bin/dscacheutil", "-q", "host", "-a", "name", "app.cn-project.test"], "cutover-after-ttl-os-cache.txt")
                if env["MAC1_IP"] in result.stdout:
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"Mac {mac} has not adopted standby after TTL plus refresh window")
                time.sleep(2)
            require_edge(mac, "mac1", "cutover-after-ttl-by-name.txt")
        for mac in (1, 2):
            admin(mac, "dns-primary", "cutover-restore.txt")
        for mac in (1, 2):
            admin(mac, "cache-flush", "cutover-restore.txt")
            require_edge(mac, "mac2", "cutover-restored-by-name.txt")
    finally:
        for mac in (1, 2):
            admin(mac, "dns-primary", "cutover-final-restore.txt")
            admin(mac, "cache-flush", "cutover-final-restore.txt")

def ha():
    try:
        run(2, ["/usr/bin/python3", "phase2/services.py", "stop", "a"], "backend-a-stop.txt")
        for mac in (1, 2):
            balancing(mac, {"B"}, "backend-a-down-by-name.txt")
    finally:
        run(2, ["/usr/bin/python3", "phase2/services.py", "start", "a"], "backend-a-start.txt")
    time.sleep(6)
    for mac in (1, 2):
        balancing(mac, {"A", "B"}, "backend-a-restored-by-name.txt")

def isolation():
    try:
        for mac in (1, 2):
            admin(mac, "firewall-on", "isolation-rules.txt")
        blocked = run(1, ["/usr/bin/curl", "--noproxy", "*", "--connect-timeout", "3", "--max-time", "4",
                          "-i", "http://" + env["MAC2_IP"] + ":3001/api/status"], "isolation-blocked-client.txt", expected=None)
        assert blocked.returncode != 0, "Direct backend A access was not blocked"
        for url in ("http://127.0.0.1:3001/api/status", "http://" + env["MAC1_IP"] + ":3002/api/status"):
            result = run(2, ["/usr/bin/curl", "--noproxy", "*", "--connect-timeout", "3", "--max-time", "5", "-sS", "-i", url], "isolation-allowed-edge.txt")
            assert "200 OK" in result.stdout
        for mac in (1, 2):
            balancing(mac, {"A", "B"}, "isolation-https-by-name.txt")
            admin(mac, "firewall-status", "isolation-counters.txt")
    finally:
        for mac in (1, 2):
            admin(mac, "firewall-off", "isolation-rollback.txt")

def final_health():
    for mac in (1, 2):
        admin(mac, "dns-primary")
        admin(mac, "dns-start")
        admin(mac, "firewall-off")
        admin(mac, "cache-flush")
        balancing(mac, {"A", "B"}, "final-by-name-health.txt")

capture_log = (OUT / "packet-capture.log").open("w")
capture = subprocess.Popen(["/usr/sbin/tcpdump", "-i", "en0", "-n", "-s", "0", "-U", "-w",
                            str(OUT / "dns-failover-cutover.pcap"),
                            "(host " + env["MAC2_IP"] + " or host " + env["BACKUP_DNS_IP"] + ") and (port 53 or port 8443)"],
                           stdout=capture_log, stderr=capture_log)
try:
    groups = [("by-name baseline on both Macs", baseline), ("primary DNS stop and OS failover", dns_failover),
                           ("OS cache TTL and DNS edge migration", cutover), ("by-name backend failover and recovery", ha),
                           ("backend isolation and rollback", isolation), ("final by-name health", final_health)]
    if args.only == "cutover":
        groups = [("OS cache TTL and DNS edge migration", cutover)]
    for name, function in groups:
        case(name, function)
finally:
    if capture.poll() is None:
        capture.send_signal(signal.SIGINT)
    capture.wait(timeout=5)
    capture_log.close()
summary = "UTC: " + datetime.now(timezone.utc).isoformat() + "\n" + ("PASSED: " + "; ".join(name for name, _ in groups) + "\n" if not failures else "FAILURES:\n" + "\n".join(failures) + "\n")
(OUT / "summary.txt").write_text(summary)
print(summary, flush=True)
raise SystemExit(bool(failures))
