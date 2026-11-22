#!/usr/bin/env python3
"""Run nginx in foreground mode for a local terminal or persistent SSH session."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
runtime = ROOT / ".runtime"
config = str(runtime / "nginx.conf")
nginx = "/opt/homebrew/bin/nginx"
subprocess.run([nginx, "-t", "-c", config], check=True)
pidfile = runtime / "nginx.pid"
pid_text = pidfile.read_text().strip() if pidfile.exists() else ""
if pid_text.isdigit():
    pid = int(pid_text)
    command = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "command="],
                             capture_output=True, text=True).stdout
    if config in command:
        raise SystemExit("Project nginx already running; quit it before changing launch mode")
print("Starting foreground nginx; keep this terminal or SSH session running.", flush=True)
raise SystemExit(subprocess.call([nginx, "-c", config, "-g", "daemon off;"]))
