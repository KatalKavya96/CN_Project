#!/bin/bash
# Run once on each Mac with its local administrator password.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
ROLE=${1:?Usage: bash phase2/install-admin.sh mac1|mac2}
case "$ROLE" in mac1|mac2) ;; *) exit 2 ;; esac
if [ "$EUID" -ne 0 ]; then
  exec sudo /bin/bash "$ROOT/phase2/install-admin.sh" "$ROLE"
fi
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
ACCOUNT=${SUDO_USER:?Run this installer through sudo from your normal account}
[[ "$ACCOUNT" =~ ^[a-zA-Z_][a-zA-Z0-9_-]*$ ]] || exit 2
source "$ROOT/phase2/lab.env"
STATE=/private/var/db/cn-project
HELPER=/usr/local/sbin/cn-project-admin
RULE=/private/etc/sudoers.d/cn-project
if [ -e "$HELPER" ] || [ -e "$RULE" ]; then
  echo 'Project admin installation exists; refusing to overwrite it.' >&2
  exit 1
fi
install -d -o root -g wheel -m 755 /usr/local/sbin /private/etc/sudoers.d
install -d -o root -g wheel -m 755 "$STATE"
install -o root -g wheel -m 600 "$ROOT/phase2/lab.env" "$STATE/lab.env"
install -o root -g wheel -m 755 "$ROOT/phase2/admin-control.sh" "$HELPER"
OWN_IP=$MAC1_IP
PORT=3002
if [ "$ROLE" = mac2 ]; then OWN_IP=$MAC2_IP; PORT=3001; fi
printf '%s app.cn-project.test api.cn-project.test\n' "$MAC2_IP" > "$STATE/records.hosts"
chmod 644 "$STATE/records.hosts"
cat > "$STATE/dnsmasq.conf" <<EOF
port=53
listen-address=127.0.0.1,$OWN_IP
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
# Normal stage allows only the primary edge's LAN address. Roll back before cutover.
cat > "$STATE/isolation.pf" <<EOF
pass in quick on $LAB_INTERFACE inet proto tcp from $MAC2_IP to $OWN_IP port $PORT keep state
block drop in quick on $LAB_INTERFACE inet proto tcp from any to $OWN_IP port $PORT
EOF
mkdir -p /etc/resolver
if [ -f /etc/resolver/cn-project.test ]; then
  cp -p /etc/resolver/cn-project.test "$STATE/resolver.original"
fi
printf 'nameserver %s\nnameserver %s\n' "$MAC1_IP" "$MAC2_IP" > /etc/resolver/cn-project.test
chmod 644 /etc/resolver/cn-project.test
/opt/homebrew/sbin/dnsmasq --test --conf-file="$STATE/dnsmasq.conf"
# Exact actions only; the helper and all privileged configs are root-owned.
temp_rule=$(mktemp /private/tmp/cn-project-sudoers.XXXXXX)
trap 'rm -f "$temp_rule"' EXIT
printf 'Cmnd_Alias CN_PROJECT = ' > "$temp_rule"
separator=''
for action in dns-start dns-stop dns-primary dns-standby dns-status cache-flush firewall-on firewall-off firewall-status; do
  printf '%s%s %s' "$separator" "$HELPER" "$action" >> "$temp_rule"
  separator=', '
done
printf '\n%s ALL=(root) NOPASSWD: CN_PROJECT\n' "$ACCOUNT" >> "$temp_rule"
/usr/sbin/visudo -cf "$temp_rule"
install -o root -g wheel -m 440 "$temp_rule" "$RULE"
/usr/sbin/visudo -c
echo 'Installed limited password-free project controls.'
"$HELPER" dns-start
"$HELPER" cache-flush
echo 'Ready: sudo -n /usr/local/sbin/cn-project-admin dns-status'
