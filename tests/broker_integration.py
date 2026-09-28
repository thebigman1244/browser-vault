import gzip, http.server, json, os, pathlib, tempfile, secrets, ssl, subprocess, threading, time, urllib.request, urllib.error

# Exercise the real broker using an isolated local Kasm stub and no production sessions.
if os.name != 'posix' or os.geteuid() != 0:
    raise SystemExit('Run this test in a disposable Linux environment as root; the broker requires root-owned health reports.')
project = pathlib.Path(__file__).resolve().parents[1]
temporary = tempfile.TemporaryDirectory(prefix='browser-vault-test-')
root = pathlib.Path(temporary.name)
state = root/'state'; state.mkdir(mode=0o700)
health = root/'health.json'
process = None

def start_broker():
    global process
    environment = dict(os.environ, VAULT_CONFIG=str(conf), VAULT_STATE=str(state), VAULT_HEALTH=str(health), VAULT_STATIC=str(project/'selfhost-dist'))
    process = subprocess.Popen(['node', str(project/'selfhost/server.mjs')], env=environment, stdout=subprocess.DEVNULL)

def stop_broker():
    global process
    if process:
        process.terminate()
        process.wait(timeout=10)
        process=None

def restart_broker():
    stop_broker()
    start_broker()

key = secrets.token_urlsafe(24)
active = False; token = 0; requested = {}

class KasmStub(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_POST(self):
        global active, token, requested
        payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if self.path.endswith('/request_kasm'):
            requested=payload;active=True;result={'kasm_id':'isolated-test'}
        elif self.path.endswith('/destroy_kasm'):
            active=False;result={}
        elif active:
            token+=1;result={'kasm':{'operational_status':'running'},'kasm_url':'/#/connect/kasm/isolated-test/mock/token-'+str(token)}
        else:result={'error_message':'Invalid kasm_id'}
        data=json.dumps(result).encode();self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)

def set_health(age=0, **overrides):
    report={'version':1,'checkedAt':int(time.time()*1000)-age,'checks':dict(firewall=True,routing=True,vpn=True,proxy=True)}
    report['checks'].update(overrides);health.write_text(json.dumps(report));health.chmod(0o644)

def request(path,method='GET',data=None,authorized=True,origin=None):
    headers={'Content-Type':'application/json'}
    if authorized:headers['Authorization']='Bearer '+key
    if origin:headers['Origin']=origin
    req=urllib.request.Request('http://127.0.0.1:8081'+path,method=method,headers=headers,data=json.dumps(data).encode() if data is not None else None)
    try:response=urllib.request.urlopen(req,timeout=10)
    except urllib.error.HTTPError as e:response=e
    return response.status,json.load(response)

def ready():
    for _ in range(40):
        try:
            if request('/api/status')[0]==200:return
        except OSError:pass
        time.sleep(.25)
    raise AssertionError('Test broker not ready')

server=None
try:
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=localhost','-addext','subjectAltName=IP:127.0.0.1','-keyout',str(root/'key.pem'),'-out',str(root/'cert.pem')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    (root/'key.pem').chmod(0o600);(root/'cert.pem').chmod(0o644)
    server=http.server.ThreadingHTTPServer(('127.0.0.1',18444),KasmStub)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(root/'cert.pem',root/'key.pem')
    server.socket=context.wrap_socket(server.socket,server_side=True)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    config={'authMode':'key','accessKey':key,'port':8081,'allowedOrigins':['https://vault.example.com'],'isolationVerified':True,'kasmApiKey':'mock','kasmApiSecret':'mock','kasmUserId':'mock','kasmOrigin':'https://127.0.0.1:18444','kasmPublicOrigin':'https://view.example.com','kasmCertificate':str(root/'cert.pem'),'workspaces':{'chromium:balanced':{'id':'mock-workspace'}}}
    conf=root/'config.json';conf.write_text(json.dumps(config));conf.chmod(0o600)
    start_broker()
    ready()
    launch={'browser':'chromium','profile':'balanced','minutes':5,'display':'smooth','url':'https://example.com'}
    assert request('/api/status',authorized=False)[0]==401
    assert request('/api/sessions','POST',launch,origin='https://hostile.example')[0]==403
    assert request('/api/sessions','POST',launch)[0]==503
    set_health(age=60000);assert request('/api/sessions','POST',launch)[0]==503
    set_health(vpn=False);assert request('/api/sessions','POST',launch)[0]==503
    set_health(firewall=False);assert request('/api/sessions','POST',launch)[0]==503
    assert not active
    print('PASS authentication and launch refusal for missing, stale, VPN-failed and firewall-failed checks',flush=True)
    set_health()
    for bad in [{'url':'http://2130706433'},{'minutes':999},{'display':'unsafe-override'}]:
        response=request('/api/sessions','POST',{**launch,**bad})
        assert response[0]==400, (bad,response)
    code,s=request('/api/sessions','POST',launch);assert code==201,(code,s)
    assert s['expiresAt']-s['startedAt']==300000
    assert requested['environment']['KVNC_ENCODING_MAX_FRAME_RATE']=='30'
    assert 'KVNC_DESKTOP_ALLOW_RESIZE' not in requested['environment']
    assert requested['enable_sharing'] is False
    assert request('/api/sessions','POST',launch)[0]==409
    first=request('/api/status')[1]['session'];assert first['state']=='running'
    second=request('/api/sessions/reconnect','POST')[1];assert second['viewUrl']!=first['viewUrl']
    restart_broker();ready()
    third=request('/api/status')[1]['session'];assert third['viewUrl']!=second['viewUrl']
    print('PASS bounded timers, safe display options, local-URL rejection, single session and refreshed display links',flush=True)
    asset=next((project/'selfhost-dist/assets').glob('*.js.gz')).with_suffix('')
    req=urllib.request.Request('http://127.0.0.1:8081/assets/'+asset.name,headers={'Accept-Encoding':'gzip'})
    with urllib.request.urlopen(req) as response:
        compressed=response.read();assert response.headers['Content-Encoding']=='gzip';assert 'private' in response.headers['Cache-Control'];assert 'immutable' in response.headers['Cache-Control'];assert gzip.decompress(compressed)==asset.read_bytes()
    print('PASS precompressed static assets and private immutable cache policy',flush=True)
    persisted=json.loads((state/'session.json').read_text());persisted['expiresAt']=int(time.time()*1000)-1000
    (state/'session.json').write_text(json.dumps(persisted))
    restart_broker();ready()
    assert request('/api/status')[1]['session'] is None and not active
    print('PASS expired session removed after broker restart',flush=True)
    print('ALL_BROKER_INTEGRATION_CHECKS_PASSED',flush=True)
finally:
    stop_broker()
    if server:server.shutdown()
    if server: server.server_close()
    temporary.cleanup()
