import pathlib,subprocess,yaml
p=pathlib.Path('/opt/kasm/current/docker/docker-compose.yaml')
data=yaml.safe_load(p.read_text())
for name,service in data['services'].items():
    image=service.get('image')
    if not image:continue
    digest=subprocess.check_output(['docker','image','inspect',image,'--format','{{index .RepoDigests 0}}'],text=True).strip()
    if '@sha256:' not in digest:raise RuntimeError('Service image digest is unavailable: '+name)
    service['image']=digest
backup=p.with_suffix('.yaml.before-pin')
if not backup.exists():backup.write_text(p.read_text());backup.chmod(0o600)
p.write_text(yaml.safe_dump(data,sort_keys=False));p.chmod(0o600)
print('Pinned installed service images for repeatable startup without downloads.')
