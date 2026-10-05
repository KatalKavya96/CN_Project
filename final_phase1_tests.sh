#!/bin/bash
set -u

BASE="https://app.cn-project.test:8443/api/status"
CURL="/usr/bin/curl"

mkdir -p evidence/phase-1/{https,caching,load-balancing,failover}

echo "=========================================="
echo "1. HTTPS FINAL CHECK"
echo "=========================================="

$CURL -i "$BASE" \
  | tee evidence/phase-1/https/https-response.txt

echo
echo "=========================================="
echo "2. HTTPS LOAD BALANCING"
echo "=========================================="

for i in {1..8}; do
    printf "Request %02d: " "$i"

    $CURL -s -D - "$BASE" \
      -o /dev/null \
      | grep -i '^X-Backend:' \
      | tr -d '\r'
done | tee evidence/phase-1/load-balancing/https-round-robin.txt

echo
echo "=========================================="
echo "3. CACHE HEADERS"
echo "=========================================="

$CURL -s -D - "$BASE" \
  -o /dev/null \
  | grep -Ei 'HTTP/|X-Backend:|Cache-Control:|ETag:' \
  | tee evidence/phase-1/caching/cache-headers.txt

echo
echo "=========================================="
echo "4. CONDITIONAL CACHE TEST"
echo "=========================================="

echo "Because nginx alternates A/B, we send several"
echo "If-None-Match requests. A request that reaches"
echo "Backend A with ETag A-v1 should return 304."
echo

for i in {1..4}; do
    echo "--- Conditional request $i ---"

    $CURL -s -D - \
      -H 'If-None-Match: "A-v1"' \
      "$BASE" \
      -o /dev/null \
      | grep -Ei 'HTTP/|X-Backend:|Cache-Control:|ETag:'

    echo
done | tee evidence/phase-1/caching/conditional-304.txt

echo
echo "=========================================="
echo "5. FIND BACKEND A PROCESS"
echo "=========================================="

BACKEND_A_PID=$(lsof -ti tcp:3001 | head -1)

if [ -z "${BACKEND_A_PID:-}" ]; then
    echo "Backend A process not found on port 3001."
    exit 1
fi

echo "Backend A PID: $BACKEND_A_PID"

echo
echo "=========================================="
echo "6. STOP BACKEND A"
echo "=========================================="

kill "$BACKEND_A_PID"
sleep 2

echo "Port 3001 after stopping Backend A:"
lsof -i :3001 || true

echo
echo "=========================================="
echo "7. TEST NGINX FAILOVER"
echo "=========================================="

for i in {1..6}; do
    printf "Request %02d: " "$i"

    $CURL -s -D - "$BASE" \
      -o /dev/null \
      | grep -Ei '^HTTP/|^X-Backend:' \
      | tr '\n' ' '

    echo
done | tee evidence/phase-1/failover/backend-a-down.txt

echo
echo "All successful responses above should now"
echo "come from Backend B."

echo
echo "=========================================="
echo "8. RESTART BACKEND A"
echo "=========================================="

nohup python3 backend-a/app.py \
  > /tmp/cn-backend-a.log 2>&1 &

sleep 2

echo "Backend A process after restart:"
lsof -i :3001 || true

echo
echo "=========================================="
echo "9. VERIFY LOAD BALANCING RETURNS"
echo "=========================================="

for i in {1..6}; do
    printf "Request %02d: " "$i"

    $CURL -s -D - "$BASE" \
      -o /dev/null \
      | grep -i '^X-Backend:' \
      | tr -d '\r'
done | tee evidence/phase-1/failover/backend-a-restored.txt

echo
echo "=========================================="
echo "PHASE 1 AUTOMATED TESTS COMPLETE"
echo "=========================================="

echo
echo "Evidence saved under:"
echo "evidence/phase-1/"
