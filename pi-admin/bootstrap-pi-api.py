import json,pathlib,subprocess,ssl,urllib.request,http.cookiejar
root=pathlib.Path('/root/browser-vault-install')
p=root/'broker.json'; c=json.loads(p.read_text())
ctx=ssl.create_default_context(cafile='/opt/kasm/current/certs/kasm_nginx.crt');ctx.check_hostname=False
opener=urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def api(endpoint,payload):
    req=urllib.request.Request('https://127.0.0.1/api/'+endpoint,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    return json.load(opener.open(req,timeout=45))
login=api('authenticate',{'username':'admin@kasm.local','password':json.loads((root/'admin.json').read_text())['admin_password']})
if not login.get('token'):raise RuntimeError('Admin authentication failed; response keys: '+str(list(login)))
auth={'username':'admin@kasm.local','token':login['token']}
if not c.get('kasmApiKey'):
    result=api('admin/create_api_configs',{**auth,'api_config':{'name':'Browser Vault launcher','enabled':True,'read_only':False}})
    if 'api_config' not in result:raise RuntimeError('API creation failed; keys: '+str(list(result)))
    a=result['api_config'];c.update(kasmApiKey=a['api_key'],kasmApiSecret=a['api_key_secret'],kasmApiId=a['api_id'])
    p.write_text(json.dumps(c,indent=2));p.chmod(0o600)
# Do not print credentials or administrative API responses.
print('API_IDENTITY_CREATED')
