import json,pathlib,subprocess,uuid
from release_config import load
settings=load()
root=pathlib.Path('/root/browser-vault-install')
p=root/'broker.json';c=json.loads(p.read_text())
def sql(q):return subprocess.check_output(['docker','exec','-i','kasm_db','psql','-U','kasmapp','-d','kasm','-At','-v','ON_ERROR_STOP=1'],input=q,text=True).strip()
aid=str(uuid.UUID(c['kasmApiId']))
sql(f"BEGIN; DELETE FROM group_permissions WHERE api_id='{aid}'; INSERT INTO group_permissions(api_id,permission_id) VALUES('{aid}',100),('{aid}',352); COMMIT;")
print('API limited to user/session authentication permissions.')
sql("UPDATE images SET restrict_to_network=true;")
sql("UPDATE group_settings SET value='False' WHERE name IN ('allow_kasm_clipboard_down','allow_kasm_clipboard_up','allow_kasm_clipboard_seamless','allow_kasm_downloads','allow_kasm_uploads','allow_kasm_microphone','allow_kasm_webcam','allow_kasm_gamepad','allow_kasm_rdp_client_file_transfer_clipboard','allow_persistent_profile','allow_kasm_sharing','inject_ssh_keys','allow_kasm_printing','allow_kasm_rdp_map_local_drives','allow_kasm_rdp_webauthn_passthrough','allow_kasm_smart_card_passthrough','allow_kasm_stop','allow_kasm_pause');")
print(sql("SELECT friendly_name,cores,memory_bytes,restrict_network_names,session_time_limit FROM images ORDER BY friendly_name;"))
print(sql("SELECT name,value FROM group_settings WHERE name IN ('allow_kasm_clipboard_up','allow_kasm_clipboard_down','allow_kasm_downloads','allow_kasm_uploads','allow_kasm_microphone','allow_kasm_webcam','session_time_limit','max_kasms_per_user') ORDER BY name;"))
assert sql('SELECT count(*) FROM images;')=='9'
uid=str(uuid.UUID(c['kasmUserId']))
assert sql(f"SELECT count(*) FROM users WHERE user_id='{uid}' AND username='user@kasm.local';")=='1'
c.update(authMode='cloudflare',cloudflareAccess=settings['cloudflareAccess'],allowedOrigins=[settings['launcherOrigin'],settings['displayOrigin']],kasmPublicOrigin=settings['displayOrigin'])
c.pop('accessKey',None)
p.write_text(json.dumps(c,indent=2));p.chmod(0o600)
subprocess.run(['install','-m600','-o','browser-vault','-g','browser-vault',str(p),'/etc/browser-vault/config.json'],check=True)
subprocess.run(['systemctl','restart','browser-vault'],check=True)
print('CLOUDFLARE_AUTH_CONFIGURED')
