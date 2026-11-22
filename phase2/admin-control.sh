#!/bin/bash
# Installed root-owned; accepts only the fixed project operations below.
set -euo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
unset BASH_ENV ENV CDPATH
STATE=/private/var/db/cn-project
source "$STATE/lab.env"
if [ "$EUID" -ne 0 ] || [ "$#" -ne 1 ]; then
  echo 'Use sudo cn-project-admin ACTION' >&2
  exit 2
fi
DNSMASQ=/opt/homebrew/sbin/dnsmasq
PF=/sbin/pfctl
ANCHOR=com.apple/cn-project
dns_pid() {
  test -f "$STATE/dnsmasq.pid" || return 1
  local pid
  pid=$(cat "$STATE/dnsmasq.pid")
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  ps -p "$pid" -o comm= | grep -q 'dnsmasq$' || return 1
  printf '%s\n' "$pid"
}
case "$1" in
  dns-start)
    if dns_pid >/dev/null; then
      echo 'Project DNS already running'
    else
      "$DNSMASQ" --test --conf-file="$STATE/dnsmasq.conf"
      "$DNSMASQ" --conf-file="$STATE/dnsmasq.conf"
    fi
    ;;
  dns-stop)
    pid=$(dns_pid)
    kill -TERM "$pid"
    ;;
  dns-primary|dns-standby)
    target=$MAC2_IP
    [ "$1" != dns-standby ] || target=$MAC1_IP
    printf '%s app.cn-project.test api.cn-project.test\n' "$target" > "$STATE/records.hosts"
    if pid=$(dns_pid); then kill -HUP "$pid"; fi
    cat "$STATE/records.hosts"
    ;;
  dns-status)
    dns_pid || true
    cat "$STATE/records.hosts"
    tail -n 25 "$STATE/dnsmasq.log" 2>/dev/null || true
    ;;
  cache-flush)
    /usr/bin/dscacheutil -flushcache
    /usr/bin/killall -HUP mDNSResponder
    ;;
  firewall-on)
    # Use the existing Apple wildcard anchor; preserve the main PF ruleset.
    "$PF" -sr 2>/dev/null | grep -F 'anchor "com.apple/*"' >/dev/null || {
      echo 'Expected Apple anchor is missing; refusing to change the main ruleset.' >&2
      exit 1
    }
    "$PF" -a "$ANCHOR" -nf "$STATE/isolation.pf"
    if [ ! -f "$STATE/pf.token" ]; then
      enabled=$("$PF" -E 2>&1)
      printf '%s\n' "$enabled"
      printf '%s\n' "$enabled" | awk '/Token/ {print $NF}' > "$STATE/pf.token"
      test -s "$STATE/pf.token" || { rm -f "$STATE/pf.token"; exit 1; }
    fi
    "$PF" -a "$ANCHOR" -f "$STATE/isolation.pf"
    "$PF" -a "$ANCHOR" -vvsr
    ;;
  firewall-off)
    "$PF" -a "$ANCHOR" -F rules
    if [ -s "$STATE/pf.token" ]; then
      token=$(cat "$STATE/pf.token")
      [[ "$token" =~ ^[0-9]+$ ]] || exit 1
      "$PF" -X "$token"
      rm -f "$STATE/pf.token"
    fi
    ;;
  firewall-status)
    "$PF" -s info
    "$PF" -a "$ANCHOR" -vvsr
    ;;
  *) echo 'Allowed: dns-start dns-stop dns-primary dns-standby dns-status cache-flush firewall-on firewall-off firewall-status' >&2; exit 2 ;;
esac
