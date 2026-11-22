#!/bin/bash
set -euo pipefail
if [ -x /usr/local/sbin/cn-project-admin ]; then
  exec sudo -n /usr/local/sbin/cn-project-admin dns-start
fi
echo 'First run bash phase2/install-admin.sh mac1 (or mac2) on the matching Mac.' >&2
exit 2
