#!/usr/bin/env python3
"""Client-scoped wrong DNS experiment; never changes macOS resolver settings."""
from datetime import datetime, timezone
from pathlib import Path
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent
runtime = ROOT / ".runtime"
config = runtime / "phase1-wrong-client-dns.conf"
logfile = runtime / "phase1-wrong-client-dns.log"
config.write_text("port=1053\nlisten-address=127.0.0.1\nbind-interfaces\n"
                  "no-resolv\nno-hosts\nserver=127.0.0.2\ncache-size=0\n"
                  "log-queries\nlog-facility=-\n")
print("UTC:", datetime.now(timezone.utc).isoformat(), flush=True)
print("SCOPE: temporary client resolver; macOS system resolver remains unchanged.", flush=True)
print("Wrong configured upstream: 127.0.0.2:53; local client endpoint: 127.0.0.1:1053", flush=True)
print(config.read_text(), flush=True)
process = None
try:
    with logfile.open("w") as log:
        process = subprocess.Popen(["/opt/homebrew/sbin/dnsmasq", "--keep-in-foreground", "--conf-file=" + str(config)],
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        time.sleep(0.6)
        if process.poll() is not None:
            raise RuntimeError("Client resolver could not start")
        command = ["/usr/bin/dig", "@127.0.0.1", "-p", "1053", "app.cn-project.test", "+time=2", "+tries=1"]
        print("COMMAND:", " ".join(command), flush=True)
        result = subprocess.run(command, capture_output=True, text=True, timeout=8)
        print(result.stdout + result.stderr, flush=True)
        print("DNS query exit:", result.returncode, flush=True)
        # A timeout, refused reply or SERVFAIL proves this resolver cannot resolve.
        answer = any(line.startswith("app.cn-project.test.") and "\tA\t" in line for line in result.stdout.splitlines())
        if answer:
            raise RuntimeError("Wrong DNS unexpectedly returned a project A record")
finally:
    if process is not None and process.poll() is None:
        process.send_signal(signal.SIGTERM)
        process.wait(timeout=5)
    print("FORWARDING LOG:\n" + logfile.read_text(), flush=True)
print("PASS: the wrongly configured client resolver did not resolve the project name; temporary resolver stopped.", flush=True)
