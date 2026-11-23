#!/usr/bin/env python3
"""Capture one verified TLS 1.2 request with a visible Certificate message.

Run on Kavya's Mac. Does not change TLS settings, DNS, trust or service state.
The destination is explicit, so this supplementary capture does not test DNS.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', type=Path, help='New directory; existing paths are refused')
    args = parser.parse_args()
    env = dict(line.split('=', 1) for line in (ROOT/'phase2/lab.env').read_text().splitlines()
               if line and not line.startswith('#'))
    edge = str(ipaddress.ip_address(env['MAC2_IP']))
    interface = env['LAB_INTERFACE']
    own = subprocess.run(['/usr/sbin/ipconfig', 'getifaddr', interface],
                         capture_output=True, text=True, timeout=5)
    if own.returncode or own.stdout.strip() != env['MAC1_IP']:
        parser.error('Run on Kavya/Mac 1 with the configured LAN address and interface.')
    ca = ROOT/'.runtime/ca.crt'
    if not ca.is_file():
        parser.error('Missing existing project public CA: ' + str(ca))
    checker = ROOT/'phase2/check-capture.py'
    if not checker.is_file():
        parser.error('Missing capture checker')
    if args.out_dir:
        out = args.out_dir.resolve()
        out.mkdir(parents=True, exist_ok=False)
    else:
        parent = ROOT/'evidence/phase-2'
        parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
        out = Path(tempfile.mkdtemp(prefix='tls12-certificate-'+stamp+'-', dir=parent))
    pcap = out/'tls12-handshake.pcap'
    command = ['/usr/bin/curl', '--noproxy', '*', '--http1.1', '--tlsv1.2', '--tls-max', '1.2',
               '--cacert', str(ca), '--resolve', 'app.cn-project.test:8443:'+edge,
               '--connect-timeout', '5', '--max-time', '15', '-v', '-i',
               '--write-out', '\nCN_HTTP_CODE=%{http_code}\nCN_TLS_VERIFY=%{ssl_verify_result}\n',
               'https://app.cn-project.test:8443/api/status']
    result = None
    with (out/'capture-tool.log').open('x') as log:
        capture = subprocess.Popen(['/usr/sbin/tcpdump', '-i', interface, '-n', '-s', '0', '-U',
                                    '-w', str(pcap), 'host '+edge+' and tcp port 8443'],
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        try:
            time.sleep(1)
            if capture.poll() is not None:
                raise RuntimeError('Capture did not start; inspect capture-tool.log')
            result = subprocess.run(command, capture_output=True, text=True, timeout=25)
            time.sleep(1)
        finally:
            if capture.poll() is None:
                capture.send_signal(signal.SIGINT)
            try:
                capture.wait(timeout=5)
            except subprocess.TimeoutExpired:
                capture.terminate()
                capture.wait(timeout=5)
    request_log = ('UTC: '+datetime.now(timezone.utc).isoformat()+'\n'
                   'One TLS 1.2 request; certificate verification enabled. No service changes.\n'
                   'DNS bypassed with --resolve; this capture does not test DNS resolution.\n'
                   'Command: '+shlex.join(command)+'\nExit: '+str(result.returncode)+'\n\n'
                   +result.stderr+'\n'+result.stdout)
    (out/'capture-request.txt').write_text(request_log)
    checked = subprocess.run([sys.executable, '-I', str(checker), str(pcap), '--skip-dns',
                              '--edge', edge, '--expect-certificate', '--json', str(out/'check.json')],
                             capture_output=True, text=True, timeout=90)
    (out/'check.txt').write_text(checked.stdout+checked.stderr)
    packet = json.loads((out/'check.json').read_text()) if (out/'check.json').exists() else {}
    https_ok = (result.returncode == 0 and 'CN_HTTP_CODE=200' in result.stdout and
                'CN_TLS_VERIFY=0' in result.stdout)
    summary = {
        'result': 'PASS' if https_ok and checked.returncode == 0 else 'FAIL',
        'https_verified_http_200': https_ok, 'visible_certificate': checked.returncode == 0,
        'capture': str(pcap.relative_to(ROOT)) if ROOT in pcap.parents else str(pcap),
        'packet_checks': packet, 'services_changed': False, 'dns_bypassed': True,
        'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in out.iterdir() if p.is_file()},
    }
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(summary['result']+': verified HTTPS and visible Certificate; saved '+str(out))
    return 0 if summary['result'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
