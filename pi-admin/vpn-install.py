import configparser,ipaddress,pathlib,subprocess,re,os
os.umask(0o077)
p=pathlib.Path('/root/vault-proton.conf')
config=configparser.ConfigParser(interpolation=None,strict=True)
config.read(p)
assert set(config.sections())=={'Interface','Peer'}
for section, allowed in [('Interface',{'privatekey','address','dns','mtu'}),('Peer',{'publickey','presharedkey','allowedips','endpoint','persistentkeepalive'})]:
 assert set(config[section])<=allowed, 'Unexpected configuration directives; refusing to run hooks.'
interface,peer=config['Interface'],config['Peer']
assert re.fullmatch('[A-Za-z0-9+/]{43}=',interface['PrivateKey'])
assert re.fullmatch('[A-Za-z0-9+/]{43}=',peer['PublicKey'])
addresses=[str(ipaddress.ip_interface(x.strip())) for x in interface['Address'].split(',') if ':' not in x]
assert addresses
endpoint,port=peer['Endpoint'].rsplit(':',1)
assert ipaddress.ip_address(endpoint).version==4 and ipaddress.ip_address(endpoint).is_global
assert 1<=int(port)<=65535
assert '0.0.0.0/0' in peer['AllowedIPs']
lines=['[Interface]','PrivateKey = '+interface['PrivateKey'],'Address = '+', '.join(addresses),'MTU = 1280','Table = off','PostUp = ip route replace default dev %i table 51820 metric 10','[Peer]','PublicKey = '+peer['PublicKey'],'AllowedIPs = 0.0.0.0/0','Endpoint = '+peer['Endpoint'],'PersistentKeepalive = 25']
if peer.get('PresharedKey'): lines.append('PresharedKey = '+peer['PresharedKey'])
dest=pathlib.Path('/etc/wireguard/vault-wg.conf');dest.parent.mkdir(mode=0o700,exist_ok=True)
dest.write_text('\n'.join(lines)+'\n');dest.chmod(0o600)
pathlib.Path('/etc/systemd/system/browser-vault-vpn-policy.service').write_text('''[Unit]
Description=Browser-only VPN routing and permanent kill switch
Before=docker.service wg-quick@vault-wg.service browser-vault.service
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/browser-vault-vpn-policy
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
''')
for service in ['docker','wg-quick@vault-wg']:
 d=pathlib.Path('/etc/systemd/system/'+service+'.service.d');d.mkdir(exist_ok=True)
 (d/'vpn-policy.conf').write_text('[Unit]\nRequires=browser-vault-vpn-policy.service\nAfter=browser-vault-vpn-policy.service\n')
subprocess.run(['systemctl','daemon-reload'],check=True)
subprocess.run(['systemctl','enable','--now','browser-vault-vpn-policy.service'],check=True)
subprocess.run(['systemctl','enable','--now','wg-quick@vault-wg.service'],check=True)
# Keep the operator-provided configuration; it is outside the source checkout.
print('VPN_CONFIGURED_BROWSER_ONLY')
