#!/bin/bash

echo "Mac 1:"
source "$(dirname "$0")/../phase2/lab.env"
ping -c 3 "$MAC1_IP"

echo
echo "Mac 2:"
ping -c 3 "$MAC2_IP"
