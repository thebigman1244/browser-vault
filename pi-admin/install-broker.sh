#!/bin/bash
set -euo pipefail
umask 077
test "$(id -u)" = 0
cd /root/browser-vault-install
test -x /usr/local/bin/node
test -f broker.tar.gz
test -f frontend.tar.gz
id browser-vault >/dev/null 2>&1 || useradd --system --home /var/lib/browser-vault --shell /usr/sbin/nologin browser-vault
install -d -m0755 /opt/browser-vault/public
install -d -m0750 -o browser-vault -g browser-vault /etc/browser-vault /var/lib/browser-vault
tar -xzf broker.tar.gz -C /opt/browser-vault
tar -xzf frontend.tar.gz -C /opt/browser-vault/public
cd /opt/browser-vault
/usr/local/bin/npm ci --omit=dev --ignore-scripts --no-audit --no-fund
chmod -R a+rX,go-w /opt/browser-vault
/usr/local/bin/node --test auth.test.mjs api-response.test.mjs protection.test.mjs
