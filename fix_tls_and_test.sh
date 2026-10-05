#!/bin/bash
set -e

echo "=== 1. Fix TLS certificate permissions ==="

sudo chown ronitsingh:staff /opt/homebrew/etc/nginx/certs/server.crt
sudo chown ronitsingh:staff /opt/homebrew/etc/nginx/certs/server.key

chmod 644 /opt/homebrew/etc/nginx/certs/server.crt
chmod 600 /opt/homebrew/etc/nginx/certs/server.key

echo
echo "Current certificate permissions:"
ls -l /opt/homebrew/etc/nginx/certs/

echo
echo "=== 2. Test nginx configuration ==="

nginx -t -c "$(pwd)/edge/nginx.conf"

echo
echo "=== 3. Reload nginx with HTTPS config ==="

nginx -s reload -c "$(pwd)/edge/nginx.conf"

sleep 1

echo
echo "=== 4. Check HTTP port 8080 ==="

lsof -i :8080 || true

echo
echo "=== 5. Check HTTPS port 8443 ==="

lsof -i :8443 || true

echo
echo "=== 6. Test HTTPS endpoint ==="

curl -i https://app.cn-project.test:8443/api/status

echo
echo
echo "=== 7. Test HTTPS round-robin load balancing ==="

for i in {1..6}; do
  printf "Request %02d: " "$i"
  curl -s -D - https://app.cn-project.test:8443/api/status \
    -o /dev/null \
    | grep -i '^X-Backend:' \
    | tr -d '\r'
done

echo
echo "=== TLS + HTTPS test complete ==="
