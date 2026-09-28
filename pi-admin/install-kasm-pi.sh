#!/bin/bash
set -euo pipefail
umask 077
cloud-init status --wait
cd /root/browser-vault-install
test ! -e kasm-installed || { echo 'Kasm is already installed; refusing to re-seed credentials.' >&2; exit 1; }
: "${KASM_SHA256:?Set KASM_SHA256 to the checksum published by Kasm for the 1.19.0 installer}"
[[ "$KASM_SHA256" =~ ^[a-fA-F0-9]{64}$ ]]
printf '%s  kasm-release.tar.gz\n' "$KASM_SHA256" | sha256sum -c -
test "${ACCEPT_KASM_EULA:-}" = yes || { echo 'Read the Kasm EULA; set ACCEPT_KASM_EULA=yes only if you accept it.' >&2; exit 1; }
tar -xzf kasm-release.tar.gz
grep -qx 'KASM_VERSION="1.19.0"' kasm_release/install.sh
python3 prepare-kasm-pi.py
install -m 0755 early-isolation.sh /usr/local/sbin/browser-vault-early-isolation
cat >/etc/systemd/system/browser-vault-early-isolation.service <<'EOF'
[Unit]
Description=Browser restrictions before container startup
Before=docker.service
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/browser-vault-early-isolation
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
EOF
mkdir -p /etc/systemd/system/docker.service.d
cat >/etc/systemd/system/docker.service.d/browser-vault.conf <<'EOF'
[Unit]
Requires=browser-vault-early-isolation.service
After=browser-vault-early-isolation.service
EOF
systemctl daemon-reload
systemctl enable --now browser-vault-early-isolation
admin=$(python3 -c 'import json;print(json.load(open("admin.json"))["admin_password"])')
user=$(python3 -c 'import json;print(json.load(open("admin.json"))["user_password"])')
bash kasm_release/install.sh --accept-eula --default-images --no-pull-images --swap-size 2048 --admin-password "$admin" --user-password "$user" >kasm-install.log 2>&1
touch kasm-installed
echo KASM_INSTALLED
