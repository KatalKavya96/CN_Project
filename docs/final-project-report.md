# Private Network Service Platform

## Final project report: Phase 1 and Phase 2

**Team:** Kavya Katal, Ronit Singh and Priyanshu Tomar  
**Submission date:** 23 November 2026  
**Deployment:** Three macOS laptops on a private LAN; no cloud service in the request path  
**Repository:** https://github.com/KatalKavya96/CN_Project

### Abstract

This project implements and observes a private network application accessed
through DNS, TCP, TLS, HTTP and an nginx reverse proxy. Two Python backends
provide identifiable responses, cache headers and conditional validation.
Phase 2 extends the original two-Mac deployment with redundant DNS, a standby
edge, controlled DNS cutover, passive backend failure handling and reversible
backend firewall rules. The final arrangement uses Kavya's Mac for primary DNS,
Backend B and standby nginx; Ronit's Mac for primary nginx and Backend A; and
Priyanshu's Mac only for backup DNS. Controlled tests passed from both original
client Macs, including DNS loss, backend failures, cache behavior and recovery.
Raw logs, packet captures, field exports and preservation manifests accompany
the report. Automatic host failover, an independent third-source Backend B
rejection test, and completion of the live faculty challenge are not claimed.

## 1. Introduction and objectives

The course principle is that the application remains simple while the network
is built, observed and defended. Phase 1 established private LAN connectivity,
private DNS records, two HTTP backends, nginx round-robin distribution, local
CA-signed HTTPS, HTTP caching behavior and DNS/TCP/TLS packet evidence.
Phase 2 retained that infrastructure and added recovery and isolation mechanisms.

Both backends implement GET `/`, GET `/api/status`, and HEAD responses. Backend A
listens on port 3001 and Backend B on 3002. `X-Backend` identifies A or B, while
nginx adds `X-Edge` to identify the serving proxy. The normal client URL is
`https://app.cn-project.test:8443/api/status`. The second private name,
`api.cn-project.test`, resolves to the same edge.

## 2. Final architecture and ownership

| Member and machine | LAN address | Responsibilities |
| --- | --- | --- |
| Kavya - Mac 1 | 10.7.26.228/19 | Primary DNS :53, Backend B :3002, standby nginx :8080/:8443, client |
| Ronit - Mac 2 | 10.7.18.166/19 | Primary nginx :8080/:8443, TLS termination, Backend A :3001, client |
| Priyanshu - Mac 3 | 10.7.26.237/19 | Phase 2 backup DNS over UDP/TCP :53 only |

All three use interface `en0`. The observed subnet mask is 255.255.224.0 and
gateway 10.7.0.1. These DHCP addresses describe the tested LAN, not permanently
assigned identities. Both existing clients have a domain-specific resolver:

```text
/etc/resolver/cn-project.test
nameserver 10.7.26.228
nameserver 10.7.26.237
```

Both DNS servers normally return 10.7.18.166 for both project names, with TTL 30.
Ronit's former backup DNS is stopped, with its configuration retained for
rollback. Mac 3 received no application, nginx configuration or project TLS
private key. Its participation is confined to backup DNS.

```text
Client on Kavya or Ronit
  |-- DNS lookup --> Kavya primary / Priyanshu backup
  |<-- A record: 10.7.18.166, TTL 30
  |
  +-- TCP :8443 --> TLS --> HTTP --> Ronit's nginx
                                     |-- A: 127.0.0.1:3001
                                     +-- B: 10.7.26.228:3002

Controlled cutover: both DNS servers advertise 10.7.26.228
Client --> Kavya's standby nginx :8443
            |-- A: 10.7.18.166:3001
            +-- B: 127.0.0.1:3002
```

DNS supplies an address; it does not forward the HTTPS request. TCP establishes
the connection before TLS. TLS authenticates the server and protects traffic;
application user login or authorization was not implemented. nginx creates a
separate upstream HTTP connection to the selected backend.

## 3. Changes from Phase 1

| Area | Phase 1 baseline | Final Phase 2 behavior |
| --- | --- | --- |
| Physical roles | Two Macs combine clients, DNS, edge and backends | Same services retained; Priyanshu added only for backup DNS |
| Name resolution | Primary private DNS | Primary Mac 1 plus backup Mac 3 in both client resolvers |
| Edge availability | Primary nginx on Ronit | Additional certified standby nginx on Kavya; manual DNS cutover |
| Backend recovery | Round-robin responses | Explicit passive failure parameters and retries; A-down/B-only proof |
| Isolation | Direct backend paths available | Reversible project PF rules restrict backend LAN access |
| Observation | Protocol captures and response headers | Failure/cutover PCAPs, upstream logs, edge headers and hash manifests |

