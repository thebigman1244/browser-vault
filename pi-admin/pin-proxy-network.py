import pathlib,yaml,subprocess,os
os.umask(0o077)
p=pathlib.Path('/opt/kasm/current/docker/docker-compose.yaml')
d=yaml.safe_load(p.read_text())
backup=p.with_suffix('.before-vpn.yaml')
if not backup.exists():backup.write_text(p.read_text())
d['networks']['vault_browsers']={'external':True}
networks=d['services']['proxy']['networks']
if isinstance(networks,list):networks={name:{} for name in networks}
networks['vault_browsers']={'ipv4_address':'172.30.80.254'}
d['services']['proxy']['networks']=networks
p.write_text(yaml.safe_dump(d,sort_keys=False))
# Compose owns the endpoint so its IP remains reserved across restart/recreation.
env=dict(os.environ,KASM_UID=subprocess.check_output(['id','-u','kasm'],text=True).strip(),KASM_GID=subprocess.check_output(['id','-g','kasm'],text=True).strip())
subprocess.run(['docker','compose','up','-d','--no-deps','proxy'],cwd=p.parent,env=env,check=True)
print('PROXY_NETWORK_PINNED')
