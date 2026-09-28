"""Validate installation settings before using them in certificates or policies."""
import ipaddress
import json
import os
import pathlib
import re
from urllib.parse import urlsplit


def load(path=None):
    path = pathlib.Path(path or os.environ.get('VAULT_INSTALL_CONFIG', '/root/browser-vault-install/settings.json'))
    settings = json.loads(path.read_text())
    for key in ('launcherOrigin', 'displayOrigin'):
        value = urlsplit(settings[key])
        if (value.scheme != 'https' or value.username or value.password or value.port
                or value.path or value.query or value.fragment
                or not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?', value.hostname or '')
                or '.' not in value.hostname or '..' in value.hostname
                or value.hostname.endswith('.example.com')):
            raise ValueError(f'{key} must be your HTTPS origin, without a path or port')
    if settings['launcherOrigin'] == settings['displayOrigin']:
        raise ValueError('Use separate launcher and display hostnames')
    access = settings['cloudflareAccess']
    if not re.fullmatch(r'https://[a-z0-9-]+\.cloudflareaccess\.com', access['issuer']) or 'your-team.' in access['issuer']:
        raise ValueError('Set your Cloudflare Access issuer URL')
    if not re.fullmatch(r'[a-fA-F0-9]{64}', access['audience']):
        raise ValueError('Set the Access application audience (AUD)')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', access['email']) or access['email'].endswith('@example.com'):
        raise ValueError('Set the exact allowed sign-in email')
    targets = settings['privateProbeAddresses']
    if len(targets) != 3:
        raise ValueError('Provide Pi, LAN test device and router IPv4 addresses')
    for target in targets:
        address = ipaddress.ip_address(target)
        if address.version != 4 or not any(address in ipaddress.ip_network(cidr) for cidr in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')):
            raise ValueError('Probe targets must be private IPv4 addresses')
    settings['displayHost'] = urlsplit(settings['displayOrigin']).hostname
    return settings


if __name__ == '__main__':
    load()
    print('Installation settings valid')
