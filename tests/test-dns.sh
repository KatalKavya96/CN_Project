#!/bin/bash

echo "Explicit DNS query to Mac 1:"
dig @10.7.25.0 app.cn-project.test +short
dig @10.7.25.0 api.cn-project.test +short

echo
echo "System resolver:"
dig app.cn-project.test +short
