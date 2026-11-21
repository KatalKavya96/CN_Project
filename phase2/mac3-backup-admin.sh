#!/bin/bash
# Root-owned DNS-only helper; no backend, nginx or firewall actions.
set -euo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
unset BASH_ENV ENV CDPATH
STATE=/private/var/db/cn-project-backup
source "$STATE/settings"
[ "$EUID" -eq 0 ] && [ "$#" -eq 1 ] || exit 2
pid_of_dns() {
  [ -f "$STATE/dnsmasq.pid" ] || return 1
  local pid
  pid=$(cat "$STATE/dnsmasq.pid")
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  ps -p "$pid" -o comm= | grep -q 'dnsmasq$' || return 1
  printf '%s\n' "$pid"
}
case "$1" in
  dns-start|dns-run)
    if pid_of_dns >/dev/null; then echo 'Mac 3 backup DNS already running';
    else /opt/homebrew/sbin/dnsmasq --test --conf-file="$STATE/dnsmasq.conf";
         if [ "$1" = dns-run ]; then
           exec /opt/homebrew/sbin/dnsmasq --keep-in-foreground --conf-file="$STATE/dnsmasq.conf"
         fi
         /opt/homebrew/sbin/dnsmasq --conf-file="$STATE/dnsmasq.conf"; fi ;;
  dns-stop)
    if pid=$(pid_of_dns); then kill -TERM "$pid"; fi ;;
  dns-primary|dns-standby)
    target=$MAC2_IP
    [ "$1" != dns-standby ] || target=$MAC1_IP
    printf '%s app.cn-project.test api.cn-project.test\n' "$target" > "$STATE/records.hosts"
    if pid=$(pid_of_dns); then kill -HUP "$pid"; fi
    cat "$STATE/records.hosts" ;;
  dns-status)
    pid_of_dns || true
    cat "$STATE/records.hosts"
    tail -n 30 "$STATE/dnsmasq.log" 2>/dev/null || true ;;
  *) echo 'Allowed: dns-start dns-run dns-stop dns-primary dns-standby dns-status' >&2; exit 2 ;;
esac
