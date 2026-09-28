#!/usr/bin/python3
"""Add desktop profiles by copying the installed browser isolation policy."""
import copy,json,pathlib,subprocess,uuid,os,sys
CONFIG=pathlib.Path('/etc/browser-vault/config.json')
BACKUP=pathlib.Path('/root/browser-vault-backup-1.2')
IMAGE='kasmweb/ubuntu-noble-desktop:1.19.0-rolling-daily'
def sql(query):
    return subprocess.check_output(['docker','exec','-i','kasm_db','psql','-U','kasmapp','-d','kasm','-At','-v','ON_ERROR_STOP=1'],input=query,text=True).strip()
def quote(value):return "'"+str(value).replace("'","''")+"'"
config=json.loads(CONFIG.read_text())
register_only=sys.argv[1:]==['--register-only']
assert not sys.argv[1:] or register_only,'Unsupported arguments'
if not register_only:
    image=json.loads(subprocess.check_output(['docker','image','inspect',IMAGE],text=True))[0]
    assert image['Architecture']=='arm64'
    assert image['Config']['User'] not in ('','0','root')
    config['desktopImageDigest']=next(x for x in image['RepoDigests'] if x.startswith('kasmweb/ubuntu-noble-desktop@sha256:'))
BACKUP.mkdir(mode=0o700,exist_ok=True)
if not (BACKUP/'config.json').exists():
    (BACKUP/'config.json').write_bytes(CONFIG.read_bytes());(BACKUP/'config.json').chmod(0o600)
for profile in ('light','balanced','power'):
    base=config['workspaces']['chromium:'+profile]
    old=str(uuid.UUID(base['id']))
    source=json.loads(sql('SELECT row_to_json(i) FROM images i WHERE image_id='+quote(old)+';'))
    new=str(uuid.uuid5(uuid.NAMESPACE_URL,'browser-vault/desktop/1.2/'+profile))
    assert source['restrict_to_network'] is True and source['restrict_network_names']==['vault_browsers']
    assert not source.get('volume_mappings') and not source.get('persistent_profile_path')
    policy=source['run_config']
    if isinstance(policy,str):policy=json.loads(policy)
    assert policy['cap_drop']==['ALL'] and 'no-new-privileges:true' in policy['security_opt']
    item=copy.deepcopy(source)
    item.update(image_id=new,name=IMAGE,friendly_name='Vault Desktop - '+profile.title(),enabled=True)
    if 'description' in item:item['description']='Disposable Ubuntu desktop inside the isolated Browser Vault VM.'
    if 'exec_config' in item:item['exec_config']={}
    item['run_config']={**policy,'hostname':'vault-desktop'}
    if not sql('SELECT image_id FROM images WHERE image_id='+quote(new)+';'):
        sql('BEGIN; INSERT INTO images SELECT (json_populate_record(NULL::images,'+quote(json.dumps(item))+')).*; INSERT INTO group_images(group_id,image_id) SELECT group_id,'+quote(new)+' FROM group_images WHERE image_id='+quote(old)+'; COMMIT;')
    config['workspaces']['desktop:'+profile]={**base,'id':new}
temporary=CONFIG.with_suffix('.tmp');temporary.write_text(json.dumps(config,indent=2));temporary.chmod(0o600)
original=CONFIG.stat();os.chown(temporary,original.st_uid,original.st_gid);os.replace(temporary,CONFIG)
print('DESKTOP_PROFILES_REGISTERED; pull and verify the image before enabling the new launcher.' if register_only else 'DESKTOP_PROFILES_READY: light, balanced, power. Existing isolation policy preserved.')
