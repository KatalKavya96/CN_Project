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
