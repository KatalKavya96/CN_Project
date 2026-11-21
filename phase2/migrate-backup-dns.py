#!/usr/bin/env python3
"""Activate the staged DNS-only migration, rolling back on any failed check."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'evidence/phase-2/mac3-dns' / datetime.now(timezone.utc).strftime('migration-%Y%m%dT%H%M%S')
OUT.mkdir(parents=True, exist_ok=False)
HOSTS = {2: 'ronitsingh@10.7.18.166', 3: 'priyanshutomar@10.7.26.237'}
OLD = '/usr/local/sbin/cn-project-admin'
SWITCH = '/usr/local/sbin/cn-project-resolver'
NEW = '/usr/local/sbin/cn-project-backup'
before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in (ROOT / 'evidence').rglob('*') if p.is_file() and OUT not in p.parents}
(OUT / 'prior-evidence-sha256.json').write_text(json.dumps(before, indent=2) + '\n')

def run(mac, command, check=True, timeout=60):
    actual = command
    if mac != 1:
        actual = ['ssh', '-i', str(Path.home() / '.ssh/id_ed25519_cn_project'),
                  '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', '-o', 'StrictHostKeyChecking=yes',
                  '-o', 'UserKnownHostsFile=' + str(ROOT / 'phase2/ssh-known-hosts'),
                  HOSTS[mac], shlex.join(command)]
    result = subprocess.run(actual, capture_output=True, text=True, timeout=timeout)
    with (OUT / 'commands.txt').open('a') as log:
        log.write(f'\nUTC: {datetime.now(timezone.utc).isoformat()}\nMac {mac}: {shlex.join(command)}\nExit: {result.returncode}\n{result.stdout}\n{result.stderr}\n')
    if check and result.returncode:
        raise RuntimeError(f'Mac {mac}: {shlex.join(command)} failed ({result.returncode})')
    return result

def admin(mac, action, helper=OLD):
    return run(mac, ['sudo', '-n', helper, action])

def healthy(mac):
    for name in ('app', 'api'):
        result = run(mac, ['dscacheutil', '-q', 'host', '-a', 'name', name + '.cn-project.test'])
        assert '10.7.18.166' in result.stdout, 'OS DNS resolution failed'
        result = run(mac, ['curl', '--noproxy', '*', '--connect-timeout', '10', '--max-time', '35',
                           '-sS', '-i', 'https://' + name + '.cn-project.test:8443/api/status'])
        assert result.stdout.startswith('HTTP/1.1 200'), 'Plain HTTPS failed'
        assert 'X-Edge: mac2' in result.stdout, 'Unexpected edge'

activated = False
try:
    for mac in (1, 2):
        admin(mac, 'status', SWITCH)
        healthy(mac)
        for name in ('app', 'api'):
            for protocol in ([], ['+tcp']):
                result = run(mac, ['dig', '@10.7.26.237', name + '.cn-project.test',
                                   '+noall', '+answer', '+time=2', '+tries=1'] + protocol)
                assert '10.7.18.166' in result.stdout and '\t30\t' in result.stdout, 'Candidate DNS answer/TTL incorrect'
    for mac in (1, 2):
        admin(mac, 'dns-primary')
    admin(3, 'dns-primary', NEW)
    admin(3, 'dns-start', NEW)
    for mac in (1, 2):
        result = admin(mac, 'use-mac3', SWITCH)
        assert result.stdout.splitlines() == ['nameserver 10.7.26.228', 'nameserver 10.7.26.237']
    # Retain the original backup until the first primary-down test succeeds.
    for retire_legacy in (False, True):
        if retire_legacy:
            admin(2, 'dns-stop')
        admin(1, 'dns-stop')
        time.sleep(1)
        for server in ('10.7.26.228', '10.7.18.166') if retire_legacy else ('10.7.26.228',):
            result = run(1, ['dig', '@' + server, 'app.cn-project.test', '+time=1', '+tries=1'], check=False)
            assert result.returncode != 0, 'Retired/stopped DNS still answering: ' + server
        for mac in (1, 2):
            admin(mac, 'cache-flush')
            healthy(mac)
        admin(3, 'dns-status', NEW)
        admin(1, 'dns-start')
    for mac in (1, 2):
        admin(mac, 'cache-flush')
        healthy(mac)
        run(mac, ['scutil', '--dns'])
    activated = True
finally:
    # Always restore primary DNS. On failure also restore both original resolvers
    # and legacy backup; no existing edge/backend/firewall service is changed.
    restores = [(1, 'dns-primary', OLD), (1, 'dns-start', OLD)]
    if not activated:
        restores += [(2, 'dns-primary', OLD), (2, 'dns-start', OLD),
                     (1, 'use-mac2', SWITCH), (2, 'use-mac2', SWITCH)]
    errors = []
    for mac, action, helper in restores:
        try:
            admin(mac, action, helper)
        except Exception as error:
            errors.append(str(error))
    changed = [name for name, digest in before.items()
               if not (ROOT / name).exists() or hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest]
    summary = {'activated_mac3': activated, 'legacy_mac2_dns_stopped': activated,
               'prior_evidence_files': len(before), 'prior_evidence_changed': changed,
               'restoration_errors': errors}
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(str(OUT), json.dumps(summary), flush=True)
    if errors or changed:
        raise RuntimeError('Restoration/evidence verification needs attention')
