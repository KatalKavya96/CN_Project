# CN Project - Private Network Service Platform

Kavya Katal and Ronit Singh. Two-Mac local deployment covering Phase 1
(build and observe) and Phase 2 (harden, recover, troubleshoot).

## Start here

- [Architecture and topology](docs/architecture.md)
- [End-to-end request flow](docs/request-flow.md)
- [Phase 2 operating commands](phase2/README.md)
- [Final demonstration runbook](docs/runbook.md)
- [Phase 2 final report](docs/phase2-report.md)
- [Evidence index](evidence/phase-2/README.md)

The application stays simple: DNS -> TCP -> TLS -> HTTP -> nginx -> backend.
Everything runs locally; there is no cloud dependency in the service path.

## Current lab inventory

Recorded 22 November 2026. DHCP addresses must be rechecked before the demo.

| Machine | Address | Interface | Services |
| --- | --- | --- | --- |
| Mac 1 - Kavya | `10.7.26.228/19` | `en0` | Primary DNS :53, Backend B :3002, standby nginx :8080/:8443, client |
| Mac 2 - Ronit | `10.7.18.166/19` | `en0` | Backup DNS :53, Backend A :3001, primary nginx :8080/:8443, client |

Subnet mask: `255.255.224.0`; gateway: `10.7.0.1`.
Both DNS servers normally map `app.cn-project.test` and `api.cn-project.test`
to Mac 2. Controlled cutover maps them to Mac 1 with TTL 30.
Both client Macs list both DNS addresses in `/etc/resolver/cn-project.test`.

## Configuration and startup

Both Macs need Python 3, dnsmasq, nginx, and OpenSSL. `phase2/lab.env` is the
current IP inventory. `phase2/render.sh mac1` or `mac2` generates that host's
nginx and development DNS config under ignored `.runtime/`.

The installed root-owned admin helper runs DNS using
`/private/var/db/cn-project/dnsmasq.conf`, with reloadable hosts records.
Do not also start the development `.runtime/dnsmasq.conf` instance on port 53.
The one-time installer is `bash phase2/install-admin.sh mac1` or `mac2`.
Do not rerun an installer over an existing installation.

On either Mac, start managed DNS with:

```bash
sudo -n /usr/local/sbin/cn-project-admin dns-start
```

On Mac 1 start Backend B and, if it is not already running, standby nginx:

```bash
python3 phase2/services.py start b
/opt/homebrew/bin/nginx -c "$PWD/.runtime/nginx.conf"
```

On Mac 2 start Backend A and keep the edge foreground session running:

```bash
/usr/bin/python3 phase2/services.py start a
/usr/bin/python3 phase2/start-edge.py
```

Mac 2's tested launch keeps nginx attached to a local terminal or persistent
SSH session. Detached daemon launches produced upstream routing errors in this
lab. Do not close the serving foreground session during the demonstration.
Do not start a second nginx when ports 8080/8443 are already in use.

`setup_repo.sh` is a historical Phase 1 scaffold that overwrites files; do not
run it on either existing checkout. Old repair scripts are also historical;
use the Phase 2 operating commands for this deployment.

## TLS and backend behavior

Each edge has a server certificate for both project names signed by the same
local CA. Mac 1 has its own server private key; the CA private key stays on
Mac 2. Server certificate/key and public CA certificate are under `.runtime/`.
Private keys and generated certificates are ignored by Git.

Use `--cacert .runtime/ca.crt` for explicit CA validation, or install the public
CA certificate in the client's trust store. Never use `-k` as final proof.
Both backends provide GET `/`, GET `/api/status`, HEAD, `X-Backend`,
`Cache-Control: max-age=60`, ETag, and matching conditional 304 responses.
`X-Edge` identifies the edge; upstream logs show backend choices and retries.

## Verification

```bash
bash tests/test-dns.sh
/usr/bin/curl --noproxy '*' --cacert .runtime/ca.crt -v https://app.cn-project.test:8443/api/status
python3 phase2/probe.py --count 8 --expect both --out evidence/phase-2/baseline/demo-by-name.txt
bash phase2/diagnose.sh
```

`dig @server` checks server data. `dscacheutil` and normal curl requests use
the macOS resolver. curl `--resolve` preserves TLS hostname validation while
bypassing DNS and therefore cannot prove OS resolver failover by itself.

The repeatable live suite on Mac 1 is `python3 phase2/final-tests.py`; it
deliberately stops primary DNS and Backend A, changes DNS, and applies PF
rules, saving observations and restoring service. Read its summary under
`evidence/phase-2/final/`. Run it only during a planned demonstration window.
The course's individual viva and faculty-injected fault still require both
students to understand and operate the system.
