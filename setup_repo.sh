#!/bin/bash
set -e

echo "Creating CN project repository structure..."

mkdir -p backend-a backend-b dns edge tls tests docs evidence/phase-1 evidence/phase-2

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
address=/app.cn-project.test/10.7.3.153
address=/api.cn-project.test/10.7.3.153

listen-address=127.0.0.1,10.7.29.7
bind-interfaces

cache-size=1000
local-ttl=30
CONF

cat > edge/nginx.conf <<'NGINX'
events {}

http {
    upstream cn_backends {
        server 10.7.3.153:3001 max_fails=2 fail_timeout=5s;
        server 10.7.29.7:3002 max_fails=2 fail_timeout=5s;
    }

    server {
        listen 8080;
        server_name app.cn-project.test;

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

    server {
        listen 8443 ssl;
        server_name app.cn-project.test;

        ssl_certificate     /opt/homebrew/etc/nginx/certs/server.crt;
        ssl_certificate_key /opt/homebrew/etc/nginx/certs/server.key;

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
curl -i http://10.7.3.153:3001/api/status

echo
echo "=== Backend B ==="
curl -i http://10.7.29.7:3002/api/status
EOF

cat > tests/test-load-balancing.sh <<'EOF'
#!/bin/bash

URL="${1:-http://10.7.3.153:8080/api/status}"

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
dig @10.7.29.7 app.cn-project.test +short

echo
echo "System resolver:"
dig app.cn-project.test +short
EOF

cat > tests/test-cache.sh <<'EOF'
#!/bin/bash

URL="${1:-http://10.7.3.153:8080/api/status}"

echo "Initial request:"
curl -i "$URL"

echo
echo "Conditional request:"
curl -i -H 'If-None-Match: "A-v1"' "$URL"
EOF

cat > tests/test-connectivity.sh <<'EOF'
#!/bin/bash

echo "Mac 1:"
ping -c 3 10.7.29.7

echo
echo "Mac 2:"
ping -c 3 10.7.3.153
EOF

chmod +x tests/*.sh

cat > docs/architecture.md <<'EOF'
# Two-Mac Architecture

## Mac 1 — 10.7.29.7
- Private DNS
- Test Client
- Backend B on port 3002

## Mac 2 — 10.7.3.153
- nginx Reverse Proxy
- TLS Termination
- Load Balancer
- Backend A on port 3001

## Request Flow

Client on Mac 1
→ DNS on Mac 1
→ app.cn-project.test resolves to Mac 2
→ nginx on Mac 2
→ Backend A on Mac 2:3001
or
→ Backend B on Mac 1:3002
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

## Two-Mac Deployment

### Mac 1
- IP: 10.7.29.7
- DNS
- Client
- Backend B :3002

### Mac 2
- IP: 10.7.3.153
- nginx Edge
- Backend A :3001
- TLS
- Load Balancer

## Flow

Client
→ DNS
→ nginx Edge
→ Backend A / Backend B

## Core Tests

```bash
./tests/test-backends.sh
./tests/test-load-balancing.sh
./tests/test-dns.sh
./tests/test-cache.sh
```
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
