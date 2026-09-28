#!/bin/bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# Compare the installed policy to this checkout before accepting a baseline.
cmp "$script_dir/vpn-firewall.sh" /usr/local/sbin/browser-vault-vpn-policy
systemctl is-active --quiet browser-vault-vpn-policy wg-quick@vault-wg
install -m755 "$script_dir/protection-monitor.py" /usr/local/sbin/browser-vault-protection-monitor
install -d -m700 /etc/browser-vault-protection
/usr/local/sbin/browser-vault-protection-monitor --record-reviewed-baseline
cat >/etc/systemd/system/browser-vault-protection-monitor.service <<'EOF'
[Unit]
Description=Read-only Browser Vault protection checks
After=browser-vault-vpn-policy.service wg-quick@vault-wg.service docker.service
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/browser-vault-protection-monitor
RuntimeDirectory=browser-vault-health
RuntimeDirectoryMode=0755
RuntimeDirectoryPreserve=yes
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
CapabilityBoundingSet=CAP_NET_ADMIN
RestrictAddressFamilies=AF_UNIX AF_NETLINK AF_INET AF_INET6
TimeoutStartSec=35
EOF
cat >/etc/systemd/system/browser-vault-protection-monitor.timer <<'EOF'
[Unit]
Description=Refresh Browser Vault protection checks
[Timer]
OnBootSec=20
OnUnitInactiveSec=15
AccuracySec=1
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl start browser-vault-protection-monitor
systemctl enable --now browser-vault-protection-monitor.timer
python3 - <<'PY'
import json
with open('/run/browser-vault-health/status.json') as f:
    status=json.load(f)
assert all(status['checks'].values()), 'Protection checks failed; do not enable the launcher.'
print('Protection monitor ready')
PY
