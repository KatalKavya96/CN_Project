#!/bin/bash
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd)
source "$ROOT/phase2/lab.env"
echo '=== macOS resolver configuration ==='
scutil --dns
echo '=== System hostname lookup ==='
dscacheutil -q host -a name app.cn-project.test
for server in "$MAC1_IP" "${BACKUP_DNS_IP:-$MAC2_IP}"; do
  echo "=== Direct DNS query: $server ==="
  dig @"$server" app.cn-project.test +time=2 +tries=1
done
for edge in "$MAC2_IP" "$MAC1_IP"; do
  echo "=== TCP: $edge:8443 ==="
  nc -vz -G 3 "$edge" 8443
  echo "=== DNS-independent verified HTTPS: $edge ==="
  /usr/bin/curl --noproxy '*' --connect-timeout 3 --max-time 10 \
    --cacert "$ROOT/.runtime/ca.crt" \
    --resolve "app.cn-project.test:8443:$edge" \
    -sS -i https://app.cn-project.test:8443/api/status
done
echo '=== HTTPS through the OS resolver ==='
/usr/bin/curl --noproxy '*' --connect-timeout 3 --max-time 10 \
  --cacert "$ROOT/.runtime/ca.crt" -sS -i https://app.cn-project.test:8443/api/status
