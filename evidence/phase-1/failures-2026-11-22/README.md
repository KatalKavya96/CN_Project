# Phase 1 Failure Demonstrations - 22 November 2026

All three outstanding experiments passed from both Macs. `summary.json` lists
the results; each text log includes commands, timestamps, exit codes and actual
stdout/stderr. Plain HTTPS uses default certificate trust; no `-k` is used.

| Experiment | Mac 1 evidence | Mac 2 evidence | Observed result |
| --- | --- | --- | --- |
| Wrong client DNS server | `wrong-dns-mac1.txt` | `wrong-dns-mac2.txt` | Temporary client resolver forwards to wrong server 127.0.0.2:53; DNS query fails with exit 9. Peer ping and DNS-independent verified HTTPS still succeed. |
| Wrong IP in real project DNS | `wrong-record-mac1.txt` | `wrong-record-mac2.txt` | Real DNS answers Mac 1's IP with NOERROR, but its standby edge is intentionally stopped. OS lookup succeeds; by-name HTTPS fails at TCP with curl exit 7. Correct edge reached with `--resolve` still verifies and returns 200. |
| Both backends stopped | `both-backends-down-mac1.txt` | `both-backends-down-mac2.txt` | DNS still resolves to Mac 2, TLS verifies normally, and nginx returns HTTP 502 Bad Gateway. |

## Scope of the wrong-DNS experiment

Each Mac runs a temporary unprivileged dnsmasq client resolver at
127.0.0.1:1053 with `server=127.0.0.2`, `no-resolv`, `no-hosts`, and no cache.
The saved configuration and forwarding log prove it actually uses the wrong
upstream. dig queries this explicitly configured client resolver. This is a
client-scoped resolver test, not a change to macOS global Network settings or
`/etc/resolver/cn-project.test`. Both system resolver configurations remain intact.
The temporary client resolver is stopped in a finally block.

## Restoration

- `wrong-record-restoration.txt`: DNS returned to Mac 2, client caches flushed,
  standby nginx restarted, and both clients returned verified HTTPS 200.
- `both-backends-restoration.txt`: both backends restarted and eight by-name
  HTTPS requests from each Mac again observed both A and B.
- `standby-restored-mac1.txt` and `standby-restored-mac2.txt`: restarted standby
  edge separately verified with six requests each and both backends observed.
- `restoration.txt`: both DNS configurations restored to the primary edge and
  both client caches flushed at the end of the suite.

No project firewall or user trust settings were changed by these experiments.
Repeat from Mac 1 with `/usr/bin/python3 phase2/phase1-failures.py` during a
planned failure-test window; it briefly changes records and stops services.
