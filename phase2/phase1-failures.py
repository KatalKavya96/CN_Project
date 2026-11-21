#!/usr/bin/env python3
"""Collect the three outstanding Phase 1 failure demonstrations on both Macs."""
from datetime import datetime, timezone
from pathlib import Path
import json
import shlex
import subprocess
import time
from dns_control import augment_lab, control_commands

ROOT = Path(__file__).resolve().parent.parent
REMOTE_ROOT = "/Users/ronitsingh/Desktop/CN_Project"
OUT = ROOT / "evidence/phase-1" / datetime.now(timezone.utc).strftime("failures-%Y%m%dT%H%M%S")
OUT.mkdir(parents=True, exist_ok=True)
env = dict(line.split("=", 1) for line in (ROOT / "phase2/lab.env").read_text().splitlines()
           if line and not line.startswith("#"))
env = augment_lab(ROOT, env)
SSH = ["/usr/bin/ssh", "-i", str(Path.home() / ".ssh/id_ed25519_cn_project"),
       "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=yes",
       "-o", "UserKnownHostsFile=/private/tmp/cn-project-ronit-known-hosts", "ronitsingh@" + env["MAC2_IP"]]
HELPER = ["sudo", "-n", "/usr/local/sbin/cn-project-admin"]
results = {}

