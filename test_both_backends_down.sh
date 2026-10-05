#!/bin/bash

BASE="https://app.cn-project.test:8443/api/status"
CURL="/usr/bin/curl"

echo "=== 1. Stop Backend A on Mac 2 ==="
pkill -f "backend-a/app.py" 2>/dev/null || true
sleep 1

echo
echo "Backend A port:"
lsof -nP -iTCP:3001 -sTCP:LISTEN || true

echo
echo "=== 2. IMPORTANT ==="
echo "Now stop Backend B manually on Mac 1 with Ctrl+C."
echo
read -p "Press Enter here after Backend B is stopped..."

echo
echo "=== 3. DNS should still work ==="
dig @10.7.25.0 app.cn-project.test +short

echo
echo "=== 4. Test HTTPS edge with both backends down ==="

$CURL -i "$BASE" || true

echo
echo "Expected result:"
echo "HTTP/1.1 502 Bad Gateway"

echo
echo "=== 5. Restart Backend A ==="

nohup python3 backend-a/app.py \
  > /tmp/cn-backend-a.log 2>&1 &

sleep 2

echo
echo "Backend A status:"
curl -i http://127.0.0.1:3001/api/status

echo
echo "=== 6. Restart Backend B manually on Mac 1 ==="
echo "Run there:"
echo "python3 backend-b/app.py"

echo
echo "=== Both-backends-down test complete ==="
