#!/bin/bash
# Stage a DNS-only backup or a fixed-address client switch; never activates clients.
set -Eeuo pipefail
trap 'result=$?; printf "DNS staging failed at line %s (exit %s), role=%s\n" "$LINENO" "$result" "${ROLE:-unset}" >&2' ERR
ROOT=$(cd "$(dirname "$0")/.." && pwd)
ROLE=${1:?Usage: bash phase2/install-mac3-dns.sh mac1|mac2|mac3}
case "$ROLE" in mac1|mac2|mac3) ;; *) exit 2 ;; esac
if [ "$EUID" -ne 0 ]; then exec sudo /bin/bash "$ROOT/phase2/install-mac3-dns.sh" "$ROLE"; fi
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
ACCOUNT=${SUDO_USER:?Run through sudo from the local user account}
[[ "$ACCOUNT" =~ ^[a-zA-Z_][a-zA-Z0-9_-]*$ ]] || { echo "Unsupported local account: $ACCOUNT" >&2; exit 2; }
source "$ROOT/phase2/lab.env"
source "$ROOT/phase2/mac3.env"
case "$ROLE" in mac1) EXPECTED=$MAC1_IP ;; mac2) EXPECTED=$MAC2_IP ;; mac3) EXPECTED=$MAC3_IP ;; esac
ACTUAL=$(/usr/sbin/ipconfig getifaddr en0)
[ "$ACTUAL" = "$EXPECTED" ] || { echo "Wrong host/IP: expected $EXPECTED, found $ACTUAL" >&2; exit 1; }
echo "Staging DNS helper for $ROLE, account $ACCOUNT, address $ACTUAL"
if [ "$ROLE" = mac3 ]; then
  STATE=/private/var/db/cn-project-backup
  HELPER=/usr/local/sbin/cn-project-backup
  RULE=/private/etc/sudoers.d/cn-project-backup
  SOURCE=mac3-backup-admin.sh
  ACTIONS='dns-start dns-run dns-stop dns-primary dns-standby dns-status'
else
  STATE=/private/var/db/cn-project-dns-migration
  HELPER=/usr/local/sbin/cn-project-resolver
  RULE=/private/etc/sudoers.d/cn-project-resolver
  SOURCE=mac3-resolver-admin.sh
  ACTIONS='status use-mac2 use-mac3'
fi
if [ -e "$HELPER" ] || [ -e "$RULE" ]; then
  echo 'Migration helper already exists; refusing to overwrite it.' >&2; exit 1
fi
install -d -o root -g wheel -m 755 "$STATE" /usr/local/sbin /private/etc/sudoers.d
printf 'MAC1_IP=%s\nMAC2_IP=%s\nMAC3_IP=%s\n' "$MAC1_IP" "$MAC2_IP" "$MAC3_IP" > "$STATE/settings"
chmod 600 "$STATE/settings"
install -o root -g wheel -m 755 "$ROOT/phase2/$SOURCE" "$HELPER"
if [ "$ROLE" = mac3 ]; then
  printf '%s app.cn-project.test api.cn-project.test\n' "$MAC2_IP" > "$STATE/records.hosts"
  chmod 644 "$STATE/records.hosts"
  cat > "$STATE/dnsmasq.conf" <<EOF
port=53
listen-address=$MAC3_IP
bind-interfaces
no-resolv
no-hosts
local=/cn-project.test/
addn-hosts=$STATE/records.hosts
local-ttl=$DNS_TTL
cache-size=1000
pid-file=$STATE/dnsmasq.pid
log-queries
log-facility=$STATE/dnsmasq.log
EOF
  /opt/homebrew/sbin/dnsmasq --test --conf-file="$STATE/dnsmasq.conf"
else
  cp -p /etc/resolver/cn-project.test "$STATE/resolver.before"
fi
TEMP_RULE=$(mktemp /private/tmp/cn-project-mac3-sudoers.XXXXXX)
trap 'rm -f "$TEMP_RULE"' EXIT
printf '%s ALL=(root) NOPASSWD: ' "$ACCOUNT" > "$TEMP_RULE"
separator=''
for action in $ACTIONS; do
  printf '%s%s %s' "$separator" "$HELPER" "$action" >> "$TEMP_RULE"
  separator=', '
done
printf '\n' >> "$TEMP_RULE"
/usr/sbin/visudo -cf "$TEMP_RULE"
install -o root -g wheel -m 440 "$TEMP_RULE" "$RULE"
/usr/sbin/visudo -c
if [ "$ROLE" = mac3 ]; then
  "$HELPER" dns-start
  echo 'Mac 3 DNS staged. Existing clients and Mac 2 backup are unchanged.'
else
  "$HELPER" status
  echo 'Client switch staged. Active resolver addresses have NOT changed.'
fi
