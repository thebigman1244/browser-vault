# Install Browser Vault on a Raspberry Pi 5

This guide separates commands for the **Pi host**, the **Ubuntu guest**, and your **build computer**. Follow the stages in order. These scripts create services, firewall rules and a VM; review them first. Use a dedicated, updated 64-bit Pi installation and retain a working administrative connection throughout setup.

The public scripts were adapted from the reference deployment. The complete generalized flow has not yet been repeated on a clean Pi. Stop on any failed command or check; do not bypass a failure by setting `isolationVerified` manually.

## 1. Prepare the host

On the Pi, verify all three architecture readings:

```sh
cat /etc/os-release
uname -m
dpkg --print-architecture
```

The kernel must report `aarch64` and userspace `arm64`. These instructions do not rewrite an SD card or migrate a 32-bit OS. If needed, install a fresh 64-bit Raspberry Pi OS using Raspberry Pi Imager first.

```sh
sudo apt-get update
sudo apt-get install -y git curl ca-certificates qemu-system-arm qemu-utils \
  qemu-efi-aarch64 cloud-image-utils nftables openssh-client python3 gpgv
test -c /dev/kvm
test -f /usr/share/AAVMF/AAVMF_CODE.fd
test -f /usr/share/AAVMF/AAVMF_VARS.fd
sudo -i
git clone https://github.com/thebigman1244/browser-vault.git /root/browser-vault
cd /root/browser-vault
```

Run subsequent host commands from this root shell. Make sure the Pi has cooling, a reliable power supply and enough free disk space. The 90 GiB virtual disk is sparse: it grows as data is written. Do not let the host filesystem fill up.

## 2. Build the launcher and broker

On a build computer with Node.js 24, Git and `tar`:

```sh
git clone https://github.com/thebigman1244/browser-vault.git
cd browser-vault
npm ci
npm --prefix selfhost ci --ignore-scripts
npm test
npm run build
node scripts/package.mjs
```

Copy `dist/broker.tar.gz` and `dist/frontend.tar.gz` to `/root/browser-vault-artifacts/` on the Pi using your existing administrative transfer method. The same build can run on the Pi before allocating RAM to the VM. Do not copy `node_modules` between operating systems or architectures.

## 3. Create the virtual machine

Install the distribution's `ubuntu-keyring` package containing `/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg` before downloading the image. On Bookworm this may require enabling the official Debian Bookworm backports repository; review the [Debian package](https://packages.debian.org/bookworm-backports/ubuntu-keyring) for your OS. Do not skip signature verification if the keyring is missing. A keyring from another source must be authenticated independently.

On the Pi:

```sh
cd /root/browser-vault
bash pi-admin/download-vm.sh
bash pi-admin/provision-vm.sh
bash pi-admin/host-cloudflared.sh
bash pi-admin/host-services.sh
vault-guest 'sudo cloud-init status --wait'
```

The image download verifies Ubuntu's signed checksum list. Provisioning refuses to overwrite an existing `vault.qcow2`. `vault-guest` uses a host-only SSH key generated during provisioning; it connects through a loopback forward, not a public SSH port.

Initial boot and package installation can take several minutes. If the first SSH attempt is too early, wait and retry it. Inspect `/var/log/browser-vault-vm/serial.log` and `journalctl -u browser-vault-vm` if the guest does not boot. Guest architecture must also be `aarch64` / `arm64`.

## 4. Prepare Cloudflare settings and private files

In Cloudflare Zero Trust, create a self-hosted Access application covering **both** your launcher hostname and display hostname, for example `vault.your-domain.tld` and `view.your-domain.tld`. Use an Allow policy limited to your exact identity/email and your chosen identity provider. Do not add a Bypass or Everyone policy. Configure a suitable session duration and MFA with your identity provider.

