#!/usr/bin/env python3
"""Start and stop only the project's backend processes, with owned PID files."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument("action", choices=["start", "stop", "status"])
parser.add_argument("backend", choices=["a", "b"])
args = parser.parse_args()
runtime = ROOT / ".runtime"
runtime.mkdir(exist_ok=True)
name = "backend-" + args.backend
pidfile = runtime / (name + ".pid")
pid = int(pidfile.read_text()) if pidfile.exists() else None
command = subprocess.run(["/bin/ps", "-p", str(pid or 0), "-o", "command="],
                         capture_output=True, text=True).stdout
alive = str(ROOT / name / "app.py") in command
if args.action == "status":
    print(name, "running" if alive else "stopped", pid)
elif args.action == "stop":
    if alive:
        os.kill(pid, signal.SIGTERM)
    pidfile.unlink(missing_ok=True)
    print(name, "stopped")
elif alive:
    print(name, "already running", pid)
else:
    with (runtime / (name + ".log")).open("ab") as log:
        child = subprocess.Popen(["/usr/bin/python3", str(ROOT / name / "app.py")],
                                 cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log,
                                 stderr=log, start_new_session=True, close_fds=True)
    time.sleep(0.4)
    if child.poll() is not None:
        raise SystemExit("Backend did not start; check " + str(runtime / (name + ".log")))
    pidfile.write_text(str(child.pid) + "\n")
    print(name, "started", child.pid)
