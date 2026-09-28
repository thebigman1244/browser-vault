#!/bin/bash
set -euo pipefail
umask 077
base=/var/lib/browser-vault-vm
test -f "$base/image-verified"
test -c /dev/kvm
command -v qemu-system-aarch64
test ! -e "$base/vault.qcow2"
id vault-vm >/dev/null 2>&1 || useradd --system --home "$base" --shell /usr/sbin/nologin --groups kvm vault-vm
install -d -m 0700 /root/.ssh
test -f /root/.ssh/browser-vault-guest || ssh-keygen -q -t ed25519 -N '' -C browser-vault-pi-management -f /root/.ssh/browser-vault-guest
pub=$(cat /root/.ssh/browser-vault-guest.pub)
cat >"$base/user-data" <<EOF
#cloud-config
hostname: browser-vault
manage_etc_hosts: true
disable_root: true
ssh_pwauth: false
users:
  - name: vault
    shell: /bin/bash
    groups: [sudo]
    sudo: ['ALL=(ALL) NOPASSWD:ALL']
    lock_passwd: true
    ssh_authorized_keys:
      - $pub
package_update: true
packages: [curl, ca-certificates, python3-yaml, jq, iptables, nftables, wireguard-tools, tcpdump, linux-modules-extra-virtual]
write_files:
  - path: /etc/ssh/sshd_config.d/40-vault.conf
    permissions: '0644'
    content: |
      PasswordAuthentication no
      PermitRootLogin no
      AllowUsers vault
  - path: /etc/systemd/resolved.conf.d/vault.conf
    permissions: '0644'
    content: |
      [Resolve]
      DNS=1.1.1.1 9.9.9.9
      FallbackDNS=
runcmd:
  - [systemctl, restart, systemd-resolved]
  - [touch, /var/lib/vault-cloud-init-done]
EOF
cat >"$base/network-config" <<'EOF'
version: 2
ethernets:
  enp1s0:
    match:
      macaddress: '52:54:00:77:00:15'
    set-name: enp1s0
    dhcp4: false
    dhcp6: false
    accept-ra: false
    addresses: [10.77.0.15/24]
    routes:
      - to: default
        via: 10.77.0.2
    nameservers:
      addresses: [1.1.1.1, 9.9.9.9]
EOF
printf 'instance-id: browser-vault-1\nlocal-hostname: browser-vault\n' >"$base/meta-data"
cloud-localds --network-config="$base/network-config" "$base/seed.img" "$base/user-data" "$base/meta-data"
qemu-img create -f qcow2 -F qcow2 -b "$base/noble-server-cloudimg-arm64.img" "$base/vault.qcow2" 90G
cp /usr/share/AAVMF/AAVMF_VARS.fd "$base/efi-vars.fd"
chown -R vault-vm:vault-vm "$base"
chmod 700 "$base"
install -d -m 0750 -o vault-vm -g vault-vm /var/log/browser-vault-vm
vmuid=$(id -u vault-vm)
cat >/etc/browser-vault-vm.nft <<EOF
table inet vault_vm {
 chain output {
  type filter hook output priority -10; policy accept;
  meta skuid $vmuid jump guest_egress
 }
 chain guest_egress {
  ct state established,related accept
  meta nfproto ipv6 counter reject
  fib daddr type local counter reject
  ip daddr { 0.0.0.0/8,10.0.0.0/8,100.64.0.0/10,127.0.0.0/8,169.254.0.0/16,172.16.0.0/12,192.0.0.0/24,192.0.2.0/24,192.168.0.0/16,198.18.0.0/15,198.51.100.0/24,203.0.113.0/24,224.0.0.0/4,240.0.0.0/4 } counter reject
  tcp dport {80,443} counter accept
  ip daddr {1.1.1.1,9.9.9.9} udp dport 53 counter accept
  ip daddr {1.1.1.1,9.9.9.9} tcp dport 53 counter accept
  udp dport 123 counter accept
  counter reject
 }
}
EOF
cat >/usr/local/sbin/browser-vault-vm-firewall <<'EOF'
#!/bin/sh
set -eu
if nft list table inet vault_vm >/dev/null 2>&1; then
 { echo 'delete table inet vault_vm'; cat /etc/browser-vault-vm.nft; } | nft -f -
else
 nft -f /etc/browser-vault-vm.nft
fi
EOF
chmod 755 /usr/local/sbin/browser-vault-vm-firewall
cat >/etc/systemd/system/browser-vault-vm-firewall.service <<'EOF'
[Unit]
Description=Block Browser Vault VM access to the Pi and private networks
Before=browser-vault-vm.service
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/browser-vault-vm-firewall
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
EOF
cat >/etc/systemd/system/browser-vault-vm.service <<'EOF'
[Unit]
Description=Browser Vault isolated ARM64 virtual machine
After=network-online.target browser-vault-vm-firewall.service
Wants=network-online.target
Requires=browser-vault-vm-firewall.service
[Service]
User=vault-vm
Group=vault-vm
SupplementaryGroups=kvm
ExecStart=/usr/bin/qemu-system-aarch64 -name browser-vault -machine virt,accel=kvm,gic-version=2 -cpu host -smp 4 -m 6656 -drive if=pflash,format=raw,readonly=on,file=/usr/share/AAVMF/AAVMF_CODE.fd -drive if=pflash,format=raw,file=/var/lib/browser-vault-vm/efi-vars.fd -drive if=virtio,format=qcow2,file=/var/lib/browser-vault-vm/vault.qcow2,cache=none,discard=unmap -drive if=virtio,format=raw,readonly=on,file=/var/lib/browser-vault-vm/seed.img -netdev user,id=net0,net=10.77.0.0/24,dhcpstart=10.77.0.15,hostfwd=tcp:127.0.0.1:2222-:22,hostfwd=tcp:127.0.0.1:18080-:8080,hostfwd=tcp:127.0.0.1:18443-:443 -device virtio-net-pci,netdev=net0,mac=52:54:00:77:00:15 -device virtio-rng-pci -display none -monitor none -serial file:/var/log/browser-vault-vm/serial.log
Restart=on-failure
RestartSec=10
TimeoutStopSec=240
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
ReadWritePaths=/var/lib/browser-vault-vm /var/log/browser-vault-vm
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX AF_NETLINK
CapabilityBoundingSet=
UMask=0077
[Install]
WantedBy=multi-user.target
EOF
cat >/usr/local/sbin/vault-guest <<'EOF'
#!/bin/sh
exec ssh -i /root/.ssh/browser-vault-guest -p 2222 -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/root/.ssh/browser-vault-known-hosts -o ConnectTimeout=10 vault@127.0.0.1 "$@"
EOF
chmod 700 /usr/local/sbin/vault-guest
systemctl daemon-reload
systemctl enable --now browser-vault-vm-firewall browser-vault-vm
echo VM_START_REQUESTED
