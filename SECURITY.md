# Security model

Browser Vault is designed to separate untrusted browsing from your everyday computer and private network. It combines a dedicated VM, restricted disposable browser containers, host and guest firewalls, authenticated remote access and browser-only VPN routing.

## Boundaries and assumptions

- The Pi host, its administrator and the configuration are trusted.
- The guest runs the browser infrastructure. A browser-container escape reaches the guest environment before it reaches the Pi host; the VM adds a separate boundary.
- Browsers cannot initiate connections to private address ranges, the guest host, the display proxy or other containers under the supplied policies.
- Browser egress is restricted to the VPN. Pi and VM management traffic are outside that VPN.
- Both public hostnames require Cloudflare Access. The broker validates signed identity claims, and the tunnel must enforce Access on the display route too.

These controls do not guarantee containment of every browser, kernel, hypervisor, remote-display or supply-chain exploit. The VM persists between sessions. Deleting a browser container does not repair a compromised guest or securely erase storage blocks. The VPN changes the browser's network path; it is not a malware filter or an anonymity guarantee. Do not place valuable credentials or data in a browsing session used for suspicious links.

A signed-in user receives pixels and sends input through the remote-display software, which is itself part of the attack surface. A trusted host administrator can access the guest and its data. Cloudflare and the VPN provider are external trust dependencies. The system is single-user and is not hardened as a hostile multi-tenant service.

## Deployment requirements

Keep host forwards on loopback. Do not publish Docker, SSH, Kasm administration or the broker directly to the Internet. Do not disable TLS verification, JWT validation, the VPN policy or protection checks to make a failing installation launch.

Use a narrowly scoped Access policy and protect the identity-provider account. Treat tunnel tokens, WireGuard keys, Kasm credentials, broker configuration and session URLs as secrets. Keep them outside the repository, with restricted filesystem permissions. If a credential is committed, removing the file is insufficient: revoke or rotate it and address the Git history.

An additional router/VLAN boundary can reduce dependence on the Pi host firewall. It is not configured by this project. Devices on unusual public-addressed local networks need an explicit policy review; the default private-range rules are not a complete inventory of your network.

## Verification

Run the workspace and VPN checks before use and after relevant changes. Private-address probes need known listening targets and firewall-counter evidence; a failed connection by itself can mean the target was offline. Test signed-out access to both domains and repeat the VPN kill-switch check after a full reboot.

CI does not boot a Raspberry Pi or exercise a real VPN. Its passing status does not certify deployment isolation. This project has not had an independent security audit.

## Reporting a vulnerability

Use the repository's **Security → Report a vulnerability** option for a private report. Include the affected revision, deployment layout and a minimal reproduction without credentials or live session links. Do not publish an exploit against another person's installation. There is no guaranteed response time or formal long-term support policy.
