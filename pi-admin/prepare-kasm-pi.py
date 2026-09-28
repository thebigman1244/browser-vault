import copy,json,pathlib,secrets,uuid,yaml
root=pathlib.Path('/root/browser-vault-install')
seed=root/'kasm_release/conf/database/seed_data'
data=yaml.safe_load((seed/'default_images_arm64.yaml').read_text())
amd=yaml.safe_load((seed/'default_images_amd64.yaml').read_text())
props=yaml.safe_load((seed/'default_properties.yaml').read_text())
profiles={'light':(1,2),'balanced':(2,3),'power':(3,4)}
selected=[]
mapping={}
for browser in ['chromium','firefox','brave']:
    source=next(i for i in data['images']+amd['images'] if i['name'].startswith('kasmweb/'+browser+':'))
    for profile,(cpu,ram) in profiles.items():
        item=copy.deepcopy(source)
        item.update(image_id=str(uuid.uuid4()),enabled=True,friendly_name=f'Vault {browser.title()} - {profile.title()}',cores=cpu,memory_bytes=ram*1024**3,cpu_allocation_method='Quotas',restrict_network_names=['vault_browsers'],allow_network_selection=False,persistent_profile_path=None,volume_mappings={},session_time_limit=1800)
        item['restrict_to_network']=True
        item['run_config']={'hostname':'browser','security_opt':['no-new-privileges:true'],'cap_drop':['ALL'],'pids_limit':512,'dns':['1.1.1.1','9.9.9.9'],'memswap_limit':ram*1024**3}
        selected.append(item)
        mapping[browser+':'+profile]={'id':item['image_id'],'cpu':cpu,'ram':ram}
data['images']=selected
data['group_images']=[{'group_id':'68d557ac-4cac-42cc-a9f3-1c7c853de0f3','image_id':i['image_id']} for i in selected]
restrictions={'allow_kasm_clipboard_down','allow_kasm_clipboard_up','allow_kasm_clipboard_seamless','allow_kasm_downloads','allow_kasm_uploads','allow_kasm_microphone','allow_kasm_webcam','allow_kasm_gamepad','allow_kasm_rdp_client_file_transfer_clipboard','allow_persistent_profile','allow_kasm_sharing','inject_ssh_keys','allow_kasm_printing','allow_kasm_rdp_map_local_drives','allow_kasm_rdp_webauthn_passthrough','allow_kasm_smart_card_passthrough','allow_kasm_stop','allow_kasm_pause'}
for setting in props['group_settings']:
    if setting['name'] in restrictions:setting['value']='False'
    if setting['name']=='max_kasms_per_user':setting['value']='1'
    if setting['name']=='session_time_limit':setting['value']='1800'
    if setting['name']=='keepalive_expiration':setting['value']='300'
for setting in props['settings']:
    if setting['name']=='same_site':setting['value']='None'
    if setting['name']=='default_cpu_allocation_method':setting['value']='Quotas'
uid=str(uuid.uuid4())
for user in props['users']:
    if user['username']=='user@kasm.local':user['user_id']=uid
for association in props['user_groups']:
    if association['user_id']=='${uuid:user_id:2}':association['user_id']=uid
(seed/'default_images_arm64.yaml').write_text(yaml.safe_dump(data,sort_keys=False))
(seed/'default_properties.yaml').write_text(yaml.safe_dump(props,sort_keys=False))
config={'authMode':'key','accessKey':secrets.token_urlsafe(36),'kasmUserId':uid,'kasmApiKey':'','kasmApiSecret':'','kasmOrigin':'https://127.0.0.1','kasmPublicOrigin':'https://127.0.0.1:18443','kasmCertificate':'/etc/browser-vault/kasm.crt','allowedOrigins':['http://127.0.0.1:18080'],'workspaces':mapping,'isolationVerified':False,'port':8080}
(root/'broker.json').write_text(json.dumps(config,indent=2))
(root/'admin.json').write_text(json.dumps({'admin_password':secrets.token_urlsafe(36),'user_password':secrets.token_urlsafe(36)}))
for name in ['broker.json','admin.json']:(root/name).chmod(0o600)
print('Prepared nine restricted ARM64 browser/resource profiles.')
