#!/bin/bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
source "$ROOT/phase2/lab.env"
ROLE=${1:?Usage: bash phase2/render.sh mac1|mac2}
case "$ROLE" in
  mac1) OWN_IP=$MAC1_IP; A_ADDR=$MAC2_IP; B_ADDR=127.0.0.1; EDGE_ID=mac1 ;;
  mac2) OWN_IP=$MAC2_IP; A_ADDR=127.0.0.1; B_ADDR=$MAC1_IP; EDGE_ID=mac2 ;;
  *) echo 'Expected mac1 or mac2' >&2; exit 1 ;;
esac
RUNTIME="$ROOT/.runtime"
mkdir -p "$RUNTIME" "$ROOT/evidence/phase-2"/{baseline,dns-failover,ttl,ha,isolation,edge-migration,troubleshooting}
chmod 700 "$RUNTIME"
if [ ! -f "$RUNTIME/records.hosts" ]; then
  printf '%s app.cn-project.test api.cn-project.test\n' "$MAC2_IP" > "$RUNTIME/records.hosts"
fi
cat > "$RUNTIME/dnsmasq.conf" <<EOF
port=53
listen-address=127.0.0.1,$OWN_IP
bind-interfaces
no-resolv
no-hosts
local=/cn-project.test/
addn-hosts=$RUNTIME/records.hosts
local-ttl=$DNS_TTL
cache-size=1000
pid-file=$RUNTIME/dnsmasq.pid
log-queries
log-facility=$RUNTIME/dnsmasq.log
EOF
cat > "$RUNTIME/resolver.conf" <<EOF
nameserver $MAC1_IP
nameserver $MAC2_IP
EOF
cat > "$RUNTIME/nginx.conf" <<EOF
pid $RUNTIME/nginx.pid;
error_log $RUNTIME/nginx-error.log info;
events {}
http {
    log_format upstream_trace '\$time_iso8601 client=\$remote_addr edge=$EDGE_ID status=\$status upstream=\$upstream_addr upstream_status=\$upstream_status time=\$upstream_response_time';
    access_log $RUNTIME/nginx-access.log upstream_trace;
    upstream cn_backends {
        server $A_ADDR:3001 max_fails=1 fail_timeout=5s;
        server $B_ADDR:3002 max_fails=1 fail_timeout=5s;
    }
    server {
        listen 8080;
        listen 8443 ssl;
        server_name app.cn-project.test api.cn-project.test;
        ssl_certificate $RUNTIME/server.crt;
        ssl_certificate_key $RUNTIME/server.key;
        ssl_protocols TLSv1.2 TLSv1.3;
        add_header X-Edge $EDGE_ID always;
        location / {
            proxy_pass http://cn_backends;
            proxy_http_version 1.1;
            proxy_set_header Host \$host;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_connect_timeout 2s;
            proxy_read_timeout 5s;
            proxy_next_upstream error timeout http_502 http_503 http_504;
            proxy_next_upstream_tries 2;
        }
    }
}
EOF
printf '%s\n' "$ROLE" > "$RUNTIME/role"
/opt/homebrew/sbin/dnsmasq --test --conf-file="$RUNTIME/dnsmasq.conf"
echo "Rendered $ROLE configs in $RUNTIME"
