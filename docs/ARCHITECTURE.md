# Architecture

Browser Vault has three layers: the Raspberry Pi host, one persistent Ubuntu VM, and a temporary browser container for each session.

## Pi host

QEMU runs under `vault-vm`, an unprivileged account with access to KVM. The service uses a read-only system filesystem, limited address families, no new privileges and QEMU's process sandbox. A QMP helper requests an orderly shutdown when the service stops.

The VM uses QEMU user networking, not a bridge onto the home LAN. A host nftables rule set applies to the QEMU user's outbound sockets. It rejects local and private destinations and IPv6, and allows a small set of public services plus the configured VPN endpoint. Established replies are permitted so management connections can work. This is important: the guest must not be able to remove the host's private-network rules.

| Loopback port on Pi | Destination in VM | Purpose |
| --- | --- | --- |
| 2222 | 22 | Guest administration with a host-held SSH key |
| 18080 | 8080 | Browser Vault broker and launcher |
| 18443 | 443 | Kasm browser display |

Cloudflare Tunnel runs as a different account, `vault-tunnel`. Its configuration and token stay on the Pi. It connects outbound to Cloudflare and reaches the guest through the loopback ports. Your client computer is not part of this path.

## Guest and session broker

The Ubuntu guest runs Docker and Kasm Workspaces. Browser Vault's Node service runs as `browser-vault`, without Docker access. It serves the React interface and talks to Kasm's API over certificate-validated local HTTPS. The API identity receives only the permissions used for session operations.

In Cloudflare mode the broker checks the Access JWT's signature, issuer, audience, expiry and exact email. It also checks allowed request origins. The display route requires Access enforcement at Cloudflare and in the tunnel connector: the launcher alone cannot protect that separate route.

The broker only accepts configured browsers, profiles, durations and display settings. It tracks one active session, persists enough state to recover after a restart, and refreshes display URLs instead of persisting access-bearing URLs. Closing a browser tab does not end its session; the server's timeout still applies.

## Browser containers

All browser sessions attach only to `vault_browsers` (`172.30.80.0/24`, bridge `br-vault`). The display proxy has a fixed `.254` address. Containers use an unprivileged user, dropped capabilities, no-new-privileges, Docker's default seccomp filtering, a 512-process limit, CPU quotas and a hard RAM limit without extra container swap. The supplied tests require no host mounts.

The display proxy may connect to the browser for streaming. New browser-initiated connections to the proxy, guest services, other containers and private networks are rejected. Clipboard, file/device forwarding and persistent profiles are disabled in Kasm settings.

## Browser-only VPN

`vault-wg` carries browser egress. Packets from the browser bridge receive routing mark `0xb00` and use table `51820`. This table retains an unreachable default even when the WireGuard interface disappears. nftables also requires permitted browser traffic to leave through WireGuard, with destination and protocol restrictions. Browser IPv6 is blocked.

Only web traffic and designated public DNS are permitted. This restricts some browser features and sites: arbitrary ports, peer-to-peer traffic and direct LAN access are intentionally unavailable. Management traffic uses the normal guest route, so losing the browser VPN should not break remote administration.

## Health and startup

Early private-address rules run before Docker. VPN policy is required before Docker and WireGuard start. A root-owned monitor checks normalized firewall rules, routing, recent WireGuard handshakes and the display proxy every 15 seconds. It writes a small read-only report for the broker. Reports older than 45 seconds prevent new sessions.

The monitor compares firewall state against a reviewed baseline, not an independent model of every possible compromise. New-session refusal does not automatically destroy an existing session. The packet filters and unreachable route provide the VPN fail-closed behavior for active sessions.
