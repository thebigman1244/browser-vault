"""Pi host: allow only the provider's UDP endpoint through the VM firewall."""
import configparser
import ipaddress
import pathlib
import subprocess
import sys

config = configparser.ConfigParser(interpolation=None)
with open(sys.argv[1]) as stream:
    config.read_file(stream)
address, port = config['Peer']['Endpoint'].rsplit(':', 1)
assert ipaddress.ip_address(address).version == 4 and ipaddress.ip_address(address).is_global
assert 1 <= int(port) <= 65535
p = pathlib.Path('/etc/browser-vault-vm.nft')
s = p.read_text()
s = '\n'.join(line for line in s.splitlines() if 'comment "vault-vpn-endpoint"' not in line)+'\n'
anchor = '  tcp dport {80,443} counter accept'
assert s.count(anchor) == 1
s = s.replace(anchor, f'  ip daddr {address} udp dport {int(port)} counter accept comment "vault-vpn-endpoint"\n'+anchor)
candidate = p.with_suffix('.candidate.nft')
candidate.write_text('delete table inet vault_vm\n'+s)
try:
    subprocess.run(['nft', '-c', '-f', str(candidate)], check=True)
    p.write_text(s)
    subprocess.run(['/usr/local/sbin/browser-vault-vm-firewall'], check=True)
finally:
    candidate.unlink(missing_ok=True)
print('VPN endpoint allowed; private-network restrictions retained')
