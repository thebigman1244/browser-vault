# Changelog

## 1.2.0

- Added an isolated Ubuntu desktop page with existing CPU/RAM, VPN, and lifetime controls.
- Added live protection and download-monitoring dashboards, local ClamAV scanning, and explicit pending/error/limit states.
- Added session-extension controls capped at 30 minutes, reconnect controls, and a confirmation before ending a session.
- Retained disabled file/clipboard forwarding, private-network restrictions, and per-session disposal.


## 1.1.0 — Public source release

- Publish the VM-backed Raspberry Pi deployment, launcher and session broker.
- Include Chromium, Firefox and Brave resource profiles, timed disposal, live protection checks and Smooth display mode.
- Replace installation-specific domains and identities with validated configuration.
- Add staged setup, architecture, security and operations documentation.
- Include host/guest isolation policies, browser-only WireGuard routing and hardware verification scripts.
- Add build, authentication, policy and configuration checks in CI.

The generalized installer flow has not yet been validated on a second clean device.
