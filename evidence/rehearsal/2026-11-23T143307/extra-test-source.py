from datetime import datetime, timezone
from pathlib import Path
import json
import shlex
import subprocess
import sys
import time

ROOT = Path('/Users/kavyakatal/Desktop/CN_Project')
OUT = Path(sys.argv[1]) / 'extra-cases'
OUT.mkdir(parents=True, exist_ok=False)
HOSTS = {2: 'ronitsingh@10.7.18.166', 3: 'priyanshutomar@10.7.26.237'}
OLD = '/usr/local/sbin/cn-project-admin'
NEW = '/usr/local/sbin/cn-project-backup'
results = {}

def run(mac, cmd, timeout=25):
    actual = cmd
    if mac != 1:
        actual = ['ssh', '-i', str(Path.home()/'.ssh/id_ed25519_cn_project'),
                  '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', '-o', 'StrictHostKeyChecking=yes',
                  '-o', 'UserKnownHostsFile=' + str(ROOT/'phase2/ssh-known-hosts'),
                  HOSTS[mac], shlex.join(cmd)]
    try:
        r = subprocess.run(actual, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError('Command exceeded timeout: ' + shlex.join(cmd))
    with (OUT/'commands.txt').open('a') as f:
        f.write(f'\nUTC: {datetime.now(timezone.utc).isoformat()}\nMac {mac}: {shlex.join(cmd)}\nExit: {r.returncode}\n{r.stdout}\n{r.stderr}\n')
    return r

def admin(mac, action):
    r = run(mac, ['sudo', '-n', NEW if mac == 3 else OLD, action])
    assert r.returncode == 0, r.stderr

def curl(mac, url, extra=()):
    return run(mac, ['curl', '--noproxy', '*', '--http1.1', '--connect-timeout', '4',
                     '--max-time', '12', '-sS', '-i'] + list(extra) + [url])

def case(name, fn):
    print('RUN ' + name, flush=True)
    try:
        fn()
        results[name] = 'PASS'
    except Exception as error:
        results[name] = 'FAIL: ' + str(error)
    print(results[name] + ': ' + name, flush=True)

def negative_tcp_tls():
    for mac in (1, 2):
        wrong_port = curl(mac, 'https://app.cn-project.test:8444/api/status')
        assert wrong_port.returncode in (7, 28), repr(wrong_port)
        wrong_name = curl(mac, 'https://wrong.cn-project.test:8443/api/status',
                          ['--resolve', 'wrong.cn-project.test:8443:10.7.18.166'])
        assert wrong_name.returncode == 60, 'Expected hostname verification failure: ' + wrong_name.stderr
        good = curl(mac, 'https://app.cn-project.test:8443/api/status')
        assert good.returncode == 0 and good.stdout.startswith('HTTP/1.1 200'), good.stderr

def cache_headers():
    for mac in (1, 2):
        statuses = set()
        for _ in range(8):
            r = curl(mac, 'https://app.cn-project.test:8443/api/status', ['-H', 'If-None-Match: "A-v1"'])
            assert r.returncode == 0, r.stderr
            assert 'Cache-Control: max-age=60' in r.stdout and 'ETag:' in r.stdout, r.stdout
            statuses.add(r.stdout.splitlines()[0])
        assert 'HTTP/1.1 304 Not Modified' in statuses, statuses

def both_dns_down():
    # Stop services only; never turn off a laptop, interface, Wi-Fi or nginx.
    try:
        admin(2, 'dns-stop')  # Legacy Mac 2 must not mask loss of the active pair.
        admin(1, 'dns-stop')
        admin(3, 'dns-stop')
        time.sleep(1)
        for mac in (1, 2):
            admin(mac, 'cache-flush')
            for server in ('10.7.26.228', '10.7.26.237'):
                r = run(mac, ['dig', '@' + server, 'app.cn-project.test', '+time=1', '+tries=1'])
                assert r.returncode != 0, 'Stopped DNS still answers: ' + server
            by_name = curl(mac, 'https://app.cn-project.test:8443/api/status')
            assert by_name.returncode in (6, 28), 'Expected fresh name-resolution failure: ' + by_name.stdout
            direct_http = curl(mac, 'http://10.7.18.166:8080/api/status')
            assert direct_http.returncode == 0 and direct_http.stdout.startswith('HTTP/1.1 200'), direct_http.stderr
            verified_edge = curl(mac, 'https://app.cn-project.test:8443/api/status',
                                 ['--resolve', 'app.cn-project.test:8443:10.7.18.166'])
            assert verified_edge.returncode == 0 and verified_edge.stdout.startswith('HTTP/1.1 200'), verified_edge.stderr
    finally:
        restore_errors = []
        for mac, action in ((1, 'dns-start'), (3, 'dns-start'), (1, 'cache-flush'), (2, 'cache-flush')):
            try:
                admin(mac, action)
            except Exception as error:
                restore_errors.append(str(error))
        assert not restore_errors, restore_errors
    for mac in (1, 2):
        restored = curl(mac, 'https://app.cn-project.test:8443/api/status')
        assert restored.returncode == 0 and restored.stdout.startswith('HTTP/1.1 200'), restored.stderr

case('wrong port versus TLS hostname mismatch, both clients', negative_tcp_tls)
case('cache headers and real conditional 304, both clients', cache_headers)
case('both active DNS services stopped; direct edge healthy; DNS restored', both_dns_down)
(OUT/'summary.json').write_text(json.dumps(results, indent=2) + '\n')
raise SystemExit(any(value != 'PASS' for value in results.values()))
