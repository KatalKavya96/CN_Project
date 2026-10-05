#!/bin/bash

echo "Explicit DNS query to Mac 1:"
dig @10.7.29.7 app.cn-project.test +short

echo
echo "System resolver:"
dig app.cn-project.test +short
