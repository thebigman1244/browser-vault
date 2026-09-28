#!/bin/bash
set -euo pipefail
for browser in chromium firefox brave; do
 echo "PULLING $browser"
 docker pull --platform linux/arm64 "kasmweb/$browser:1.19.0-rolling-daily" >"/root/browser-vault-install/pull-$browser.log" 2>&1
 test "$(docker image inspect "kasmweb/$browser:1.19.0-rolling-daily" --format '{{.Architecture}}')" = arm64
 echo "READY $browser arm64"
done
touch /root/browser-vault-install/images-ready
