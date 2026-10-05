#!/bin/bash
set -e

echo "=== 1. Create TLS working directory ==="
mkdir -p tls/generated

echo
echo "=== 2. Create local Certificate Authority ==="

openssl genrsa \
  -out tls/generated/ca.key \
  2048

openssl req \
  -x509 \
  -new \
  -nodes \
  -key tls/generated/ca.key \
  -sha256 \
  -days 3650 \
  -out tls/generated/ca.crt \
  -subj "/C=IN/ST=Haryana/L=Sonipat/O=CN Project/OU=Local CA/CN=CN Project Local CA"

echo
echo "=== 3. Create server private key ==="

openssl genrsa \
  -out tls/generated/server.key \
  2048

echo
echo "=== 4. Create server CSR ==="

openssl req \
  -new \
  -key tls/generated/server.key \
  -out tls/generated/server.csr \
  -subj "/C=IN/ST=Haryana/L=Sonipat/O=CN Project/OU=Computer Networks/CN=app.cn-project.test"

echo
echo "=== 5. Create SAN extension file ==="

cat > tls/generated/server.ext <<'EXT'
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=@alt_names

[alt_names]
DNS.1=app.cn-project.test
DNS.2=api.cn-project.test
EXT

echo
echo "=== 6. Sign server certificate using local CA ==="

openssl x509 \
  -req \
  -in tls/generated/server.csr \
  -CA tls/generated/ca.crt \
  -CAkey tls/generated/ca.key \
  -CAcreateserial \
  -out tls/generated/server.crt \
  -days 365 \
  -sha256 \
  -extfile tls/generated/server.ext

echo
echo "=== 7. Verify certificate SAN ==="

openssl x509 \
  -in tls/generated/server.crt \
  -text \
  -noout \
  | grep -A2 "Subject Alternative Name"

echo
echo "=== 8. Install CA into macOS System Keychain ==="

sudo security add-trusted-cert \
  -d \
  -r trustRoot \
  -k /Library/Keychains/System.keychain \
  tls/generated/ca.crt

echo
echo "=== 9. Install nginx certificate/key ==="

sudo cp tls/generated/server.crt \
  /opt/homebrew/etc/nginx/certs/server.crt

sudo cp tls/generated/server.key \
  /opt/homebrew/etc/nginx/certs/server.key

sudo chown ronitsingh:staff \
  /opt/homebrew/etc/nginx/certs/server.crt \
  /opt/homebrew/etc/nginx/certs/server.key

chmod 644 /opt/homebrew/etc/nginx/certs/server.crt
chmod 600 /opt/homebrew/etc/nginx/certs/server.key

echo
echo "=== 10. Test nginx configuration ==="

nginx -t -c "$(pwd)/edge/nginx.conf"

echo
echo "=== 11. Reload nginx ==="

nginx -s reload -c "$(pwd)/edge/nginx.conf"

sleep 2

echo
echo "=== 12. Verify HTTPS port ==="

lsof -i :8443 || true

echo
echo "=== 13. STRICT HTTPS TEST — NO -k ==="

curl -i https://app.cn-project.test:8443/api/status

echo
echo
echo "=== 14. HTTPS ROUND-ROBIN TEST ==="

for i in {1..6}; do
    printf "Request %02d: " "$i"

    curl -s \
      -D - \
      https://app.cn-project.test:8443/api/status \
      -o /dev/null \
      | grep -i '^X-Backend:' \
      | tr -d '\r'
done

echo
echo "=== TRUSTED TLS SETUP COMPLETE ==="
