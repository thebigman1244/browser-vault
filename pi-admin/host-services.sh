#!/bin/bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
install -m755 "$script_dir/vm-shutdown.py" /usr/local/sbin/browser-vault-vm-shutdown
python3 - <<'PY'
from pathlib import Path
p=Path('/etc/systemd/system/browser-vault-vm.service')
s=p.read_text()
if '-qmp ' not in s:
 s=s.replace('-monitor none ', '-monitor none -qmp unix:/var/lib/browser-vault-vm/qmp.sock,server=on,wait=off -sandbox on,obsolete=deny,elevateprivileges=deny,spawn=deny,resourcecontrol=deny ')
 s=s.replace('Restart=on-failure','ExecStop=/usr/local/sbin/browser-vault-vm-shutdown\nRestart=on-failure')
 p.write_text(s)
PY
cat >/etc/systemd/system/browser-vault-tunnel.service <<'EOF'
[Unit]
Description=Browser Vault authenticated Cloudflare tunnel
After=network-online.target browser-vault-vm.service
Wants=network-online.target browser-vault-vm.service
[Service]
User=vault-tunnel
Group=vault-tunnel
ExecStart=/usr/bin/cloudflared --no-autoupdate tunnel --metrics 127.0.0.1:20241 run --token-file /etc/cloudflared/token
Restart=always
RestartSec=10
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
CapabilityBoundingSet=
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
UMask=0077
[Install]
WantedBy=multi-user.target
EOF
# The VM will receive these shutdown changes on its next controlled restart.
systemctl daemon-reload
systemctl enable browser-vault-tunnel
echo HOST_SERVICES_PREPARED
