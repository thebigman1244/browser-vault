import json,pathlib,subprocess
root=pathlib.Path('/root/browser-vault-install')
results=json.loads((root/'workspace-test-results.json').read_text())
assert {r['browser'] for r in results}=={'chromium','firefox','brave'}
assert all(r['network']=='passed' and r['containerHardening']=='passed' and r['browserProcess']=='running' for r in results)
for p in [root/'broker.json',pathlib.Path('/etc/browser-vault/config.json')]:
 c=json.loads(p.read_text());c['isolationVerified']=True;p.write_text(json.dumps(c,indent=2));p.chmod(0o600)
drop=pathlib.Path('/etc/systemd/system/kasm.service.d');drop.mkdir(exist_ok=True)
(drop/'recovery.conf').write_text('[Unit]\nStartLimitIntervalSec=0\n[Service]\nRestart=on-failure\nRestartSec=30\n')
subprocess.run(['systemctl','daemon-reload'],check=True)
subprocess.run(['systemctl','restart','browser-vault'],check=True)
print('LIVE_LAUNCHER_ENABLED_AFTER_WORKSPACE_TESTS')
