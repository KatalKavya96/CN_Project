#!/bin/bash

URL="${1:-http://10.7.3.153:8080/api/status}"

echo "Initial request:"
curl -i "$URL"

echo
echo "Conditional request:"
curl -i -H 'If-None-Match: "A-v1"' "$URL"
