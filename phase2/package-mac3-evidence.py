#!/usr/bin/env python3
"""Create a separate current-topology evidence supplement; leave old books intact."""
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'evidence/phase-2/mac3-dns'
originals = json.loads((OUT / 'migration-20261122T211927/prior-evidence-sha256.json').read_text())
changed = [name for name, digest in originals.items()
           if not (ROOT / name).is_file() or hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest]
if changed:
    raise RuntimeError('Original evidence changed: ' + repr(changed))
files = [p for p in (ROOT / 'evidence').rglob('*') if p.is_file()]
files += [p for folder in ('docs', 'phase2', 'tests') for p in (ROOT / folder).rglob('*')
          if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
files += [ROOT / 'README.md']
excluded = {OUT / 'manifest.json', OUT / 'evidence-book.html'}
manifest = {'assembled_utc': datetime.now(timezone.utc).isoformat(),
            'topology': {'primary_dns': '10.7.26.228', 'backup_dns': '10.7.26.237',
                         'primary_edge': '10.7.18.166', 'legacy_backup_dns': 'stopped'},
            'original_evidence_files_checked': len(originals), 'original_evidence_changed': changed,
            'files': {str(p.relative_to(ROOT)): {'bytes': p.stat().st_size,
                      'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                      for p in sorted(set(files) - excluded)}}
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
sections = [
    ('Migration and original evidence preservation', OUT / 'migration-20261122T211927/summary.json'),
    ('Phase 2 complete acceptance suite', OUT / 'final-20261123/summary.txt'),
    ('Phase 1 failures and restoration', ROOT / 'evidence/phase-1/failures-20261122T212149/summary.json'),
    ('Final live health and default TLS trust', ROOT / 'evidence/recovery/2026-11-23T025332/recovery-summary.json'),
    ('Current DNS service and client state', OUT / 'final-state.txt'),
    ('DNS packet fields from real capture', OUT / 'final-20261123/dns-packets.tsv'),
    ('DNS, TCP, TLS and verified HTTPS', OUT / 'protocol-20261122T212320/capture-request.txt')]
parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><title>CN Project: Mac 3 DNS evidence</title>',
         '<style>body{font:16px/1.5 system-ui;max-width:1050px;margin:32px auto;padding:0 20px;color:#182534}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f2f5f8;padding:16px;font-size:12px}a{color:#0759a6}h2{margin-top:32px}</style><body>',
         '<h1>Phase 2: Backup DNS on Priyanshu’s Mac</h1><p>Kavya Katal · Ronit Singh · Priyanshu Tomar</p>',
         '<p>23 November 2026 IST. Primary DNS: Mac 1. Backup DNS: Mac 3. Edges and backends stay on Macs 1 and 2.</p>',
         '<p>Actual logs and packet exports; excerpts below are not terminal screenshots. Historical artifacts remain unchanged.</p>',
         '<p><a href="README.md">Evidence index</a> · <a href="manifest.json">SHA-256 manifest</a> · <a href="../../../docs/tomorrow-demo.md">Three-person demo guide</a></p>']
for title, path in sections:
    parts += ['<h2>' + html.escape(title) + '</h2>',
              '<p><a href="' + html.escape(os.path.relpath(path, OUT), quote=True) + '">Full source</a></p>',
              '<pre>' + html.escape(path.read_text()[:18000]) + '</pre>']
parts += ['<p>Original evidence hashes verified: ' + str(len(originals)) + '; changed: 0.</p></body></html>']
(OUT / 'evidence-book.html').write_text('\n'.join(parts))
print('Preserved', len(originals), 'original files; indexed', len(manifest['files']), 'current sources.')
