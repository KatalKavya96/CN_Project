#!/bin/bash
set -e

echo "=== Backend A ==="
curl -i http://127.0.0.1:3001/api/status

echo
echo "=== Backend B ==="
curl -i http://10.7.25.0:3002/api/status