Backup DNS was initially tested on Ronit, then moved to Priyanshu without moving
the edges or backends. Both clients passed fresh resolution and plain HTTPS
with primary DNS and the retired Mac 2 backup simultaneously unavailable.
Historical two-Mac observations and older captures retain their collection
dates and addresses. They are preserved alongside the final three-Mac evidence.

## 4. Configuration and security controls

Primary and backup dnsmasq services use fixed root-owned configurations and
reloadable hosts records. Both receive the same record change. Root-owned
helpers expose exact project operations through limited sudoers rules. They
do not grant unrestricted password-free sudo. The active IP inventory is
`phase2/lab.env`; `phase2/mac3.env` records the backup DNS host.

nginx enables TLS 1.2 and 1.3. Each edge has a separate private key and a server
certificate covering both project hostnames, signed by the same local CA.
The CA private key stays on Ronit. Both client Macs passed default-trust HTTPS
without `-k` or `--cacert`; explicit public-CA validation remains supported.
Private keys and generated certificate/runtime files are ignored by Git.

The upstreams use `max_fails=1`, `fail_timeout=5s`, a two-second connection
timeout, a five-second read timeout and retries on configured upstream errors.
Backend responses use `Cache-Control: max-age=60` and per-backend ETags
`"A-v1"` and `"B-v1"`. HTTP freshness and DNS TTL govern different cached data.

## 5. Phase 2 extensions and learning summaries

### Extension A - Backup DNS resolver

Priyanshu's dnsmasq answers both names over UDP and TCP on port 53. Both client
resolvers list Kavya and Priyanshu. Tests stopped primary DNS, confirmed a direct
query failed, flushed client caches, and obtained successful OS lookups and
by-name HTTPS from both clients. Backup query logs recorded the client requests.
The active-pair outage test also stopped both DNS services: fresh hostname
requests failed while direct HTTP and verified DNS-bypassed HTTPS remained
healthy. DNS was restored afterward. Evidence: E1, E2 and E3.

**Learning summary:** DNS redundancy protects name resolution when a DNS
service becomes unavailable. A direct successful query to a backup is readiness
evidence; failover requires observing the normal client resolver during primary
failure with cached answers removed. An NXDOMAIN reply is a valid negative
answer and differs from a timeout. DNS redundancy cannot make a failed web
service healthy, and it does not move website traffic through the DNS server.

### Extension B - DNS TTL and controlled record change

The project uses TTL 30. Both DNS servers were updated from Ronit's edge to
Kavya's standby. Direct queries returned the new address, while OS-cache tests
recorded client adoption and by-name HTTPS destination changes. The suite used
a bounded refresh window rather than an exact expiry assertion. A separate
temporary caching dnsmasq on Kavya's loopback port 1053 showed a real countdown,
retention of the old address, adoption after expiry, and immediate return to the
restored address after manual flushing. That isolated cache is distinct from
the macOS resolver test. Evidence: E1 and E4.

**Learning summary:** A changed authoritative answer does not immediately
replace every client cache entry. Direct `dig @server` queries and application
resolution answer different questions. macOS may return an old answer while
initiating a refresh shortly after nominal TTL expiry, so results should be
measured. DNS TTL controls cached name data; it neither expires HTTP content nor
terminates an existing TCP connection. A flush demonstrates immediate adoption.

### Extension C - Service isolation

Project PF anchors on the original Macs restrict backend LAN ports to the
primary edge's source address. With both rule sets applied, Kavya's direct
request to Backend A timed out, while Ronit's loopback A request, remote B
request and client HTTPS remained successful. Rules and counters were exported.
Rollback removed only the project rules and released the project's PF enable
reference. Isolation was removed before standby cutover. Evidence: E1.

**Learning summary:** IP/port filtering controls network paths, not process
identity. An edge and client sharing a source address cannot be separated by
these rules; loopback success is not proof of LAN rejection. The recorded test
proves Backend A rejection, allowed access to B and HTTPS continuity. An
independent third-source rejection probe against B was not added: Mac 3's
requested role remained DNS only. This evidence limit is explicit. The
primary-only policy must be removed when the standby needs access to A.

### Extension D - Backend availability and recovery

Both clients first observed A/B responses through the primary edge. Backend A
was stopped; all tested requests succeeded through B. After A restarted and the
failure interval elapsed, A/B distribution resumed. Additional failure tests
stopped both backends, producing HTTP 502 with verified TLS still available.
Both backends were restarted and normal balancing rechecked. Evidence: E1, E5
and E6.