Copy the application's audience tag (AUD) and the team's issuer URL. One application containing both hostnames lets the broker use one audience value. See [Cloudflare's self-hosted application guide](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/).

On the Pi:

```sh
install -d -m700 /root/browser-vault-install /root/browser-vault-artifacts
cp /root/browser-vault/config/settings.example.json /root/browser-vault-install/settings.json
nano /root/browser-vault-install/settings.json
chmod 600 /root/browser-vault-install/settings.json
python3 /root/browser-vault/pi-admin/release_config.py
```

Replace every example value. The three private probe addresses are, in order, your Pi, a second LAN test device, and your router. Choose addresses you control with known listening services; a timeout to a nonexistent machine alone is not proof of isolation. Test ports are specified in `test-workspaces.py` and `vpn-test.py`; adjust them to those services.

Obtain a WireGuard configuration from your VPN provider and save it as `/root/vault-proton.conf` on the Pi, mode `600`. Despite the filename, the parser accepts a compatible configuration from another provider. Requirements: one Interface, one Peer, a literal public IPv4 UDP endpoint, an IPv4 interface address, and `0.0.0.0/0` in AllowedIPs. Hooks and unknown directives are rejected. The supplied policy uses public DNS resolvers over the tunnel, rather than importing provider-specific DNS settings. [Proton's manual WireGuard guide](https://protonvpn.com/support/wireguard-configurations) describes how to obtain a configuration.

Download the **Kasm Workspaces 1.19.0 installer** from the [official download page](https://kasm.com/downloads), review its EULA and obtain its published SHA-256 checksum. Save the archive as `/root/browser-vault-artifacts/kasm-release.tar.gz`. Browser Vault does not redistribute Kasm or grant rights to it. Do not silently substitute a newer release: the seed format and database permission IDs are version-specific.

## 5. Transfer installation files into the guest

On the Pi, as root:

```sh
vault-guest 'mkdir -p /home/vault/stage; chmod 700 /home/vault/stage'
scp -i /root/.ssh/browser-vault-guest -P 2222 \
  -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/root/.ssh/browser-vault-known-hosts \
  /root/browser-vault/pi-admin/* /root/browser-vault/selfhost/early-isolation.sh \
  /root/browser-vault/selfhost/isolate-network.sh \
  /root/browser-vault-install/settings.json /root/vault-proton.conf \
  /root/browser-vault-artifacts/*.tar.gz vault@127.0.0.1:/home/vault/stage/
vault-guest 'sudo install -d -m700 /root/browser-vault-install; sudo cp /home/vault/stage/* /root/browser-vault-install/; sudo chmod -R go-rwx /root/browser-vault-install; sudo mv /root/browser-vault-install/vault-proton.conf /root/vault-proton.conf'
python3 /root/browser-vault/pi-admin/allow-vpn-endpoint.py /root/vault-proton.conf
vault-guest
```

The last command opens the guest shell. Become root and enter the install directory:

```sh
sudo -i
cd /root/browser-vault-install
python3 release_config.py
export KASM_SHA256='PASTE_THE_OFFICIAL_1_19_0_SHA256_HERE'
export ACCEPT_KASM_EULA=yes
bash install-kasm-pi.sh
```

The installer logs to `/root/browser-vault-install/kasm-install.log`, which contains administrative credentials. Keep it private. This step can take a while. Browser downloads are deliberately deferred until network restrictions are installed.

## 6. Install Node and the broker in the guest

Install an ARM64 Node.js 24 LTS release from [nodejs.org](https://nodejs.org/en/download), verifying its signed `SHASUMS256.txt` using the official [release verification instructions](https://github.com/nodejs/node#verifying-binaries). Extract the verified `node-v24.*-linux-arm64.tar.xz` under `/opt`. Replace `VERSION` below with the exact version downloaded; do not paste a checksum from an unofficial source.

```sh
ln -s /opt/node-vVERSION-linux-arm64/bin/node /usr/local/bin/node
ln -s /opt/node-vVERSION-linux-arm64/bin/npm /usr/local/bin/npm
node --version
npm --version
cd /root/browser-vault-install
bash install-broker.sh
install -m755 isolate-network.sh /usr/local/sbin/browser-vault-isolate
bash finish-guest-services.sh
python3 bootstrap-pi-api.py
python3 configure-pi-api.py
```

The launcher starts but refuses new sessions until verification is complete. Credentials remain in root-only installation files and in the broker account's private configuration. The display certificate includes your configured hostname and loopback address.

## 7. Apply the VPN and browser network policy

Still in the guest:

```sh
apt-get update
apt-get install -y nftables wireguard-tools tcpdump python3-yaml linux-modules-extra-virtual
modprobe nf_conntrack_bridge
install -m755 vpn-firewall.sh /usr/local/sbin/browser-vault-vpn-policy
python3 vpn-install.py
python3 pin-proxy-network.py
bash pull-browsers.sh
python3 pin-services.py
bash install-monitor.sh
python3 test-workspaces.py
python3 enable-launcher.py
```

Browser images are large. `pull-browsers.sh` checks ARM64 availability; stop if any pull or architecture check fails. Service images are pinned to installed digests. Browser images use the 1.19.0 rolling tags, so record and review their digests before future updates.

The workspace test creates and removes three test sessions and checks CPU/RAM limits, non-root execution, capabilities, seccomp, network attachment and browser startup. It also makes public HTTPS and private-network probes. Only after this passes does `enable-launcher.py` enable normal launches. `install-monitor.sh` must have passed too; a missing or stale monitor report still prevents launch.

Exit the guest back to the Pi before proceeding.

## 8. Publish through Cloudflare Tunnel

Create a remotely managed tunnel in Cloudflare. Store only its token in `/etc/cloudflared/token` on the Pi using a private editor, not a command pasted into shared logs. Set ownership `root:vault-tunnel` and mode `640`.

Copy the guest's **public certificate**, never its private key:

```sh
vault-guest 'sudo cat /etc/browser-vault/kasm.crt' > /etc/cloudflared/kasm.crt
chown root:vault-tunnel /etc/cloudflared/token /etc/cloudflared/kasm.crt
chmod 640 /etc/cloudflared/token /etc/cloudflared/kasm.crt
```

Configure these published application routes in the tunnel dashboard:

| Public hostname | Origin service | Required origin settings |
| --- | --- | --- |
| Your launcher hostname | `http://127.0.0.1:18080` | Access token validation enabled; your team and application AUD |
| Your display hostname | `https://127.0.0.1:18443` | Origin Server Name = your display hostname; CA Pool = `/etc/cloudflared/kasm.crt`; Access token validation enabled |

Leave **No TLS Verify disabled**. Both hostnames must be covered by the Access application before starting the tunnel. Refer to [Cloudflare origin parameters](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/origin-configuration/) for certificate and Access validation fields. Do not publish ports 2222, 18080, 18443 or the Kasm admin interface directly, and do not enable router port forwarding.

```sh
systemctl enable --now browser-vault-tunnel
systemctl is-active browser-vault-tunnel browser-vault-vm browser-vault-vm-firewall
```

## 9. Acceptance checks

1. In a signed-out browser, open each hostname. Both must require Access sign-in. A different identity must be denied.
2. Sign in, verify all protection checks are current, and launch Chromium. Confirm keyboard, pointer and scrolling work in the live display.
3. While that disposable test session is active, run `python3 /root/browser-vault-install/vpn-test.py` as root **inside the guest**. This compares public addresses, checks DNS traffic, tests private destinations, stops the VPN briefly to test the kill switch, and restores it in a `finally` block. It contacts `api.ipify.org` to compare public IPs. Do not run it during somebody else's session.
4. End the session and confirm its container is removed. Repeat a normal interactive launch with Firefox and Brave.
5. End all sessions, reboot the Pi, then confirm the VM, VPN, tunnel and protection timer recover. Repeat the signed-out Access checks and VPN test after reboot.
6. Record the image digests, OS versions and test output privately. Remove staging copies of credentials from `/home/vault/stage` after checking that every target is in that directory; keep the root-only recovery configuration in a protected backup.

Do not use suspicious content until these checks pass. A green launcher indicates a recent operational check, not an independent security audit.

## Add the desktop and download monitor

After completing and verifying the base installation, follow [Desktop and security pages](OPERATIONS.md#desktop-and-security-pages-12) to install the Ubuntu desktop image and local antivirus monitor. These components need additional disk space and scan memory. The launcher reports unavailable desktop profiles and unavailable scanning until those steps are complete.
