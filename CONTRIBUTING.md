# Contributing

Keep changes focused and describe the behavior they change. Include a reproduction for bug fixes and the commands used for validation. Screenshots help with interface changes; remove real domains, account identities and session URLs first.

Run the README development checks before opening a pull request. Changes to authentication, session creation, firewall policy or routing need tests for failure paths as well as success. Hardware or provider-specific changes should name the device, OS, Kasm version and whether the VPN and reboot checks passed.

Do not weaken a security control to hide an installation failure. Keep secrets out of examples and fixtures. Preserve third-party license notices. Documentation should use direct language, explicit host/guest command locations and claims supported by the implementation.

For security issues, follow [SECURITY.md](SECURITY.md) instead of opening a public issue.
