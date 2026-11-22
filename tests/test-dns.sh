#!/bin/bash

echo "Explicit DNS query to Mac 1:"
source "$(dirname "$0")/../phase2/lab.env"
dig @"$MAC1_IP" app.cn-project.test +short
dig @"$MAC1_IP" api.cn-project.test +short
dig @"$MAC2_IP" app.cn-project.test +short

echo
echo "System resolver:"
dscacheutil -q host -a name app.cn-project.test
