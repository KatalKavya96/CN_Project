"""Route DNS-only controls to the selected backup; edge/backend roles stay fixed."""
from pathlib import Path
import shlex

ROOT = Path(__file__).resolve().parent.parent
HELPER = ["sudo", "-n", "/usr/local/sbin/cn-project-admin"]

def augment_lab(root, values):
    values = dict(values)
    candidate = root / "phase2/mac3.env"
    if candidate.exists():
        values.update(line.split("=", 1) for line in candidate.read_text().splitlines()
                      if line and not line.startswith("#"))
    values.setdefault("BACKUP_DNS_IP", values["MAC2_IP"])
    return values

def mac3_active(values):
    return values.get("BACKUP_DNS_IP") == values.get("MAC3_IP")

def mac3_command(values, action):
    return ["/usr/bin/ssh", "-i", str(Path.home() / ".ssh/id_ed25519_cn_project"),
            "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=yes",
            "-o", "UserKnownHostsFile=" + str(ROOT / "phase2/ssh-known-hosts"),
            values["MAC3_USER"] + "@" + values["MAC3_IP"],
            shlex.join(["sudo", "-n", "/usr/local/sbin/cn-project-backup", action])]

def control_commands(values, mac, action):
    # Commands targeting Mac 3 originate from the orchestrator on Kavya's Mac.
    # Keep retired Mac 2's records aligned for rollback, without restarting it.
    if mac3_active(values) and mac == 2 and action.startswith("dns-"):
        commands = [(1, mac3_command(values, action))]
        if action in ("dns-primary", "dns-standby"):
            commands.append((2, HELPER + [action]))
        return commands
    return [(mac, HELPER + [action])]
