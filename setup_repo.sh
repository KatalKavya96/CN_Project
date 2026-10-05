#!/bin/bash
set -e

echo "Creating CN project repository structure..."

mkdir -p backend-a backend-b dns edge tls tests docs evidence/phase-1

cat > backend-a/app.py <<'PY'
from http.server import BaseHTTPRequestHandler, HTTPServer
import json

ETAG = '"A-v1"'

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get("If-None-Match") == ETAG:
            self.send_response(304)
            self.send_header("ETag", ETAG)
            self.send_header("Cache-Control", "max-age=60")
            self.send_header("X-Backend", "A")
            self.end_headers()
            return

        if self.path == "/api/status":
            body = json.dumps({
                "backend": "A",
                "status": "ok"
            }).encode()
        else:
            body = json.dumps({
                "message": "Backend A running"
            }).encode()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Backend", "A")
        self.send_header("Cache-Control", "max-age=60")
        self.send_header("ETag", ETAG)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

HTTPServer(("0.0.0.0", 3001), Handler).serve_forever()
PY

cat > backend-b/app.py <<'PY'
from http.server import BaseHTTPRequestHandler, HTTPServer
import json

ETAG = '"B-v1"'

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get("If-None-Match") == ETAG:
            self.send_response(304)
            self.send_header("ETag", ETAG)
            self.send_header("Cache-Control", "max-age=60")
            self.send_header("X-Backend", "B")
            self.end_headers()
            return

        if self.path == "/api/status":
            body = json.dumps({
                "backend": "B",
                "status": "ok"
            }).encode()
        else:
            body = json.dumps({
                "message": "Backend B running"
            }).encode()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Backend", "B")
        self.send_header("Cache-Control", "max-age=60")
        self.send_header("ETag", ETAG)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

HTTPServer(("0.0.0.0", 3002), Handler).serve_forever()
PY

cat > dns/project.conf <<'CONF'
address=/app.cn-project.test/10.7.13.163
address=/api.cn-project.test/10.7.13.163

listen-address=127.0.0.1,10.7.25.0
bind-interfaces

cache-size=1000
local-ttl=30
CONF

cat > edge/nginx.conf <<'NGINX'
pid /tmp/cn-project-nginx.pid;

events {}

http {
    upstream cn_backends {
        server 127.0.0.1:3001;
        server 10.7.25.0:3002;
    }

    # HTTP — keep for testing
    server {
        listen 8080;
        server_name app.cn-project.test api.cn-project.test;

        location / {
            proxy_pass http://cn_backends;
            proxy_http_version 1.1;

            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto http;
            proxy_set_header Connection "";
        }
    }

    # HTTPS / TLS
    server {
        listen 8443 ssl;
        server_name app.cn-project.test api.cn-project.test;

        ssl_certificate     /opt/homebrew/etc/nginx/certs/server.crt;
        ssl_certificate_key /opt/homebrew/etc/nginx/certs/server.key;

        ssl_protocols TLSv1.2 TLSv1.3;

        location / {
            proxy_pass http://cn_backends;
            proxy_http_version 1.1;

            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto https;
            proxy_set_header Connection "";
        }
    }
}
NGINX

cat > tls/openssl.cnf <<'CONF'
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = v3_req

[dn]
C = IN
ST = Haryana
L = Sonipat
O = CN Project
OU = Computer Networks
CN = app.cn-project.test

[v3_req]
subjectAltName = @alt_names
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth

[alt_names]
DNS.1 = app.cn-project.test
DNS.2 = api.cn-project.test
CONF

cat > tests/test-backends.sh <<'EOF'
#!/bin/bash
set -e

echo "=== Backend A ==="
curl -i http://127.0.0.1:3001/api/status

echo
echo "=== Backend B ==="
curl -i http://10.7.25.0:3002/api/status
EOF

cat > tests/test-load-balancing.sh <<'EOF'
#!/bin/bash

URL="${1:-http://app.cn-project.test:8080/api/status}"

echo "Testing: $URL"
echo

for i in {1..10}; do
    printf "Request %02d: " "$i"
    curl -s -D - "$URL" -o /dev/null \
        | grep -i '^X-Backend:' \
        | tr -d '\r'
done
EOF

cat > tests/test-dns.sh <<'EOF'
#!/bin/bash

echo "Explicit DNS query to Mac 1:"
dig @10.7.25.0 app.cn-project.test +short
dig @10.7.25.0 api.cn-project.test +short

echo
echo "System resolver:"
dig app.cn-project.test +short
EOF

cat > tests/test-cache.sh <<'EOF'
#!/bin/bash

URL="${1:-http://app.cn-project.test:8080/api/status}"

echo "Initial request:"
curl -i "$URL"

echo
echo "Conditional request:"
curl -i -H 'If-None-Match: "A-v1"' "$URL"
EOF

cat > tests/test-connectivity.sh <<'EOF'
#!/bin/bash

echo "Mac 1:"
ping -c 3 10.7.25.0

echo
echo "Mac 2:"
ping -c 3 10.7.13.163
EOF

chmod +x tests/*.sh

cat > docs/architecture.md <<'EOF'
# Phase 1 two-Mac architecture

| Mac | LAN IP | Role and ports |
| --- | --- | --- |
| Mac 1 — Kavya | `10.7.25.0` | Primary DNS `:53`, client, Backend B `:3002` |
| Mac 2 — Ronit | `10.7.13.163` | nginx HTTP `:8080` / HTTPS `:8443`, TLS termination, round-robin load balancer, Backend A `:3001` |

Both Macs share a reachable private LAN. The client on Mac 1 queries its primary DNS service for `app.cn-project.test` or `api.cn-project.test`; both names resolve to `10.7.13.163` (Mac 2). Mac 2 can also query Mac 1 DNS.

```text
Client (Mac 1)
  ├─ DNS query → Mac 1 :53 → app/api.cn-project.test = 10.7.13.163
  └─ HTTPS → Mac 2 nginx :8443 (TLS terminates here)
                    ├─ Backend A, Mac 2 127.0.0.1:3001
                    └─ Backend B, Mac 1 10.7.25.0:3002
```

nginx also listens on `:8080` for HTTP testing. The HTTPS client knows only the edge name and port. nginx forwards HTTP requests to the two backends in round-robin order and returns their JSON, `X-Backend`, cache headers, and ETags. The response returns over the same TCP/TLS connection to the client.
EOF

cat > docs/runbook.md <<'EOF'
# Demo Runbook

1. Show topology and IPs
2. Ping both Macs
3. Show Backend A and Backend B directly
4. Show nginx load balancing
5. Show DNS resolution
6. Show HTTPS
7. Show Cache-Control and 304
8. Stop one backend and prove the other still serves
9. Show Wireshark DNS/TCP/TLS packets
10. Explain troubleshooting order:
   DNS → TCP → TLS → HTTP/Application
EOF

cat > README.md <<'EOF'
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
EOF

cat > .gitignore <<'EOF'
.DS_Store
__pycache__/
*.pyc

# Do not commit TLS private keys/certs
*.key
*.pem
*.crt
EOF

echo
echo "Repository files created successfully."
echo "Next:"
echo "  git add ."
echo '  git commit -m "Add complete CN project implementation structure"'
echo "  git push"