**Learning summary:** nginx's configured checks are passive and request-driven.
An upstream connection failure can trigger retry of the other backend; a later
request can try a recovered backend after the failure interval. These GET
request tests demonstrate backend process resilience, not complete host HA.
Stopping Ronit's whole Mac would also remove primary nginx. Shared host roles
and the LAN/router remain failure dependencies even with two backend processes.

### Extension E - Controlled edge migration

Kavya's standby has its own CA-signed certificate and can reach both backends.
Tests changed both DNS servers to Kavya's address, compared server answers with
cached client results, flushed one client for immediate migration, and observed
the other client's eventual adoption. Verified HTTPS returned `X-Edge: mac1`.
Restoring both records and flushing clients returned requests to `mac2`.
Both edges passed A/B checks in the final recovery. Evidence: E1, E4 and E6.

**Learning summary:** Keep the old edge serving during a DNS transition because
cached clients and established connections can continue using it. Updating only
one DNS server creates inconsistent answers. The standby reduces manual
recovery work, but automatic edge failover would additionally require health
monitoring and traffic steering. This project demonstrates controlled cutover;
it does not claim that DNS changes migrate live TCP sessions or automatically
remove the primary edge as an operational dependency.

### Extension F - Troubleshooting preparation

`phase2/diagnose.sh` checks scoped resolver configuration, OS lookup, each DNS
server, TCP connectivity, DNS-independent verified HTTPS and normal by-name
HTTPS. Drills distinguished wrong client DNS, a wrong record, an unused TCP
port, a certificate hostname mismatch, unavailable backends and loss of both
active DNS services. The actual faculty-injected challenge remains a live
evaluation task. Evidence: E3 and E5; operating commands are in E7.

**Learning summary:** Diagnose the failing layer before making changes. ICMP
reachability does not prove DNS or HTTPS. Refusal concerns a listener/path,
timeouts can reflect availability or filtering, certificate errors concern TLS,
and 502 indicates that the edge could not obtain a valid upstream response.
`--resolve` bypasses DNS while retaining the TLS hostname; `-k` would hide a trust
failure. Fixing one known cause and rechecking is more informative than
restarting every component at once.

## 6. Latest controlled test results

The latest complete real-system rehearsal ran on 23 November 2026. The
restoration snapshot completed at approximately 14:40 IST. The following are
recorded test observations, not a guarantee that services cannot later sleep
or change address. No simulated Newton results are used as acceptance evidence.

| Test | Observed result | Evidence |
| --- | --- | --- |
| Baseline DNS and HTTPS | Both clients receive 200 through mac2 and observe A/B | E1 |
| Primary DNS unavailable | Both clients resolve via backup and use HTTPS | E1 |
| Both active DNS services unavailable | Fresh name requests fail; direct edge HTTP and verified HTTPS still succeed | E3 |
| TTL and standby migration | Updated/flushed clients reach mac1; restored clients return to mac2 | E1, E4 |
| Backend A unavailable/recovered | B-only success, then A/B recovery on both clients | E1 |
| Both backends unavailable | Verified TLS plus HTTP 502; A/B restored afterward | E5 |
| Incorrect client DNS/record | Expected lookup or destination failure, followed by successful restoration | E5 |
| Backend PF isolation | Direct A blocked; edge paths and HTTPS work; rollback recorded | E1 |
| Wrong TCP port | Expected connection failure at unused port 8444 | E3 |
| Wrong TLS hostname | Expected certificate rejection, curl error 60 | E3 |
| HTTP validator | Matching A ETag returns 304; B's different representation returns 200 | E3 |
| Final recovery | DNS, local endpoints, both edges, both names, default trust and A/B pass | E6 |

The Phase 2 capture recorded 1,089 packets with zero kernel drops. TShark
exports contain 23 DNS packets and 1,066 TCP/TLS packets. Captures were taken
on Kavya's interface; remote-client behavior is additionally supported by its
command logs. Encryption limits what can be read from TLS packet payloads.

## 7. Troubleshooting findings and retained failures

- An obsolete dnsmasq listener previously occupied primary DNS port 53. The
  managed service could not bind until that conflicting process was stopped.
- Detached primary-edge launches produced EHOSTUNREACH for remote Backend B.
  A foreground nginx process in a persistent authenticated session passed.
  The precise macOS policy cause was not established; the working launch and
  its session dependency are documented rather than presented as a general fix.
- An early exact-35-second OS-cache assertion failed. A bounded refresh recheck
  passed; both original failure and later observations remain saved.
