#!/bin/bash

echo "========================================="
echo "1. VERIFY CERTIFICATE CHAIN DIRECTLY"
echo "========================================="

openssl verify \
  -CAfile tls/generated/ca.crt \
  tls/generated/server.crt

echo
echo "========================================="
echo "2. SHOW WHICH CURL IS BEING USED"
echo "========================================="

which curl
curl -V

echo
echo "========================================="
echo "3. TEST WITH macOS SYSTEM CURL"
echo "========================================="

/usr/bin/curl -i \
  https://app.cn-project.test:8443/api/status

SYSTEM_RESULT=$?

echo
echo "========================================="
echo "4. STRICT OPENSSL-CURL TEST WITH OUR CA"
echo "========================================="

curl \
  --cacert tls/generated/ca.crt \
  -i \
  https://app.cn-project.test:8443/api/status

echo
echo "========================================="
echo "5. HTTPS LOAD BALANCING"
echo "========================================="

for i in {1..6}; do
    printf "Request %02d: " "$i"

    curl \
      --cacert tls/generated/ca.crt \
      -s \
      -D - \
      https://app.cn-project.test:8443/api/status \
      -o /dev/null \
      | grep -i '^X-Backend:' \
      | tr -d '\r'
done

echo
echo "========================================="
echo "6. TLS HANDSHAKE / ISSUER CHECK"
echo "========================================="

openssl s_client \
  -connect app.cn-project.test:8443 \
  -servername app.cn-project.test \
  -CAfile tls/generated/ca.crt \
  </dev/null 2>/dev/null \
  | grep -E 'subject=|issuer=|Verify return code'

echo
echo "========================================="
echo "DONE"
echo "========================================="
