"""Regression cases for PR #1: DNS correlation and visible TLS claims."""
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('capture_checker', Path(__file__).resolve().parents[1]/'phase2/check-capture.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def fixture(tls13=True):
    client, edge, dns = '10.7.26.228', '10.7.18.166', '10.7.26.237'
    def packet(n, src, dst, **fields):
        return {'frame.number': str(n), 'frame.time_epoch': str(n), 'ip.src': src, 'ip.dst': dst, **fields}
    rows = [packet(1, client, dns, **{'dns.qry.name': 'app.cn-project.test'}),
            packet(2, dns, client, **{'udp.srcport': '53', 'dns.flags.response': 'True',
                   'dns.flags.rcode': '0', 'dns.qry.name': 'app.cn-project.test',
                   'dns.a': edge, 'dns.response_to': '1'})]
    def tcp(n, down=False, **fields):
        return packet(n, edge if down else client, client if down else edge,
                      **{'tcp.stream': '0', 'tcp.srcport': '8443' if down else '50000',
                         'tcp.dstport': '50000' if down else '8443', **fields})
    rows += [tcp(3, **{'tcp.flags.syn': 'True', 'tcp.seq': '0'}),
             tcp(4, True, **{'tcp.flags.syn': 'True', 'tcp.flags.ack': 'True', 'tcp.seq': '0', 'tcp.ack': '1'}),
             tcp(5, **{'tcp.flags.ack': 'True', 'tcp.ack': '1'}),
             tcp(6, **{'tls.handshake.type': '1', 'tls.handshake.extensions_server_name': 'app.cn-project.test'}),
             tcp(7, True, **{'tls.handshake.type': '2' if tls13 else '2,11',
                 'tls.handshake.extensions.supported_version': '0x0304' if tls13 else ''}),
             tcp(8, **{('tls.record.opaque_type' if tls13 else 'tls.record.content_type'): '23'}),
             tcp(9, True, **{('tls.record.opaque_type' if tls13 else 'tls.record.content_type'): '23'})]
    return rows


class CaptureChecks(unittest.TestCase):
    def test_positive_visible_sequence(self):
        result = checker.check(fixture())
        self.assertEqual(result['result'], 'PASS')
        self.assertEqual(result['scope'], 'VISIBLE PACKET SEQUENCE ONLY')
        self.assertNotIn('finished_frame', result['matches'][0])

    def test_dns_after_syn_is_rejected(self):
        rows = fixture()
        rows[1]['frame.number'] = rows[1]['frame.time_epoch'] = '20'
        self.assertEqual(checker.check(rows)['result'], 'FAIL')

    def test_other_clients_dns_is_rejected(self):
        rows = fixture()
        rows[1]['ip.dst'] = '10.7.26.241'
        self.assertEqual(checker.check(rows)['result'], 'FAIL')

    def test_wrong_dns_answer_is_rejected(self):
        rows = fixture()
        rows[1]['dns.a'] = '10.7.26.250'
        self.assertEqual(checker.check(rows)['result'], 'FAIL')

    def test_tls13_does_not_claim_visible_certificate(self):
        self.assertEqual(checker.check(fixture(), certificate=True)['result'], 'FAIL')

    def test_coalesced_tls12_certificate_is_recognized(self):
        self.assertEqual(checker.check(fixture(False), certificate=True)['result'], 'PASS')

    def test_client_reset_before_reply_is_rejected(self):
        rows = fixture()
        rows[-2]['tcp.flags.reset'] = 'True'
        self.assertEqual(checker.check(rows)['result'], 'FAIL')

    def test_explicit_dns_bypass_is_labelled(self):
        result = checker.check(fixture()[2:], skip_dns=True)
        self.assertEqual(result['result'], 'PASS')
        self.assertFalse(result['dns_required'])

    def test_capture_cannot_be_an_output_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'capture.pcap'
            path.write_bytes(b'original capture')
            result = subprocess.run([sys.executable, str(spec.origin), str(path), '--json', str(path)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(path.read_bytes(), b'original capture')

    def test_existing_report_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'report.json'
            path.write_text('original report')
            result = subprocess.run([sys.executable, str(spec.origin), 'unused.pcap', '--json', str(path)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(path.read_text(), 'original report')


if __name__ == '__main__':
    unittest.main()
