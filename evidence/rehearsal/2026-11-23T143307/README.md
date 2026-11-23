# Live rehearsal on the three real Macs — 23 November 2026

This run exercised the actual services. No NPT model was involved. Both original
client Macs were tested; Priyanshu supplied the Phase 2 backup DNS.

| Test | Observed result | Evidence |
| --- | --- | --- |
| Normal DNS, HTTPS and A/B balancing | PASS on both clients | [Phase 2 summary](phase2/summary.txt), [baseline](phase2/baseline-by-name.txt) |
| Primary DNS stopped | Both clients resolve through Priyanshu and use HTTPS | [OS lookups](phase2/primary-down-os-lookup.txt), [HTTPS](phase2/primary-down-by-name-https.txt), [backup log](phase2/backup-query-log.txt) |
| DNS edge cutover and OS cache expiry | Both clients adopt standby; normal edge restored | [Authoritative answers](phase2/cutover-authoritative.txt), [post-TTL lookups](phase2/cutover-after-ttl-os-cache.txt), [restored HTTPS](phase2/cutover-restored-by-name.txt) |
| Backend A stopped and restarted | B serves requests; then A/B return | [A down](phase2/backend-a-down-by-name.txt), [recovery](phase2/backend-a-restored-by-name.txt) |
| PF isolation and rollback | Direct A access blocked; allowed edge paths and HTTPS work; rules removed | [Blocked client](phase2/isolation-blocked-client.txt), [allowed paths](phase2/isolation-allowed-edge.txt), [rollback](phase2/isolation-rollback.txt) |
| Wrong client DNS, wrong DNS record, both backends stopped | PASS on both clients; both-backend failure returns 502; services restored | [Phase 1 results](../../phase-1/failures-20261123T090450/summary.json) |
| Wrong port and incorrect TLS hostname | Connection fails at wrong port; certificate rejects wrong hostname; valid HTTPS still works | [Supplement results](extra-recheck/extra-cases/summary.json), [raw commands](extra-recheck/extra-cases/commands.txt) |
| HTTP cache headers and validator | Real 304 and 200 responses with ETag and Cache-Control | [Raw commands](extra-recheck/extra-cases/commands.txt) |
| Both active DNS services stopped | Fresh hostname requests fail, while direct HTTP and verified DNS-bypassed HTTPS succeed; DNS restored | [Supplement results](extra-recheck/extra-cases/summary.json), [raw commands](extra-recheck/extra-cases/commands.txt) |
| Separate isolated cache TTL | Countdown, old/fresh destinations, expiry and manual flush passed | [TTL observations](../../phase-2/mac3-dns/ttl-20261123T090856/client-cache-and-cutover.txt) |
| Final live restoration | LAN, DNS, endpoints, both edges, default trust and A/B verified | [Recovery result](../../recovery/2026-11-23T143948/recovery-summary.json) |

The packet capture contains 1,089 captured packets with zero kernel drops.
Open [the PCAP](phase2/dns-failover-cutover.pcap) in Wireshark, or inspect
[DNS fields](phase2/dns-packets.tsv) and [TCP/TLS fields](phase2/tcp-tls-packets.tsv).

The initial supplement in `extra-cases/` halted before stopping active DNS:
the retired Mac 2 DNS was already stopped, and its non-idempotent stop helper
returned exit 1. The corrected precondition verifies that legacy DNS does not
answer. `extra-recheck/` contains the successful full repeat. Both attempts and
their exact test sources are retained; the first is not passing outage evidence.

Scope: wrong client DNS is a temporary client-scoped experiment; global DNS
preferences are unchanged. A wrong TLS hostname tests certificate rejection;
HTTPS itself was not disabled. No laptop, Wi-Fi interface, or primary nginx
serving session was shut down. The firewall proof retains the original two-client
scope and does not add an independent third-source Backend B rejection test.

Normal final state: Kavya primary DNS + Backend B + standby edge; Ronit primary
edge + Backend A; Priyanshu backup DNS. Both DNS services advertise Ronit's edge.
Ronit's retired DNS remains stopped. The preservation check in `summary.json`
covers every one of the 249 evidence files present before this rehearsal.
