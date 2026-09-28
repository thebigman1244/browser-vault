#!/bin/bash
set -euo pipefail
cd /root/browser-vault-install
display_host=$(python3 -c 'from release_config import load; print(load()["displayHost"])')
test -f kasm-installed
test -s broker.json
# Replace the installer's CN-only certificate with a SAN certificate that the
# Pi's connector can validate. Keep its private key inside the guest.
if ! openssl x509 -in /opt/kasm/current/certs/kasm_nginx.crt -noout -ext subjectAltName 2>/dev/null | grep -Fq "DNS:$display_host"; then
 openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 825 -subj "/CN=$display_host" -addext "subjectAltName=DNS:$display_host,DNS:browser-vault,IP:127.0.0.1" -keyout /opt/kasm/current/certs/kasm_nginx.key -out /opt/kasm/current/certs/kasm_nginx.crt >/dev/null 2>&1
 chmod 600 /opt/kasm/current/certs/kasm_nginx.key
 chmod 644 /opt/kasm/current/certs/kasm_nginx.crt
 docker restart kasm_proxy >/dev/null
fi
install -m644 /opt/kasm/current/certs/kasm_nginx.crt /etc/browser-vault/kasm.crt
install -m600 -o browser-vault -g browser-vault broker.json /etc/browser-vault/config.json
cat >/etc/systemd/system/browser-vault-isolation.service <<'EOF'
[Unit]
Description=Browser Vault private network restrictions
After=docker.service
Requires=docker.service
PartOf=docker.service
Before=browser-vault.service
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/browser-vault-isolate
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target docker.service
EOF
cat >/etc/systemd/system/browser-vault.service <<'EOF'
[Unit]
Description=Browser Vault authenticated launcher
After=network-online.target browser-vault-isolation.service kasm.service
Requires=browser-vault-isolation.service
Wants=kasm.service
[Service]
User=browser-vault
Group=browser-vault
ExecStart=/usr/local/bin/node /opt/browser-vault/server.mjs
Restart=on-failure
RestartSec=5
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
ReadWritePaths=/var/lib/browser-vault
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
CapabilityBoundingSet=
UMask=0077
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now browser-vault-isolation browser-vault
echo GUEST_SERVICES_READY
