#!/usr/bin/env python3
"""Check visible DNS/TCP/TLS evidence using Wireshark's packet reassembly.

PASS describes a visible packet sequence, not decrypted Finished/HTTP messages,
certificate trust or application success. Pair captures with verified curl logs.
No packets are sent and no services or existing captures are changed.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys

FIELDS = [
    'frame.number', 'frame.time_epoch', 'ip.src', 'ip.dst',
    'tcp.srcport', 'tcp.dstport', 'tcp.stream', 'tcp.flags.syn',
    'tcp.flags.ack', 'tcp.flags.reset', 'tcp.seq', 'tcp.ack',
    'udp.srcport', 'udp.dstport', 'dns.flags.response', 'dns.flags.rcode',
    'dns.qry.name', 'dns.a', 'dns.response_to',
    'tls.handshake.type', 'tls.handshake.extensions_server_name',
    'tls.handshake.extensions.supported_version', 'tls.handshake.version',
    'tls.record.content_type', 'tls.record.opaque_type',
]


def values(packet, field):
    return packet.get(field, '').split(',') if packet.get(field) else []


def number(packet):
    return int(packet['frame.number'])


def flag(packet, field):
    return packet.get(field, '').lower() in ('true', '1')


def integer(packet, field):
    return int(packet.get(field, '-1'), 0)


def find_tshark():
    candidates = [shutil.which('tshark'), '/Applications/Wireshark.app/Contents/MacOS/tshark']
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError('TShark is required. Use the Mac with Wireshark installed.')


def read_packets(path, port):
    command = [find_tshark(), '-r', str(path), '-n', '-d', f'tcp.port=={port},tls',
               '-T', 'fields', '-E', 'header=y', '-E', 'occurrence=a']
    for field in FIELDS:
        command += ['-e', field]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError('TShark could not read capture: ' + result.stderr.strip())
    return list(csv.DictReader(io.StringIO(result.stdout), delimiter='\t'))


def matching_dns(packets, client, edge, name, syn):
    by_frame = {number(packet): packet for packet in packets}
    for response in packets:
        if not (flag(response, 'dns.flags.response') and
                response.get('dns.flags.rcode') == '0' and
                response.get('udp.srcport') == '53' and
                response.get('ip.dst') == client and
                name in values(response, 'dns.qry.name') and
                edge in values(response, 'dns.a') and
                number(response) < number(syn) and
                float(response['frame.time_epoch']) <= float(syn['frame.time_epoch'])):
            continue
        for reference in values(response, 'dns.response_to'):
            query = by_frame.get(int(reference))
            if query and (query.get('ip.src') == client and
                          query.get('ip.dst') == response.get('ip.src') and
                          name in values(query, 'dns.qry.name') and
                          number(query) < number(response)):
                return number(response)
    return None


def inspect_stream(stream, packets, name, port, edge=None, skip_dns=False, certificate=False):
    rows = sorted(stream, key=number)
    syn = next((p for p in rows if flag(p, 'tcp.flags.syn') and
                not flag(p, 'tcp.flags.ack') and p.get('tcp.dstport') == str(port)), None)
    if not syn or (edge and syn.get('ip.dst') != edge):
        return None
    client, server = syn['ip.src'], syn['ip.dst']
    up = lambda p: p.get('ip.src') == client and p.get('ip.dst') == server
    down = lambda p: p.get('ip.src') == server and p.get('ip.dst') == client
    synack = next((p for p in rows if down(p) and number(p) > number(syn) and
                   flag(p, 'tcp.flags.syn') and flag(p, 'tcp.flags.ack') and
                   integer(p, 'tcp.ack') == integer(syn, 'tcp.seq') + 1), None)
    if not synack:
        return None
    ack = next((p for p in rows if up(p) and number(p) > number(synack) and
                flag(p, 'tcp.flags.ack') and not flag(p, 'tcp.flags.syn') and
                integer(p, 'tcp.ack') == integer(synack, 'tcp.seq') + 1), None)
    if not ack:
        return None
    dns_frame = None if skip_dns else matching_dns(packets, client, server, name, syn)
    if not skip_dns and dns_frame is None:
        return None
    hello = next((p for p in rows if up(p) and number(p) >= number(ack) and
                  '1' in values(p, 'tls.handshake.type') and
                  name in values(p, 'tls.handshake.extensions_server_name')), None)
    if not hello:
        return None
    server_hello = next((p for p in rows if down(p) and number(p) > number(hello) and
                         '2' in values(p, 'tls.handshake.type')), None)
    if not server_hello:
        return None
    tls13 = '0x0304' in values(server_hello, 'tls.handshake.extensions.supported_version')
    cert = next((p for p in rows if down(p) and number(p) >= number(server_hello) and
                 '11' in values(p, 'tls.handshake.type')), None)
    if certificate and (tls13 or cert is None):
        return None
    def encrypted(p):
        field = 'tls.record.opaque_type' if tls13 else 'tls.record.content_type'
        return '23' in values(p, field)
    client_data = next((p for p in rows if up(p) and number(p) > number(server_hello)
                        and encrypted(p)), None)
    if not client_data:
        return None
    server_data = next((p for p in rows if down(p) and number(p) > number(client_data)
                        and encrypted(p)), None)
    if not server_data or any(flag(p, 'tcp.flags.reset') and number(p) < number(server_data)
                              for p in rows):
        return None
    return {
        'stream': syn['tcp.stream'], 'client': client, 'edge': server,
        'dns_response_frame': dns_frame,
        'tcp_handshake_frames': [number(syn), number(synack), number(ack)],
        'client_hello_frame': number(hello), 'server_hello_frame': number(server_hello),
        'tls_version': 'TLS 1.3' if tls13 else 'TLS 1.2 or earlier',
        'certificate_frame': number(cert) if cert else None,
        'encrypted_record_frames': [number(client_data), number(server_data)],
    }


def check(packets, name='app.cn-project.test', port=8443, edge=None,
          skip_dns=False, certificate=False):
    streams = {}
    for packet in packets:
        if packet.get('tcp.stream') and str(port) in (packet.get('tcp.srcport'), packet.get('tcp.dstport')):
            streams.setdefault(packet['tcp.stream'], []).append(packet)
    matches = [result for stream in streams.values()
               if (result := inspect_stream(stream, packets, name, port, edge, skip_dns, certificate))]
    return {
        'result': 'PASS' if matches else 'FAIL', 'scope': 'VISIBLE PACKET SEQUENCE ONLY',
        'dns_required': not skip_dns, 'certificate_required': certificate,
        'streams_checked': len(streams), 'matching_streams': len(matches), 'matches': matches,
        'limitations': [
            'Encrypted TLS 1.3 inner message types, Finished and HTTP content are not identified.',
            'Record length does not establish an encrypted alert, handshake success or HTTP success.',
            'Pair with certificate-verified curl output for trust and HTTP status evidence.',
            'DNS correlation currently covers captured IPv4 UDP query/response pairs; cached/DNS-TCP lookups need --skip-dns.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pcap', type=Path)
    parser.add_argument('--name', default='app.cn-project.test')
    parser.add_argument('--port', type=int, default=8443)
    parser.add_argument('--edge')
    parser.add_argument('--skip-dns', action='store_true')
    parser.add_argument('--expect-certificate', action='store_true')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    protected = args.pcap.resolve()
    outputs = [p.resolve() for p in (args.out, args.json) if p]
    if protected in outputs or len(set(outputs)) != len(outputs):
        parser.error('Output paths must be distinct and cannot replace the capture.')
    if any(p.exists() for p in outputs):
        parser.error('Refusing to overwrite an existing output file; choose new paths.')
    try:
        result = check(read_packets(args.pcap, args.port), args.name.lower().rstrip('.'),
                       args.port, args.edge, args.skip_dns, args.expect_certificate)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        parser.exit(2, str(error) + '\n')
    result['capture'] = str(args.pcap)
    result['sha256'] = hashlib.sha256(args.pcap.read_bytes()).hexdigest()
    report = json.dumps(result, indent=2) + '\n'
    print(report, end='')
    for output in (args.out, args.json):
        if output:
            with output.open('x') as destination:
                destination.write(report)
    return 0 if result['result'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
