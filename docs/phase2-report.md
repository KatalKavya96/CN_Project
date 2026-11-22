# Phase 2 Final Report

Team: Kavya Katal and Ronit Singh. Lab session: 22 November 2026.

Live acceptance tests were completed on both Macs. The acceptance summary is
`evidence/phase-2/acceptance-summary.md`. A first OS-cache timing check failed;
the measured-refresh recheck passed and is preserved alongside the first run.
All network test results use normal certificate verification with the explicit
project CA. After user-keychain authorization completed on Mac 1, plain HTTPS
also passed on both Macs using default trust, without `--cacert` or `-k`.

## Changes from Phase 1

The same two Macs and backends are retained. DHCP addresses changed to
Mac 1 `10.7.26.228/19` and Mac 2 `10.7.18.166/19`. Phase 2 adds a backup DNS
resolver on Mac 2, a separately certified standby nginx edge on Mac 1,
explicit passive upstream failure handling, upstream logs and edge headers,
reversible PF isolation, and limited root-owned administrator controls.
Client verification uses the public CA certificate without disabling TLS checks.

## A. Backup DNS

Both DNS server configurations provide the same records and TTL 30.
Backup DNS direct query evidence is saved under `evidence/phase-2/dns-failover/`.
The obsolete primary DNS process was replaced by the managed service. Primary
DNS was then stopped; a direct query confirmed it no longer answered. After
cache flushing, both Macs resolved the project hostname through the backup and
completed verified HTTPS by name. Primary DNS was restored and both clients
were checked again. See `final/primary-stopped-direct-query.txt`,
`final/primary-down-os-lookup.txt`, `final/primary-down-by-name-https.txt`, and
`final/backup-query-log.txt` under the Phase 2 evidence directory.

Learning: DNS redundancy preserves name resolution when a DNS process fails.
It does not keep an unavailable application alive. An NXDOMAIN answer is a
valid negative response and should not be confused with an unreachable DNS
server; resolver selection must be observed rather than assumed.

## B. TTL and record changes

Both root-owned DNS configurations use `local-ttl=30` and reloadable hosts
records. A temporary client caching dnsmasq on Mac 1 port 1053 was tested
against the live backup DNS. Evidence in `ttl/client-cache-and-cutover.txt`
shows the old answer at TTL 29, 24, 19, 14, 9, and 4 seconds, followed by the
new answer after expiry. After restoring primary-edge records, SIGHUP flushed
that client cache and immediately returned the restored address. This is a
real client-resolver cache test, not a macOS system-cache observation.

The actual macOS caches were also tested on both Macs, using normal by-name
curl requests without `--resolve`. Both initially retained Mac 2 after the
records changed. Flushing Mac 2 immediately moved it to Mac 1. Mac 1 returned
one old answer about 37 seconds after cutover while refreshing, then returned
Mac 1 about 39 seconds after cutover. Both clients served verified HTTPS from
the standby; restoring records and flushing caches returned them to Mac 2.
See `final-cutover-recheck/`. The first test's exact-35-second assertion was
replaced by a bounded measured refresh window; its failure logs are retained.

Learning: direct DNS queries bypass the macOS application cache. A cached
answer can remain after an authoritative record changes, and an established
connection can remain after the DNS TTL expires. Measure each independently.

## C. Service isolation

Mac 2 PF isolation was applied and tested. Mac 1's direct connection to
Backend A :3001 timed out, while Mac 2's loopback request succeeded.
The block rule counter recorded dropped packets. The project anchor was
then flushed and its own PF enable reference released. Mac 1's Backend B
rules were also applied: a Mac 2 LAN request succeeded and rule counters were
saved, followed by rollback. Evidence is under `evidence/phase-2/isolation/`.
An independent disallowed third-client test against Backend B remains unavailable.
The final integrated test additionally applied both Macs' rules together:
direct Mac 1-to-A traffic was blocked, Mac 2 reached local A and remote B, and
both clients received A/B responses over HTTPS through the primary edge.
Both firewall anchors were rolled back afterward. See `final/isolation-*`.

Learning: an IP/port firewall controls network paths rather than application
identity. With combined roles on two hosts, traffic sharing an allowed source
IP cannot distinguish an edge from a client. A third independent client gives
the clearest additional proof that Backend B rejects unrelated LAN clients.

## D. Backend availability

The standby edge passed verified HTTPS with A/B responses, six B-only
successful requests while Backend A was stopped, and A/B responses after A
was restarted. Evidence is under `evidence/phase-2/ha/`.
The primary edge subsequently passed eight A/B requests, eight successful B-only
requests during an A failure, and eight A/B requests after A recovered.
See `baseline/primary-edge-persistent-ssh.txt`, `ha/primary-a-down.txt`, and
`ha/primary-a-restored.txt`. Daemon and detached launches produced EHOSTUNREACH
for Backend B, while nginx kept in foreground mode inside an authenticated
persistent SSH session reached both backends. This launch dependency is
recorded; the precise macOS policy cause was not established. Initial failed
baseline probes are retained rather than hidden.
The final by-name test repeated failure and recovery from both clients with
no DNS bypass. Both saw B-only while A was stopped and A/B after recovery.
See `final/backend-a-down-by-name.txt` and `final/backend-a-restored-by-name.txt`.

