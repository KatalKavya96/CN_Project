#!/usr/bin/env python3
"""Measure DNS TTL/cutover with an isolated client DNS cache on UDP/TCP 1053.

This tests a real caching resolver on Mac 1, not the macOS system resolver.
"""
from datetime import datetime, timezone
import os
from pathlib import Path
import signal
import subprocess
import time
from dns_control import augment_lab, mac3_active, mac3_command

ROOT = Path(__file__).resolve().parent.parent
env = dict(line.split("=", 1) for line in (ROOT / "phase2/lab.env").read_text().splitlines()
           if line and not line.startswith("#"))
env = augment_lab(ROOT, env)
runtime = ROOT / ".runtime"
out = ROOT / "evidence/phase-2/ttl/client-cache-and-cutover.txt"
if mac3_active(env):
    out = ROOT / "evidence/phase-2/mac3-dns" / datetime.now(timezone.utc).strftime("ttl-%Y%m%dT%H%M%S") / "client-cache-and-cutover.txt"
out.parent.mkdir(parents=True, exist_ok=True)
ssh = ["/usr/bin/ssh", "-i", str(Path.home() / ".ssh/id_ed25519_cn_project"),
       "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=yes",
       "-o", "UserKnownHostsFile=/private/tmp/cn-project-ronit-known-hosts",
       "ronitsingh@" + env["MAC2_IP"]]
helper = ["sudo", "-n", "/usr/local/sbin/cn-project-admin"]
events = []

def record(text):
    line = datetime.now(timezone.utc).isoformat() + " " + text
    print(line, flush=True)
    events.append(line)
    out.write_text("\n".join(events) + "\n")

def run(command):
    result = subprocess.run(command, capture_output=True, text=True, timeout=15)
    record("command=" + repr(command) + "\n" + result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError("Command failed: " + str(result.returncode))
    return result.stdout

def change(action):
    if mac3_active(env):
        run(mac3_command(env, action))
    run(ssh + ["sudo -n /usr/local/sbin/cn-project-admin " + action])
    run(helper + [action])
    time.sleep(0.4)

def lookup(cached=True):
    command = ["/usr/bin/dig", "@127.0.0.1", "-p", "1053"] if cached else ["/usr/bin/dig", "@" + env["BACKUP_DNS_IP"]]
    text = run(command + ["app.cn-project.test", "+time=2", "+tries=1"])
    answers = [line.split() for line in text.splitlines()
               if line.startswith("app.cn-project.test.") and "\tA\t" in line]
    if not answers:
        raise RuntimeError("Missing DNS A answer")
    ip, ttl = answers[0][-1], int(answers[0][1])
    record(f"DNS answer={ip} TTL={ttl} cached={cached}")
    return ip

def https(ip, expected):
    text = run(["/usr/bin/curl", "--noproxy", "*", "--http1.1", "--cacert", str(runtime / "ca.crt"),
                "--resolve", "app.cn-project.test:8443:" + ip, "--connect-timeout", "3", "--max-time", "10",
                "-sS", "-i", "https://app.cn-project.test:8443/api/status"])
    if "X-Edge: " + expected not in text or not text.startswith("HTTP/1.1 200"):
        raise RuntimeError("Unexpected edge response")

cache = None
try:
    record("Client caching resolver: dnsmasq on Mac 1 127.0.0.1:1053; upstream backup DNS. This is NOT the macOS OS-cache test.")
    change("dns-primary")
    with (runtime / "client-cache.log").open("w") as log:
        cache = subprocess.Popen(["/opt/homebrew/sbin/dnsmasq", "--keep-in-foreground", "--port=1053",
                                  "--listen-address=127.0.0.1", "--bind-interfaces", "--no-resolv", "--no-hosts",
                                  "--server=/cn-project.test/" + env["BACKUP_DNS_IP"], "--cache-size=100"],
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=log)
    time.sleep(0.5)
    if cache.poll() is not None:
        raise RuntimeError("Client cache failed to start")
    assert lookup() == env["MAC2_IP"]
    change("dns-standby")
    assert lookup(False) == env["MAC1_IP"]
    old = lookup()
    assert old == env["MAC2_IP"], "Old cached answer was not retained"
    https(old, "mac2")
    https(lookup(False), "mac1")
    record("PASS: cached client still reaches old edge; fresh DNS client reaches standby edge")
    for seconds in range(0, 35, 5):
        time.sleep(5)
        lookup()
    assert lookup() == env["MAC1_IP"]
    record("PASS: expired cached answer adopted standby address")
    change("dns-primary")
    assert lookup() == env["MAC1_IP"], "Expected standby answer still cached before manual flush"
    cache.send_signal(signal.SIGHUP)
    time.sleep(0.4)
    assert lookup() == env["MAC2_IP"]
    https(lookup(), "mac2")
    record("PASS: manual client DNS-cache flush immediately adopted restored primary edge")
finally:
    restore_commands = [ssh + ["sudo -n /usr/local/sbin/cn-project-admin dns-primary"], helper + ["dns-primary"]]
    if mac3_active(env):
        restore_commands.insert(0, mac3_command(env, "dns-primary"))
    for command in restore_commands:
        result = subprocess.run(command, capture_output=True, text=True, timeout=15)
        record("Restore primary records: " + str(result.returncode) + "\n" + result.stdout + result.stderr)
    if cache is not None and cache.poll() is None:
        cache.terminate()
        cache.wait(timeout=5)
