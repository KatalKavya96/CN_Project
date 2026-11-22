#!/usr/bin/env python3
"""Save real curl headers, bodies, timestamps and exit status for the demo."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument("--edge", help="Explicit destination for DNS-independent HTTPS")
parser.add_argument("--count", type=int, default=6)
parser.add_argument("--out", required=True)
parser.add_argument("--expect", choices=["A", "B", "both"])
args = parser.parse_args()
command = ["/usr/bin/curl", "--http1.1", "--noproxy", "*", "--cacert",
           str(ROOT / ".runtime/ca.crt"), "--connect-timeout", "3", "--max-time", "12", "-sS", "-i"]
if args.edge:
    command += ["--resolve", "app.cn-project.test:8443:" + args.edge]
command += ["https://app.cn-project.test:8443/api/status"]
lines = ["UTC: " + datetime.now(timezone.utc).isoformat(),
         "Mode: " + ("explicit edge; DNS bypassed" if args.edge else "OS DNS resolver"),
         "Command: " + shlex.join(command)]
seen = set()
failed = False
for index in range(args.count):
    result = subprocess.run(command, capture_output=True, text=True)
    lines += [f"\nRequest {index + 1}; exit={result.returncode}", result.stdout, result.stderr]
    failed |= result.returncode != 0 or not result.stdout.startswith("HTTP/1.1 200")
    for header in result.stdout.splitlines():
        if header.lower().startswith("x-backend:"):
            seen.add(header.split(":", 1)[1].strip())
if args.expect:
    expected = {"A", "B"} if args.expect == "both" else {args.expect}
    failed |= seen != expected
lines += ["Observed backends: " + ", ".join(sorted(seen)), "Result: " + ("FAIL" if failed else "PASS")]
output = "\n".join(lines) + "\n"
destination = ROOT / args.out
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(output)
print(output)
sys.exit(1 if failed else 0)