def run(mac, command, filename, expected=0, timeout=30):
    actual = command if mac == 1 else SSH + ["cd " + shlex.quote(REMOTE_ROOT) + " && " + shlex.join(command)]
    result = subprocess.run(actual, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    with (OUT / filename).open("a") as log:
        log.write("\nUTC: " + datetime.now(timezone.utc).isoformat() + f"\nMac {mac}\nCommand: " + shlex.join(command) +
                  f"\nExit: {result.returncode}\n" + result.stdout + "\n" + result.stderr + "\n")
    if expected is not None and result.returncode != expected:
        raise RuntimeError(f"Mac {mac}, {filename}: exit {result.returncode}")
    return result

def admin(mac, action, filename="restoration.txt"):
    for target, command in control_commands(env, mac, action):
        result = run(target, command, filename)
    return result

def request(mac, filename, edge=None, failure=False):
    command = ["/usr/bin/curl", "--noproxy", "*", "--http1.1", "--connect-timeout", "4", "--max-time", "12", "-v", "-i"]
    if edge:
        command += ["--resolve", "app.cn-project.test:8443:" + edge]
    command += ["https://app.cn-project.test:8443/api/status"]
    return run(mac, command, filename, expected=None if failure else 0)

def healthy(mac, filename):
    result = request(mac, filename)
    assert result.stdout.startswith("HTTP/1.1 200"), "Expected healthy HTTP 200"
    assert "SSL certificate verify ok." in result.stderr, "TLS verification not recorded"
    assert "X-Edge: mac2" in result.stdout

def dns_answer(mac, filename, expected_ip):
    result = run(mac, ["/usr/bin/dig", "@" + env["MAC1_IP"], "app.cn-project.test", "+time=2", "+tries=1"], filename)
    answers = [line.split()[-1] for line in result.stdout.splitlines()
               if line.startswith("app.cn-project.test.") and "\tA\t" in line]
    assert expected_ip in answers, "Unexpected DNS A answer: " + repr(answers)

def restore_dns():
    for mac in (1, 2):
        admin(mac, "dns-primary")
    for mac in (1, 2):
        admin(mac, "cache-flush")

def wrong_dns():
    for mac in (1, 2):
        filename = f"wrong-dns-mac{mac}.txt"
        run(mac, ["/usr/bin/python3", "phase2/wrong-dns-client.py"], filename)
        other = env["MAC2_IP"] if mac == 1 else env["MAC1_IP"]
        run(mac, ["/sbin/ping", "-c", "2", other], filename)
        result = request(mac, filename, edge=env["MAC2_IP"])
        assert result.stdout.startswith("HTTP/1.1 200")
        assert "SSL certificate verify ok." in result.stderr
        dns_answer(mac, filename, env["MAC2_IP"])
        healthy(mac, filename)
        results[f"wrong_dns_mac{mac}"] = "PASS (client-scoped resolver; system DNS unchanged)"

def wrong_record():
    nginx = "/opt/homebrew/bin/nginx"
    config = str(ROOT / ".runtime/nginx.conf")
    try:
        run(1, [nginx, "-s", "quit", "-c", config], "wrong-record-preparation.txt")
        time.sleep(1)
        closed = run(2, ["/usr/bin/nc", "-vz", "-G", "2", env["MAC1_IP"], "8443"], "wrong-record-preparation.txt", expected=None)
        assert closed.returncode != 0, "Standby edge still listening"
        for mac in (1, 2):
            admin(mac, "dns-standby", "wrong-record-actions.txt")
        for mac in (1, 2):
            admin(mac, "cache-flush", "wrong-record-actions.txt")
        for mac in (1, 2):
            filename = f"wrong-record-mac{mac}.txt"
            dns_answer(mac, filename, env["MAC1_IP"])
            lookup = run(mac, ["/usr/bin/dscacheutil", "-q", "host", "-a", "name", "app.cn-project.test"], filename)
            assert env["MAC1_IP"] in lookup.stdout
            failed = request(mac, filename, failure=True)
            assert failed.returncode in (7, 28), "Expected TCP failure to wrong edge address"
            assert env["MAC1_IP"] in failed.stderr, "Client did not attempt the wrong DNS destination"
            correct = request(mac, filename, edge=env["MAC2_IP"])
            assert correct.stdout.startswith("HTTP/1.1 200")
            assert "SSL certificate verify ok." in correct.stderr
            results[f"wrong_record_mac{mac}"] = "PASS"
    finally:
        restore_dns()
        run(1, [nginx, "-c", config], "wrong-record-restoration.txt")
        for mac in (1, 2):
            healthy(mac, "wrong-record-restoration.txt")

def both_backends():
    try:
        run(1, ["/usr/bin/python3", "phase2/services.py", "stop", "b"], "both-backends-actions.txt")
        run(2, ["/usr/bin/python3", "phase2/services.py", "stop", "a"], "both-backends-actions.txt")
        time.sleep(0.5)
        for mac in (1, 2):
            filename = f"both-backends-down-mac{mac}.txt"
            dns_answer(mac, filename, env["MAC2_IP"])
            result = request(mac, filename)
            assert result.stdout.startswith("HTTP/1.1 502"), "Expected HTTP 502 with both backends stopped"
            assert "SSL certificate verify ok." in result.stderr
            assert "X-Edge: mac2" in result.stdout
            results[f"both_backends_mac{mac}"] = "PASS"
    finally:
        run(1, ["/usr/bin/python3", "phase2/services.py", "start", "b"], "both-backends-restoration.txt")
        run(2, ["/usr/bin/python3", "phase2/services.py", "start", "a"], "both-backends-restoration.txt")
        time.sleep(6)
        for mac in (1, 2):
            seen = set()
            for _ in range(8):
                response = request(mac, "both-backends-restoration.txt")
                assert response.stdout.startswith("HTTP/1.1 200")
                seen.update(line.split(":", 1)[1].strip() for line in response.stdout.splitlines()
                            if line.lower().startswith("x-backend:"))
            assert seen == {"A", "B"}, "A/B load balancing not restored"
            results[f"restored_mac{mac}"] = "PASS (plain HTTPS and A/B)"

try:
    for mac in (1, 2):
        healthy(mac, "baseline.txt")
    for title, function in [("wrong client DNS", wrong_dns), ("wrong DNS record", wrong_record),
                            ("both backends stopped", both_backends)]:
        print("RUN", title, flush=True)
        function()
        print("PASS", title, "on both Macs", flush=True)
finally:
    restore_dns()
    (OUT / "summary.json").write_text(json.dumps({"utc": datetime.now(timezone.utc).isoformat(), "results": results}, indent=2) + "\n")
print(json.dumps(results, indent=2), flush=True)
