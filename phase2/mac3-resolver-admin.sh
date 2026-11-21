#!/bin/bash
# Root-owned switch between the original and candidate project backup DNS.
set -euo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
unset BASH_ENV ENV CDPATH
STATE=/private/var/db/cn-project-dns-migration
source "$STATE/settings"
[ "$EUID" -eq 0 ] && [ "$#" -eq 1 ] || exit 2
case "$1" in
  status) cat /etc/resolver/cn-project.test ;;
  use-mac2|use-mac3)
    backup=$MAC2_IP
    [ "$1" != use-mac3 ] || backup=$MAC3_IP
    temp=$(mktemp /etc/resolver/.cn-project.XXXXXX)
    trap 'rm -f "$temp"' EXIT
    printf 'nameserver %s\nnameserver %s\n' "$MAC1_IP" "$backup" > "$temp"
    chmod 644 "$temp"
    chown root:wheel "$temp"
    mv -f "$temp" /etc/resolver/cn-project.test
    /usr/bin/dscacheutil -flushcache
    /usr/bin/killall -HUP mDNSResponder
    cat /etc/resolver/cn-project.test ;;
  *) echo 'Allowed: status use-mac2 use-mac3' >&2; exit 2 ;;
esac
