# Phase 2: Backup DNS on Priyanshu's Mac

Updated 23 November 2026 IST. Directory names and raw logs use UTC where marked
(22 November UTC is 23 November in India). Original two-Mac evidence is preserved.

| Machine | Active role |
| --- | --- |
| Kavya, 10.7.26.228 | Primary DNS, Backend B, standby edge, client |
| Ronit, 10.7.18.166 | Primary edge, Backend A, client; legacy backup DNS stopped |
| Priyanshu, 10.7.26.237 | Phase 2 backup DNS only, UDP/TCP 53 |

Both clients' `/etc/resolver/cn-project.test` now lists `10.7.26.228` then
`10.7.26.237`. Both names normally answer `10.7.18.166`, TTL 30.
No backend, edge, CA trust, private key, or Phase 1 role was moved to Mac 3.
Internet Sharing on Mac 3 was left unchanged; its specifically bound DNS works.

| Check | Result | Evidence |
| --- | --- | --- |
| Candidate UDP/TCP 53, both names from both clients | PASS, answer and TTL checked | [Migration commands](migration-20261122T211927/commands.txt) |
| OS resolver fallback and plain HTTPS on both clients, with primary AND legacy backup stopped | PASS | [Migration summary](migration-20261122T211927/summary.json), [commands](migration-20261122T211927/commands.txt) |
| Original evidence preservation | All 163 pre-migration files unchanged | [Original hashes](migration-20261122T211927/prior-evidence-sha256.json) |
| Phase 2 baseline, real OS DNS failover, TTL cutover, backend recovery, PF isolation and rollback, final health | All six groups PASS | [Final suite summary](final-20261123/summary.txt), [raw directory](final-20261123/) |
| Phase 1 wrong client DNS, wrong DNS record, both backends stopped, restoration | PASS on both clients | [New Phase 1 results](../../phase-1/failures-20261122T212149/summary.json) |
| Isolated cache TTL countdown, stale/fresh destinations, expiry and manual flush | PASS; distinct from OS resolver test above | [TTL log](ttl-20261122T212228/client-cache-and-cutover.txt) |
| Fresh DNS → TCP → TLS → HTTPS protocol capture | Recorded against Mac 3 DNS | [PCAP](protocol-20261122T212320/dns-tcp-tls-current.pcap), [verified request](protocol-20261122T212320/capture-request.txt) |
| Actual failure/cutover packet capture | 1,111 captured packets, zero kernel drops | [PCAP](final-20261123/dns-failover-cutover.pcap), [capture log](final-20261123/packet-capture.log) |
| Wireshark/TShark field exports | 23 DNS packets, 1,088 TCP/TLS packets | [DNS](final-20261123/dns-packets.tsv), [TCP/TLS](final-20261123/tcp-tls-packets.tsv) |
| Final restored endpoints, LAN, both names, default trust, A/B on both edges | PASS; 223 pre-recovery evidence files unchanged | [Recovery summary](../../recovery/2026-11-23T025332/recovery-summary.json) |

Open the [evidence book](evidence-book.html) for excerpts and direct source links.
The [manifest](manifest.json) records current file hashes. The older submission
book and manifest retain their original capture state and are historical;
this supplement records the new topology without rewriting those artifacts.
These are real logs and packet exports, not manufactured terminal screenshots.

The new suite retains the original two-client firewall test scope. A third-source
Backend B rejection test was not added because Mac 3's requested role is DNS only.
Faculty-injected fault, spoken demonstration and individual viva remain live tasks.

Use the [updated three-person guide](../../../docs/tomorrow-demo.md). Keep all
three Macs awake on the same Wi-Fi. Start DNS on Kavya and Priyanshu only.
The old DNS on Ronit is retained for rollback, not a third active resolver.
See [rollback instructions](../../../phase2/MAC3-SETUP.md).
