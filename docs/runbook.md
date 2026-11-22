# Final Demonstration Runbook

For exact per-person commands and spoken explanations, follow
[Tomorrow's two-Mac demo guide](tomorrow-demo.md).

Run commands from the repo root. Current IP inventory is in `phase2/lab.env`.
Both Macs must be awake, on the same LAN, with primary DNS records restored,
both backends running, primary and standby edges ready, and project PF rules off.
The acceptance summary records completed tests and the two-Mac firewall proof
limitation. Keep evidence files open so they are found quickly.

## 1. Topology and service inventory

Show `docs/architecture.md` Phase 2 section. Mac 1 is primary DNS, client,
Backend B, and standby edge. Mac 2 is backup DNS, primary edge, and Backend A.
Explain that stopping Backend A means stopping its process, not the whole Mac.

## 2. LAN connectivity

On each Mac run `ifconfig en0` and `bash tests/test-connectivity.sh`.
Record IP, mask, interface, MAC, and gateway (`route -n get default`).

## 3. Private DNS

Run `bash tests/test-dns.sh` and `scutil --dns`.
Both resolvers must answer both project names with Mac 2's IP and TTL 30.
The system lookup uses `dscacheutil`, not plain dig.

## 4. Verified HTTPS by name

```bash
/usr/bin/curl --noproxy '*' -v https://app.cn-project.test:8443/api/status
```

Show certificate verification and HTTP 200. No `-k`.

## 5. Backend load balancing

```bash
python3 phase2/probe.py --count 8 --expect both --out evidence/phase-2/baseline/demo-by-name.txt
```

Show `X-Edge: mac2` and both `X-Backend: A` and `B`.

## 6. Packet evidence

Open the saved Wireshark capture. Identify DNS query/answer, ephemeral client
port, TCP SYN/SYN-ACK/ACK to :8443, ClientHello/SNI, ServerHello, and encrypted
Application Data. TLS 1.3 encrypts the certificate handshake message after
ServerHello, so the absence of a plaintext certificate packet is expected.
Use curl to show HTTP headers and certificate validation separately.

## 7. HTTP caching

Show `evidence/phase-2/baseline/cache-headers.txt` and the conditional attempt
files containing 304. Run fresh requests with a single matching ETag:

```bash
/usr/bin/curl --noproxy '*' --cacert .runtime/ca.crt -I https://app.cn-project.test:8443/api/status
/usr/bin/curl --noproxy '*' --cacert .runtime/ca.crt -i -H 'If-None-Match: "A-v1"' https://app.cn-project.test:8443/api/status
```

A B response to an A ETag can legitimately return 200. Repeat to reach A.

## 8. Backend failure and recovery

On Mac 2 run `python3 phase2/services.py stop a`.
On Mac 1 run the probe by name with `--expect B`.
Restore A with `python3 phase2/services.py start a` on Mac 2.
Wait at least 5 seconds, then probe with `--expect both`.
Explain passive detection, timeout/retry, recovery, and the edge SPOF.

## 9. Phase 2 resilience, isolation, and cutover

Backup DNS: stop only primary DNS on Mac 1 with
`sudo -n /usr/local/sbin/cn-project-admin dns-stop`, flush its OS cache using
`cache-flush`, and resolve by OS lookup and HTTPS. Capture backup-server logs
and packets. Restore with `dns-start`. A successful direct dig to backup
alone does not prove client failover.

Isolation: run `firewall-on` on both Macs. Show Mac 1 direct Backend A
access blocked, Mac 2 loopback A and remote B allowed, and HTTPS still working.
Show `firewall-status` counters. Run `firewall-off` on both Macs before migration.
Explain the two-host limitation for an independent blocked Backend B client.

TTL and cutover: prime each client's OS cache while records point at Mac 2.
Run `dns-standby` on both DNS servers. Show direct DNS immediately reports Mac 1,
while any observed old cached answer still uses Mac 2. After expiry show
new requests use Mac 1 and `X-Edge: mac1`. Repeat and manually `cache-flush`
to show immediate adoption. Record actual timestamps; do not promise exact
resolver timing or treat `--resolve` as a cache observation.

Restore `dns-primary` on both resolvers, flush both client caches, and show
normal service through Mac 2 again.

## 10. Faculty-injected fault

Use `bash phase2/diagnose.sh`. Explain each result before moving up a layer:
DNS answer, reachable IP/TCP port, verified TLS, HTTP status/backend response.
Use `curl --resolve` to isolate DNS while preserving TLS hostname validation.
Refused connection means no listener or rejection; timeout can indicate a
silent filter or unavailable host; TLS error means certificate/trust/hostname;
502 means the edge responded but its upstream failed.

## 11. Individual viva

Both members explain DNS failure versus app failure, TTL and existing TCP
connections, passive checks versus active probes, source/destination sockets,
local CA trust and SANs, PF states and rollback, and the combined-role SPOFs.
Swap roles during rehearsal so each can explain the other Mac's configuration.

## Restore after every demonstration

On both Macs: `dns-primary`, `dns-start`, `firewall-off`, `cache-flush` using
the admin helper. Start the local backend if stopped, keep both edges running,
and rerun by-name HTTPS with `--expect both`. Never leave an injected fault active.
