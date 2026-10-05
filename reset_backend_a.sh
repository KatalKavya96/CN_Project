#!/bin/bash

echo "=== 1. Stop any old Backend A processes ==="

pkill -f "backend-a/app.py" 2>/dev/null || true
sleep 1

echo
echo "=== 2. Find anything listening on port 3001 ==="

PIDS=$(lsof -tiTCP:3001 -sTCP:LISTEN 2>/dev/null)

if [ -n "$PIDS" ]; then
    echo "Killing listener(s): $PIDS"
    kill $PIDS 2>/dev/null || true
    sleep 1
fi

PIDS=$(lsof -tiTCP:3001 -sTCP:LISTEN 2>/dev/null)

if [ -n "$PIDS" ]; then
    echo "Force killing remaining listener(s): $PIDS"
    kill -9 $PIDS 2>/dev/null || true
    sleep 1
fi

echo
echo "=== 3. Verify port 3001 is free ==="

lsof -nP -iTCP:3001 -sTCP:LISTEN || true

echo
echo "=== 4. Start Backend A ==="

nohup python3 backend-a/app.py \
    > /tmp/cn-backend-a.log 2>&1 &

BACKEND_PID=$!

echo "Started Backend A PID: $BACKEND_PID"

sleep 2

echo
echo "=== 5. Verify Backend A is listening ==="

lsof -nP -iTCP:3001 -sTCP:LISTEN || true

echo
echo "=== 6. Test Backend A directly ==="

curl -i http://127.0.0.1:3001/api/status

echo
echo
echo "=== 7. Reload nginx ==="

nginx -s reload -c "$(pwd)/edge/nginx.conf"

sleep 1

echo
echo "=== 8. Verify round-robin restored ==="

for i in {1..6}; do
    printf "Request %02d: " "$i"

    /usr/bin/curl -s -D - \
      https://app.cn-project.test:8443/api/status \
      -o /dev/null \
      | grep -i '^X-Backend:' \
      | tr -d '\r'
done

echo
echo "=== Backend A reset complete ==="
