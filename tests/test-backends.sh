#!/bin/bash
set -e

echo "=== Backend A ==="
curl -i http://127.0.0.1:3001/api/status

echo
echo "=== Backend B ==="
source "$(dirname "$0")/../phase2/lab.env"
curl -i "http://$MAC1_IP:3002/api/status"
