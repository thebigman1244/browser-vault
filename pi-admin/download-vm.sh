#!/bin/bash
set -euo pipefail
umask 077
mkdir -p /var/lib/browser-vault-vm
cd /var/lib/browser-vault-vm
test ! -e vault.qcow2 || { echo 'Existing VM disk found; refusing to replace its backing image.' >&2; exit 1; }
rm -f image-verified
curl -fL --retry 3 -o noble-server-cloudimg-arm64.img https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-arm64.img
curl -fsSL -o SHA256SUMS https://cloud-images.ubuntu.com/noble/current/SHA256SUMS
curl -fsSL -o SHA256SUMS.gpg https://cloud-images.ubuntu.com/noble/current/SHA256SUMS.gpg
gpgv --keyring /usr/share/keyrings/ubuntu-cloudimage-keyring.gpg SHA256SUMS.gpg SHA256SUMS
grep 'noble-server-cloudimg-arm64.img$' SHA256SUMS | sha256sum -c -
touch image-verified
