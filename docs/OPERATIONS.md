# Operations and troubleshooting

## Service checks

On the Pi:

```sh
sudo systemctl status browser-vault-vm browser-vault-vm-firewall browser-vault-tunnel
sudo journalctl -u browser-vault-vm -u browser-vault-tunnel --since '15 minutes ago'
sudo nft list table inet vault_vm
sudo ss -lntp
```

The guest management and web forwards must bind only to `127.0.0.1`. Check disk space on the Pi and inside the VM regularly. The sparse disk can grow near its 90 GiB capacity, and image updates need temporary free space.

Inside the guest:

```sh
sudo systemctl status browser-vault wg-quick@vault-wg browser-vault-protection-monitor.timer
sudo cat /run/browser-vault-health/status.json
sudo ip route show table 51820
sudo nft list table inet vault_vpn
sudo nft list table bridge vault_l2
sudo wg show vault-wg latest-handshakes
```

Do not share `wg showconf`, private configuration files, tunnel tokens, complete session responses or installer logs. Redact account identifiers from diagnostic output before posting an issue.

## Common problems

| Symptom | Check |
| --- | --- |
| JSON error mentioning `<` or an HTML login page | Access may have returned a sign-in page to an API request. Sign in to the launcher hostname again; verify the Access application covers both hostnames. |
| Launcher connects but sessions stay disabled | Inspect the protection report. Check the VPN handshake, routing table, firewall baseline and proxy address. Do not bypass the checks. |
| Display asks for a second sign-in | The display hostname has its own request path through Access. Confirm both hostnames belong to the intended application and identity policy. |
| Browser display will not open | Allow the launcher to open a new tab, then use Open interactive browser or Refresh display link. Check the display tunnel route and origin certificate. |
| Tunnel reports certificate errors | Compare the certificate SAN with the configured display hostname and Origin Server Name. Copy the current public guest certificate to the Pi's CA Pool path. Leave TLS verification enabled. |
| VPN stopped working | Check provider status/expiry and the endpoint in the WireGuard file. If it changed, update the host endpoint rule before reconnecting the guest. |
| Health checks fail after a policy edit | Review the actual rules against the intended policy. Re-record the baseline only after a deliberate review and successful tests. |
| Some sites or downloads fail | Network protocols and ports are restricted; clipboard and file transfers are disabled. These are expected defaults. |
| Kasm reports no resources | Wait for the previous container to be removed; check guest memory, disk space and image pulls. Only one browser session is supported. |

## Updates

End the active session first. Save the deployed revision and private configuration. With the VM shut down cleanly, take a host-side backup or snapshot that preserves the base image, overlay and EFI state together. Keep backups encrypted and outside this repository.

Review upstream host OS, Ubuntu, Kasm, Docker, cloudflared, Node and browser-image updates. They are separate components; updating the launcher does not update all of them. Rebuild frontend and broker bundles from the selected Git revision using `npm ci`, run the tests, and transfer only the new bundles. Stop the broker, preserve the previous `/opt/browser-vault` tree, install the new bundles with `install-broker.sh`, and restart the broker. Do not re-run the initial Kasm seed script during an update.

The Kasm setup scripts target 1.19.0. Follow upstream upgrade documentation for Kasm itself and review API permissions, container restrictions and networking afterward. `pin-services.py` pins service images to the currently installed digest; deliberate upgrades need corresponding image/compose changes. Browser rolling tags are mutable. Record the exact digests you test and repeat workspace, VPN, Access and reboot checks after updating them.

The generated display certificate expires after 825 days. Schedule renewal before expiry. Renew in a maintenance window, deploy the public certificate to the Pi, and verify the broker and tunnel both trust it. The private key stays in the guest.

## Recovery and removal

If the guest is suspect, stop `browser-vault-vm` and `browser-vault-tunnel` on the Pi and investigate from the trusted host. Rebuild the guest from a clean image rather than treating session deletion as recovery from a guest compromise. Rotate credentials if they may have been exposed.

To retire the deployment, end sessions, disable and stop the tunnel and VM services, revoke the Cloudflare tunnel credential and WireGuard credential, and remove the two DNS routes/Access application if they are no longer used. Only then remove reviewed service files and VM data. The firewall tables are project-specific (`vault_vm` on the Pi, `vault_vpn`/`vault_l2` in the guest); do not flush the machine's entire firewall. There is intentionally no unattended destructive uninstall script.
