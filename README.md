# CN Project — Private Network Service Platform

## Objective, team, and scope

Phase 1 builds a private LAN service and demonstrates the DNS → TCP → TLS → HTTP request path. The application is deliberately simple; the network is the project. Team: Kavya Katal and Ronit Singh. This repository describes the **Phase 1 two-Mac deployment only**.

## Architecture

| Machine | Current LAN IP | Roles | Services |
| --- | --- | --- | --- |
| Mac 1 — Kavya | `10.7.25.0` | Primary DNS, client/test machine, Backend B | DNS UDP/TCP 53; Backend B TCP 3002 |
| Mac 2 — Ronit | `10.7.13.163` | nginx edge, TLS termination, round-robin load balancer, Backend A | Backend A TCP 3001; HTTP TCP 8080; HTTPS TCP 8443 |

Both Macs must be on the same reachable private LAN. Verify each current address with `ifconfig en0` and test reachability with `./tests/test-connectivity.sh` before the demo. These are current lab addresses and may need updating on a different LAN. See [architecture](docs/architecture.md) for the request path.

`app.cn-project.test` and `api.cn-project.test` both resolve to **`10.7.13.163`** through Mac 1 DNS. The client resolves the name at Mac 1, connects to nginx on Mac 2 at `:8443`, and nginx terminates TLS and distributes requests between local Backend A (`127.0.0.1:3001`) and Backend B on Mac 1 (`10.7.25.0:3002`). The client never needs a backend address.

## Dependencies and startup

Install Python 3 and Homebrew `dnsmasq` on Mac 1. Install Python 3, Homebrew `nginx`, and OpenSSL on Mac 2. Use the executable paths appropriate to each Mac. Commands below run from this repository's root. **Do not run `setup_repo.sh` over an existing checkout; it generates starter files and overwrites files.**

### Mac 1 — Kavya

Create `/etc/resolver/cn-project.test` with this content (administrator access required):

```text
nameserver 10.7.25.0
```

Configure Mac 2 to use Mac 1 for this domain too (a matching `/etc/resolver/cn-project.test` is sufficient). Start the primary DNS and Backend B in separate terminals:

```bash
sudo /opt/homebrew/sbin/dnsmasq --keep-in-foreground --conf-file="$(pwd)/dns/project.conf"
python3 backend-b/app.py
```

If dnsmasq is already running, use its existing service configuration; do not start a second instance on port 53. `dnsmasq --test --conf-file="$(pwd)/dns/project.conf"` checks syntax without starting it.

### Mac 2 — Ronit

Place the server certificate and private key at the paths configured in `edge/nginx.conf` and ensure nginx can read them. Start Backend A and validate/start nginx in separate terminals:

```bash
python3 backend-a/app.py
nginx -t -c "$(pwd)/edge/nginx.conf"
nginx -c "$(pwd)/edge/nginx.conf"
```

The nginx config uses `/tmp/cn-project-nginx.pid`, separate from a default nginx configuration. Do not start another nginx instance if the service is already listening on 8080/8443.

## TLS trust

`tls/openssl.cnf`, `tls/generated/server.ext`, and `fix_trusted_tls.sh` document the local-CA certificate setup. The server certificate must include both private names in its SANs. The CA private key and server private key must stay private on Mac 2; `*.key`, `*.pem`, and `*.crt` are ignored and intentionally absent from Git. Share **only the public CA certificate** (`ca.crt`) with each client Mac and install it in that client's trust store, or use it explicitly with `/usr/bin/curl --cacert /path/to/ca.crt`. If the original CA is unavailable, regenerate the CA and server certificate on Mac 2 using the setup script, then redistribute the new public CA certificate. Review that script before running it: it changes certificates, keychain trust, and nginx runtime state. Never commit private keys or use `curl -k` as final TLS proof.

## Verification

Run these from Mac 1 after services and certificate trust are ready:

```bash
dig @10.7.25.0 app.cn-project.test +short
dig @10.7.25.0 api.cn-project.test +short
/usr/bin/curl -i http://10.7.25.0:3002/api/status
/usr/bin/curl -i http://app.cn-project.test:8080/api/status
/usr/bin/curl -i https://app.cn-project.test:8443/api/status
./tests/test-load-balancing.sh "https://app.cn-project.test:8443/api/status"
```

Run `curl -i http://127.0.0.1:3001/api/status` and `./tests/test-backends.sh` **on Mac 2**, where Backend A is local. If the CA is not installed in curl's trust store, add `--cacert /path/to/ca.crt` to the HTTPS commands; this still performs certificate validation. `./tests/test-dns.sh` checks both records. `./tests/test-cache.sh` defaults to HTTP and can take an HTTPS URL after trust is configured.

Both backends return JSON at `/` and `/api/status`. Status responses identify the backend with `X-Backend: A` or `B`, include `Cache-Control: max-age=60` and an `ETag` (`"A-v1"` or `"B-v1"`), and return `304 Not Modified` for a matching `If-None-Match`. For example:

```bash
/usr/bin/curl -i -H 'If-None-Match: "A-v1"' https://app.cn-project.test:8443/api/status
```

Because requests alternate between A and B, repeat the conditional request if it first reaches B. A fresh cache hit reuses stored content; a conditional request asks the server whether stored content changed; an ordinary new request retrieves the full response.

## Failure behavior and packet evidence

When Backend A is unavailable, nginx can continue serving Backend B. When both backends are unavailable, DNS and the TLS edge may still work but the application returns `502 Bad Gateway`. After restoring A, requests should again reach both backends. Run service-stopping demonstrations only during a planned test window and verify recovery; existing evidence is under `evidence/phase-1/`.

The packet screenshots show a DNS query/response, TCP SYN → SYN-ACK → ACK, TLS Client Hello with `app.cn-project.test` SNI, Server Hello, and encrypted Application Data. The DNS query uses port 53; the HTTPS connection uses destination port 8443 and a client ephemeral source port. These establish the DNS → TCP → TLS path; use curl headers to show the HTTP response because the HTTPS payload is encrypted in the capture.

Phase 2 DNS failover, firewall isolation, and edge migration are outside this submission.
