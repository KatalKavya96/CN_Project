# Acceptance Summary - 22 November 2026

All six network acceptance groups have passing live evidence on both Macs.
HTTPS initially used explicit CA validation, never `-k`. Following approved
user-keychain installation on Mac 1, plain HTTPS also passes on both Macs with
default trust: hostname match, certificate verification, HTTP 200 and exit 0.
See `final/default-trust-mac1-verified.txt` and `final/default-trust-mac2-verified.txt`.

| Test group | Result | Evidence |
| --- | --- | --- |
| By-name baseline | PASS | `final/baseline-by-name.txt` (both clients, A/B) |
| Primary DNS stop and OS failover | PASS | `final/primary-stopped-direct-query.txt`, `primary-down-os-lookup.txt`, `primary-down-by-name-https.txt`, `backup-query-log.txt` in `final/` |
| OS-cache TTL and DNS edge migration | PASS on measured-refresh recheck | `final-cutover-recheck/summary.txt` and the paired cache, DNS, flush and HTTPS logs |
| By-name backend failure/recovery | PASS | `final/backend-a-down-by-name.txt`, `backend-a-restored-by-name.txt` in `final/` |
| Integrated firewall isolation/rollback | PASS within two-host scope | `final/isolation-blocked-client.txt`, `isolation-allowed-edge.txt`, `isolation-https-by-name.txt`, `isolation-counters.txt`, `isolation-rollback.txt` in `final/` |
| Restored by-name service | PASS | `final/final-by-name-health.txt`, `final-cutover-recheck/cutover-restored-by-name.txt` |

The first suite recorded a failed OS-cache check because it expected the first
lookup at exactly TTL+5 seconds to return a new address. That first lookup
returned an old answer while triggering refresh. The corrected test polls and
records refresh for up to 60 additional seconds. It observed the new address
on the next poll. The original `final/summary.txt` is deliberately retained;
the recheck summary supersedes only its cache/cutover failure, not any other test.

Open `final/dns-failover-cutover.pcap` or
`final-cutover-recheck/dns-failover-cutover.pcap` in Wireshark.
`final/dns-packet-index.tsv` and `final/tls-packet-index.tsv` locate DNS answers,
ClientHello/SNI, ServerHello and TLS records.

Real troubleshooting drills produced TCP connection refusal and TLS SAN
mismatch errors under `troubleshooting/`. Both complete diagnostic scripts
ran successfully after recovery, under `final/diagnostics-mac*.txt`.

Remaining human/evaluation requirements: spoken rehearsal and individual viva,
and the live faculty-injected fault. Earlier canceled trust authorization and
failed curl attempts are historical; the final `default-trust-mac*-verified.txt`
files supersede them. A third independent client would strengthen Backend B
rejection evidence; it is unavailable in the two-Mac deployment.

The three outstanding Phase 1 failure demonstrations now also have results on
both clients: see `../phase-1/failures-2026-11-22/README.md` and `summary.json`.
Wrong DNS is demonstrated with a temporary client-scoped resolver; wrong
project records and both-backends-down are injected into the real service.
All services and DNS records are restored and both edges again serve A/B.