Learning: passive checks learn from failed requests. A refused TCP connection
fails quickly; a silent drop waits for the configured timeout. Retrying a
request on a healthy backend maintains service for these GET requests.
Stopping Mac 2 itself also loses its edge, so process failure is not host HA.

## E. Edge migration

Standby nginx is installed and running on Mac 1 with its own CA-signed
certificate. Verified HTTPS and both upstreams pass using a DNS-independent
`--resolve` probe. During the isolated-client-cache test, actual backup DNS
records were changed to Mac 1. The cached old DNS answer reached `X-Edge: mac2`,
while a fresh DNS lookup reached `X-Edge: mac1`; both returned verified HTTPS
200 responses. After TTL expiry, the client cache adopted Mac 1. Records were
then restored on both managed DNS configurations. See
`evidence/phase-2/ttl/client-cache-and-cutover.txt`. The curl destinations were
derived from real DNS answers using `--resolve`; this is not an OS resolver test.
The subsequent real OS-resolver cutover also passed on both Macs, with old
cached requests reaching `X-Edge: mac2` and flushed/updated requests reaching
`X-Edge: mac1`. These requests did not use `--resolve`. See
`final-cutover-recheck/cutover-immediate-by-name.txt`,
`cutover-fresh-client-by-name.txt`, and `cutover-after-ttl-by-name.txt` there.

Learning: keep the old edge working through the transition because cached DNS
answers and existing connections can still use it. Updating only one of two
DNS servers gives inconsistent records. Manual DNS migration is controlled
cutover, not automatic removal of the edge single point of failure.

## F. Troubleshooting and remaining preparation

`phase2/diagnose.sh` checks scoped resolver configuration, OS lookup, each DNS
server, TCP, DNS-independent TLS/HTTP, and HTTP through the OS resolver.
Two safe diagnostic drills were recorded: wrong destination port returned curl
error 7 (connection refused), and wrong hostname returned curl error 60
(certificate SAN mismatch). Full two-person rehearsal is pending. An actual fault found
during setup was an obsolete user-configured dnsmasq listener occupying port 53
and returning NXDOMAIN. The replacement DNS could not bind until that process
was stopped. The nginx-only outbound failure was resolved for the lab by
retaining a foreground SSH session, as described in Extension D.
The completed diagnosis script was run on both Macs after recovery; see
`final/diagnostics-mac1.txt` and `final/diagnostics-mac2.txt`.

Learning: test DNS, TCP, TLS, and application behavior separately. curl
`--resolve` keeps hostname validation while bypassing DNS; `-k` would hide a
TLS trust fault. Explain the command's purpose and observed error aloud.

## Additional validation

The three previously missing Phase 1 failure experiments were subsequently
completed on both Macs. See `evidence/phase-1/failures-2026-11-22/`.
A temporary client-scoped resolver configured with an unavailable upstream
failed DNS while peer IP connectivity and DNS-independent trusted HTTPS worked.
Real project records were then changed to Mac 1 with its standby edge stopped:
DNS succeeded but by-name connections failed, while direct selection of the
correct edge still worked. With both backends stopped, DNS and verified TLS
remained available and nginx returned 502 on both clients. Both backends,
primary DNS records, client caches and standby nginx were restored; primary
and standby edges again served A/B responses. This wrong-resolver experiment
did not modify macOS global DNS settings.

The standby edge returned real `304 Not Modified` responses with matching
per-backend ETags. Both server certificates verify against the existing CA.
Private keys and generated runtime material are ignored by Git. A fresh saved
capture, `evidence/phase-2/baseline/dns-tcp-tls-current.pcap`, contains the DNS
query/answer and the TCP/TLS connection to Mac 2 :8443. Its paired request log
shows verified HTTPS. This capture uses explicit backup DNS followed by curl
to the returned address; it does not prove OS resolver failover or caching.
The final suite exercised by-name baseline, real DNS failover, OS cutover,
backend failure/recovery, isolation with HTTPS continuity, and final health on
both Macs. `final/dns-failover-cutover.pcap` and the recheck capture preserve the
live sessions; DNS and TLS packet indexes identify relevant frames.

## Evaluation caveats

A fresh live recovery on 23 November verified both Macs again after Ronit's
closed-lid/battery network availability issue. The repository configuration
was intact. See `docs/live-recovery.md` and
`evidence/recovery/2026-11-23T015853/` for peer pings, both DNS names/servers,
direct root/status/HEAD responses from both backends, and default-trust A/B
responses through both edges from both clients. Saved evidence was preserved.

- Both students still need to rehearse the spoken 11-step demonstration and
  answer the individual viva; the faculty-injected fault occurs at evaluation.
- CA trust is resolved: after approval and native macOS authorization on Mac 1,
  both Macs passed plain HTTPS with TLS 1.3, a matching hostname, `SSL certificate
  verify ok.`, HTTP 200, and exit 0. See `final/default-trust-mac1-verified.txt`
  and `final/default-trust-mac2-verified.txt`. Earlier failed trust attempts are
  retained as historical diagnostic evidence.
- Backend B's rejection of an independent unrelated client needs a third
  source address. The two-Mac test proves the configured rules, allowed path,
  Backend A rejection, and continuing HTTPS, and documents the role overlap.
- The primary edge's current foreground SSH session must remain alive.
- DHCP changes require updating both ordinary and installed root-owned configs;
  editing `phase2/lab.env` alone does not update the already-installed DNS service.
