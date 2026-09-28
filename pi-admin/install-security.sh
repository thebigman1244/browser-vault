#!/bin/bash
set -euo pipefail
source_dir=${1:?Provide the reviewed update directory}
test -f "$source_dir/pi-admin/security_collector.py"
command -v clamscan >/dev/null
id vault-scan >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin vault-scan
install -d -m700 /var/lib/browser-vault-security
install -m755 "$source_dir/pi-admin/security_collector.py" /usr/local/sbin/browser-vault-security-collector
cat >/etc/systemd/system/browser-vault-security.service <<'EOF'
[Unit]
Description=Collect isolated download snapshots and request unprivileged antivirus scans
After=docker.service browser-vault.service
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/browser-vault-security-collector
RuntimeDirectory=browser-vault-security
RuntimeDirectoryMode=0755
RuntimeDirectoryPreserve=yes
UMask=0077
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
ReadWritePaths=/run/browser-vault-security /var/lib/browser-vault-security
RestrictAddressFamilies=AF_UNIX
MemoryMax=384M
CPUQuota=50%
TasksMax=32
TimeoutStartSec=150
[Install]
WantedBy=multi-user.target
EOF
cat >/etc/systemd/system/browser-vault-security.timer <<'EOF'
[Unit]
Description=Check Browser Vault downloads regularly
[Timer]
OnBootSec=30
OnUnitInactiveSec=30
AccuracySec=1
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now clamav-freshclam
systemctl enable --now browser-vault-security.timer
systemctl start browser-vault-security
echo SECURITY_MONITOR_INSTALLED
