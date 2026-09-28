from release_config import load
settings=load()
import json,pathlib,ssl,urllib.request,subprocess,time,socket
root=pathlib.Path('/root/browser-vault-install')
cfg=json.loads((root/'broker.json').read_text())
ctx=ssl.create_default_context(cafile='/opt/kasm/current/certs/kasm_nginx.crt')
ctx.check_hostname=True
def api(name,**body):
    data={'api_key':cfg['kasmApiKey'],'api_key_secret':cfg['kasmApiSecret'],'user_id':cfg['kasmUserId'],**body}
    req=urllib.request.Request('https://127.0.0.1/api/public/'+name,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
    result=json.load(urllib.request.urlopen(req,context=ctx,timeout=45))
    if result.get('error_message'):raise RuntimeError(result['error_message'])
    return result
def docker(*args,stdin=None):return subprocess.check_output(['docker',*args],input=stdin,text=True).strip()
network_test='''import socket
targets=[('public HTTPS','example.com',443,True),('browser gateway','172.30.80.1',443,False),('Pi','192.168.1.10',22,False),('Windows','192.168.1.20',445,False),('router','192.168.1.1',80,False),('VM gateway','10.77.0.2',22,False),('metadata','169.254.169.254',80,False),('other containers','172.18.0.1',443,False)]
for label,host,port,expected in targets:
 try:
  s=socket.create_connection((host,port),timeout=2);s.close();actual=True
 except OSError:actual=False
 assert actual==expected,(label,actual)
 print(label+': '+('reachable' if actual else 'blocked'))
'''
for old, new in zip(['192.168.1.10','192.168.1.20','192.168.1.1'], settings['privateProbeAddresses']):
 network_test=network_test.replace(old,new)
results=[]
for browser,profile in [('chromium','light'),('firefox','balanced'),('brave','power')]:
    workspace=cfg['workspaces'][browser+':'+profile]
    print('WAITING FOR IMAGE '+browser,flush=True)
    for n in range(180):
        if subprocess.run(['docker','image','inspect','kasmweb/'+browser+':1.19.0-rolling-daily'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:break
        time.sleep(5)
    else:raise RuntimeError('Image download did not complete')
    print('START '+browser+' '+profile,flush=True)
    for attempt in range(12):
        try:
            launch=api('request_kasm',image_id=workspace['id'],enable_sharing=False,kasm_url='https://example.com')
            break
        except RuntimeError as e:
            if 'No resources are available' not in str(e) or attempt==11:raise
            time.sleep(10)
    sid=launch['kasm_id']
    try:
        for n in range(60):
            status=api('get_kasm_status',kasm_id=sid)
            op=status.get('kasm',{}).get('operational_status',status.get('operational_status'))
            if op=='running':break
            if op in ['failed','error']:raise RuntimeError('Workspace failed to start')
            time.sleep(3)
        else:raise RuntimeError('Workspace startup timed out')
        ids=docker('ps','-q').splitlines()
        containers=json.loads(docker('inspect',*ids))
        matches=[c for c in containers if sid in c['Name'] or sid in json.dumps(c.get('Config',{}).get('Labels',{}))]
        if len(matches)!=1:raise RuntimeError('Cannot uniquely identify browser container')
        c=matches[0];h=c['HostConfig'];cid=c['Id']
        assert not h['Privileged']
        assert h['CapDrop']==['ALL']
        assert 'no-new-privileges:true' in h['SecurityOpt'] or 'no-new-privileges' in h['SecurityOpt']
        assert h['PidsLimit']==512
        assert h['Memory']==workspace['ram']*1024**3,(h['Memory'],workspace)
        assert h['MemorySwap']==h['Memory']
        cpu=h.get('NanoCpus',0)/1e9 or h['CpuQuota']/h['CpuPeriod']
        assert cpu==workspace['cpu'],cpu
        assert set(c['NetworkSettings']['Networks'])=={'vault_browsers'},{k:{'ip':v['IPAddress'],'gateway':v['Gateway']} for k,v in c['NetworkSettings']['Networks'].items()}
        assert not h.get('Devices') and not h.get('DeviceRequests')
        assert c['Config']['User'] not in ('','0','root')
        mounts=[{'type':m['Type'],'source':m['Source'],'destination':m['Destination']} for m in c['Mounts']]
        assert not mounts, 'Browser must not have any host mounts'
        flags=docker('exec',cid,'sh','-c',"grep -E '^(CapBnd|NoNewPrivs|Seccomp):' /proc/1/status")
        assert 'Seccomp:\t2' in flags and 'NoNewPrivs:\t1' in flags and 'CapBnd:\t0000000000000000' in flags,flags
        print(docker('exec','-i',cid,'python3','-',stdin=network_test),flush=True)
        processes=docker('exec',cid,'ps','-eo','comm').splitlines()
        expected={'chromium':['chromium','chrome'],'firefox':['firefox'],'brave':['brave','brave-browser','chrome']}[browser]
        assert any(x.strip() in expected for x in processes),processes
        assert subprocess.run(['docker','exec',cid,'test','!','-e','/home/kasm-user/vault-test-marker']).returncode==0
        docker('exec',cid,'sh','-c','echo disposable-test > /home/kasm-user/vault-test-marker')
        results.append({'browser':browser,'profile':profile,'cpu':cpu,'ramGiB':workspace['ram'],'architecture':docker('exec',cid,'uname','-m'),'mounts':mounts,'network':'passed','containerHardening':'passed','browserProcess':'running'})
        (root/'workspace-test-results.json').write_text(json.dumps(results,indent=2))
        print('PASS '+browser,flush=True)
    finally:
        api('destroy_kasm',kasm_id=sid)
        for n in range(45):
            if not any(sid in line for line in docker('ps','-a','--format','{{.Names}}').splitlines()):break
            time.sleep(2)
        else:raise RuntimeError('Browser container was not destroyed')
        print('DESTROYED '+browser,flush=True)
(root/'workspace-test-results.json').write_text(json.dumps(results,indent=2))
print('ALL_WORKSPACE_TESTS_PASSED',flush=True)
