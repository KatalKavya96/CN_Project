#!/bin/bash
set -e

echo "=== Backend A ==="
curl -i http://10.7.3.153:3001/api/status

echo
echo "=== Backend B ==="
curl -i http://10.7.29.7:3002/api/status