- The latest supplemental test initially halted because stopping an already
  stopped legacy DNS returned exit 1. This was a test-precondition failure.
  The corrected precondition verified that legacy DNS did not answer; the
  repeated outage test passed. Both attempts and exact test sources are retained.

No claim of success is based on an initial failed attempt. Corrections and
successful repeats are identified separately in the evidence indexes.

## 8. Evidence, reproducibility and restoration

| Reference | Repository location |
| --- | --- |
| E1 - Latest Phase 2 results | [Rehearsal index](../evidence/rehearsal/2026-11-23T143307/README.md), including `phase2/summary.txt`, failure/cutover logs, PCAP and packet fields |
| E2 - Third-Mac migration | [Migration index](../evidence/phase-2/mac3-dns/README.md), including primary-plus-legacy-down proof and original evidence hashes |
| E3 - Supplemental drills | [Corrected results](../evidence/rehearsal/2026-11-23T143307/extra-recheck/extra-cases/summary.json) and [raw commands](../evidence/rehearsal/2026-11-23T143307/extra-recheck/extra-cases/commands.txt) |
| E4 - Isolated cache TTL | [Countdown and cutover log](../evidence/phase-2/mac3-dns/ttl-20261123T090856/client-cache-and-cutover.txt) |
| E5 - Phase 1 failure tests | [Failure summary](../evidence/phase-1/failures-20261123T090450/summary.json) and paired per-client logs |
| E6 - Final recovery | [Recovery summary](../evidence/recovery/2026-11-23T143948/recovery-summary.json) and DNS, endpoints, TLS, edge and PF exports |
| E7 - Live operating guide | [Viva command menu](viva-command-menu.md), [demo guide](tomorrow-demo.md), [DNS setup/rollback](../phase2/MAC3-SETUP.md) |

The rehearsal preservation check verified all 249 pre-existing evidence files
unchanged. The final recovery independently checked its 310-file pre-recovery
snapshot. These counts refer to different capture boundaries. Historical books
and manifests retain their original snapshot; new report files are additional
submission artifacts, not replacements for raw test evidence.

Repeatable orchestration runs from Kavya's Mac using the established SSH
connection and scoped helpers. `phase2/final-tests.py` exercises Phase 2;
`phase2/phase1-failures.py` covers the three additional failures;
`phase2/ttl-cutover.py` measures the isolated cache; `phase2/recover-live.py`
restores and checks the normal deployment. Do not run these concurrently with
manual faults. Per-person commands and expected outputs are in E7.

Normal restoration starts primary DNS on Kavya and backup DNS on Priyanshu,
sets both record sets to Ronit's edge, restores A and B, removes project PF
rules, flushes both client caches and verifies 200/mac2/A/B. Ronit's legacy DNS
remains stopped. Existing healthy nginx sessions are retained; a second nginx
instance must not be started on occupied ports.

## 9. Limitations and live evaluation status

The controlled acceptance tests and saved artifacts are complete within their
stated scope. The independent Backend B rejection test was not performed,
whole-host power/network failures were not injected, and no automatic edge
health monitor or traffic-steering service is implemented. Retry safety for
arbitrary non-idempotent application operations was not evaluated.

Both original clients trust a project CA locally; this is not public-CA trust.
The tested network addresses must be rechecked before presenting. Changing the
ordinary inventory file does not update installed root-owned DNS configuration.
Keep all laptops open, powered and on the same Wi-Fi, and preserve the serving
primary-edge session. The faculty-injected challenge, final spoken presentation
and each member's individual viva remain live assessment activities.

## 10. Team responsibilities

| Member | Demonstration responsibility |
| --- | --- |
| Kavya Katal | Explain topology and request flow; demonstrate primary DNS, Backend B, standby edge, client requests and packet evidence |
| Ronit Singh | Explain nginx, TLS and upstream connections; demonstrate Backend A failure/recovery, load balancing and firewall evidence |
| Priyanshu Tomar | Explain backup DNS; demonstrate matching records, backup query logs, DNS failover and synchronized cutover updates |

These are operational responsibilities. Each member must also understand and
explain the complete system.

## 11. Conclusion

The project demonstrates a complete private request path and controlled recovery
across three Macs, with Priyanshu contributing independent backup DNS while
the original edges and backends retain their placement. Recorded experiments
separate name-resolution failures, transport failures, TLS verification errors
and upstream application failures. Restoration checks and preserved evidence
support the reported results. The final learning outcome is the ability to
explain each layer, select an appropriate test and recover the system without
concealing its remaining operational dependencies.
