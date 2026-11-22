# Phase 2 Evidence Index

Collected live on 22 November 2026. Phase 1 artifacts elsewhere retain their
October addresses. Start with [acceptance summary](acceptance-summary.md) for
the final results; earlier diagnostic failures are retained below.

| Requirement | Evidence | What it proves |
| --- | --- | --- |
| Protocol flow | `baseline/dns-tcp-tls-current.pcap`, `baseline/capture-request.txt` | Explicit backup DNS query/answer, TCP handshake, TLS and verified HTTPS |
| Backup resolver readiness | `dns-failover/backup-direct.txt`, `backup-api-direct.txt` in that directory | Backup answers both names with TTL 30; not OS failover |
| Standby readiness | `edge-migration/standby-direct.txt` | Mac 1 serves verified HTTPS and both backends; not DNS cutover |
| Backend failure | `ha/standby-a-down.txt` | Standby serves B only while A is stopped |
| Backend recovery | `ha/standby-a-restored.txt` | Standby resumes A/B responses after A restarts |
| Backend A isolation | `isolation/mac1-to-backend-a-blocked.txt`, `mac2-local-a-and-counters.txt` in that directory | Direct client access blocked; local edge access works; PF drops counted |
| Firewall rollback | `isolation/mac2-before.txt`, `mac2-rollback.txt` in that directory | Project rules removed and own enable reference released |
| HTTP caching | `baseline/cache-headers.txt`, `conditional-attempt-1.txt`, `conditional-attempt-2.txt` in that directory | Cache-Control, ETags and actual 304 responses |
| Troubleshooting | `troubleshooting/wrong-port-dns-bypassed.txt`, `wrong-tls-hostname.txt` in that directory | TCP refusal and TLS hostname mismatch distinguished |
| Upstream paths | `baseline/mac2-upstream-log.txt`, `edge-migration/mac1-upstream-log.txt` | Actual selected upstreams and failed attempts |
| Primary edge readiness | `baseline/primary-edge-persistent-ssh.txt` | Verified HTTPS with both backends in the working launch mode |
| Primary HA | `ha/primary-a-down.txt`, `primary-a-restored.txt` in that directory | B-only success during A failure, then A/B recovery |
| TTL and cutover | `ttl/client-cache-and-cutover.txt` | Actual DNS change, cached old versus fresh new edge, TTL countdown and expiry, manual client-cache flush |
| Backend B allow policy | `isolation/mac2-to-backend-b-allowed.txt`, `mac1-rules-and-counters.txt`, `mac1-rollback.txt` in that directory | Mac 2 LAN access remains allowed; project PF rules rolled back |

Files containing `initial`, `after-reload`, or `latest` retain diagnostic
failures. Daemon/detached primary-edge probes failed with no route to Backend B;
the later persistent foreground SSH launch passes. Failed files are not passing
evidence. The TTL/cutover test uses an isolated caching DNS resolver on client
port 1053, with HTTPS destinations derived from real DNS answers. It does not
claim macOS system-resolver caching or failover. Later real OS tests in `final/`
and `final-cutover-recheck/` passed on both Macs after the primary DNS repair.
Use the acceptance summary for their results and remaining evaluation caveats.
