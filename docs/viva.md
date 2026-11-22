# Phase 2 Viva Preparation

All three members should explain these from understanding, then swap machine roles
in a spoken rehearsal. Use the real evidence rather than memorizing a claim.

1. **What fails when primary DNS stops?** Only that DNS service. A flushed
   client can query backup DNS and still reach the existing edge and backends.
   An already cached name or open connection might continue without any DNS query.
2. **Why does NXDOMAIN differ from timeout?** NXDOMAIN is an actual negative
   DNS answer. Timeout means no answer arrived. Multiple resolver addresses do
   not imply retrying every negative answer against a different server.
3. **What does TTL 30 mean?** DNS data may be reused for that time by a cache.
   Our isolated client resolver showed a countdown; macOS also showed a short
   refresh delay after the nominal TTL. We recorded the observed behavior.
4. **Does DNS cutover move an existing connection?** No. Existing TCP/TLS
   connections can stay on the old edge. New connections after new resolution
   use the new address, so keep both edges serving through migration.
5. **How do we prove a different edge handled the request?** `X-Edge` is mac1
   or mac2, and upstream logs record the actual backend address and status.
   `X-Backend` identifies A or B; it does not identify the edge.
6. **How does nginx detect failure?** Passive request failures increment its
   failure state. Our settings mark a failed backend unavailable for five
   seconds and retry another backend, with a two-second connect timeout.
   No periodic active health probe is configured.
7. **Why do refusal and packet loss differ?** A TCP RST fails quickly. Silent
   drops wait for a timeout, which makes explicit upstream timeouts useful.
8. **Can we stop the whole Mac to simulate stopping A?** On Mac 2 that also
   removes primary nginx. Backup DNS stays on Priyanshu's Mac. The experiment stops only Backend A's
   process. Combined roles share host failures, called fate sharing.
9. **What remains a single point of failure?** The primary edge until traffic
   is manually moved; also shared LAN/router infrastructure. Standby plus DNS
   cutover is controlled recovery, not an automatic traffic failover service.
10. **What do the PF rules do?** On each backend's LAN interface, allow Mac 2's
    source IP and block other sources to the backend port. State tracks replies.
    The project uses a dedicated anchor and releases only its own PF reference.
11. **What did the original two-Mac firewall test not prove independently?** Backend B's unrelated-client
    rejection needs a third source IP. Mac 1's local access uses loopback, and
    Mac 2 shares the allowed edge IP. We prove A rejection, B allowed access,
    counters, and continuing HTTPS and document that limitation. Mac 3 now
    supplies DNS only; the migration did not add a third-source firewall test.
12. **Why does `--cacert` differ from `-k`?** The public CA file establishes
    trust while still verifying chain, hostname and validity. `-k` disables
    checks and is not used. Both Macs now also pass plain HTTPS with default
    trust after the approved CA installation on Mac 1.
13. **Why does `--resolve` help diagnosis?** It supplies an IP for a hostname
    while keeping the hostname for TLS/SNI and HTTP. That bypasses only DNS;
    it cannot prove the OS resolver or its cache. The final by-name tests omit it.
14. **Where are the layers visible?** DNS query/answer; TCP SYN/SYN-ACK/ACK with
    ephemeral client port and destination 8443; TLS ClientHello/SNI and
    ServerHello; encrypted records. curl exposes decrypted HTTP headers.
15. **How do we handle an injected fault?** Check scoped resolver and name,
    then TCP port, then validated TLS, then HTTP/upstream logs. State each
    observation and what it rules out before changing anything. Use the
    wrong-port and wrong-hostname drill evidence to distinguish TCP and TLS.

Follow `docs/runbook.md` for the 11-step presentation. Restore primary records,
both DNS services and backends, clear test PF anchors, and verify A/B HTTPS
before ending any rehearsal.
