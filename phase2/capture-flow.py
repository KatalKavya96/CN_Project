#!/usr/bin/env python3
"""Capture an explicit backup-DNS lookup followed by verified HTTPS to its answer."""
from datetime import datetime, timezone
from pathlib import Path
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent
env = dict(line.split("=", 1) for line in (ROOT / "phase2/lab.env").read_text().splitlines()
           if line and not line.startswith("#"))
destination = ROOT / "evidence/phase-2/baseline"
destination.mkdir(parents=True, exist_ok=True)
pcap = destination / "dns-tcp-tls-current.pcap"
with (destination / "capture-tool.log").open("w") as tool_log:
    capture = subprocess.Popen(["/usr/sbin/tcpdump", "-i", env["LAB_INTERFACE"],
                                "-n", "-s", "0", "-U", "-w", str(pcap),
                                "host", env["MAC2_IP"], "and", "(port 53 or port 8443)"],
                               stdout=tool_log, stderr=tool_log)
    try:
        time.sleep(1)
        if capture.poll() is not None:
            raise SystemExit("Packet capture failed; inspect capture-tool.log")
        lookup = subprocess.run(["/usr/bin/dig", "@" + env["MAC2_IP"],
                                 "app.cn-project.test", "+time=2", "+tries=1"],
                                capture_output=True, text=True, check=True)
        answer_lines = [line for line in lookup.stdout.splitlines()
                        if line.startswith("app.cn-project.test.") and "\tA\t" in line]
        if not answer_lines:
            raise SystemExit("DNS did not return an A record")
        edge = answer_lines[0].split()[-1]
        if edge not in (env["MAC1_IP"], env["MAC2_IP"]):
            raise SystemExit("Unexpected DNS destination")
        command = ["/usr/bin/curl", "--noproxy", "*", "--http1.1", "--cacert",
                   str(ROOT / ".runtime/ca.crt"), "--resolve", "app.cn-project.test:8443:" + edge,
                   "--connect-timeout", "3", "--max-time", "10", "-v",
                   "https://app.cn-project.test:8443/api/status"]
        result = subprocess.run(command, capture_output=True, text=True)
        (destination / "capture-request.txt").write_text(
            "UTC: " + datetime.now(timezone.utc).isoformat() +
            "\nExplicit DNS lookup followed by HTTPS to the returned address.\n"
            "This is protocol evidence, not proof of OS cache or resolver failover.\n\n" +
            lookup.stdout + "\n" + result.stderr + "\n" + result.stdout)
        time.sleep(1)
        if result.returncode:
            raise SystemExit(result.returncode)
    finally:
        if capture.poll() is None:
            capture.send_signal(signal.SIGINT)
        capture.wait(timeout=5)
print("Saved", pcap)
