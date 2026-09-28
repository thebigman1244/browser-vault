#!/bin/bash
set -euo pipefail
install -d -m 0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg -o /usr/share/keyrings/cloudflare-main.gpg
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main' >/etc/apt/sources.list.d/cloudflared.list
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y cloudflared
cloudflared --version
id vault-tunnel >/dev/null 2>&1 || useradd --system --home /var/lib/cloudflared --shell /usr/sbin/nologin vault-tunnel
install -d -m 0750 -o root -g vault-tunnel /etc/cloudflared
echo CLOUDFLARED_INSTALLED_NOT_STARTED
