from release_config import load
settings=load()
import subprocess,json,pathlib,time,socket,uuid,concurrent.futures
def run(args,**kw):return subprocess.run(args,text=True,capture_output=True,timeout=kw.pop('timeout',45),**kw)
def check(args,**kw):
 p=run(args,**kw)
 if p.returncode:raise RuntimeError('Check failed: '+repr(args[:3])+' '+p.stderr[-300:])
 return p.stdout
state=json.loads(pathlib.Path('/var/lib/browser-vault/session.json').read_text())
assert state and state['state']=='running','Launch a browser first'
containers=json.loads(check(['docker','inspect',*check(['docker','ps','-q']).split()]))
matches=[x for x in containers if state['id'] in x['Name'] or state['id'] in json.dumps(x['Config'].get('Labels',{}))]
assert len(matches)==1
c=matches[0];cid=c['Id'];h=c['HostConfig']
assert set(c['NetworkSettings']['Networks'])=={'vault_browsers'}
assert not c['Mounts'] and not h['Privileged'] and h['CapDrop']==['ALL']
assert c['Config']['User'] not in ['','root','0']
assert h['Memory']==h['MemorySwap'] and h['PidsLimit']==512
print('PASS container: dedicated network, no mounts, non-root, capabilities dropped, memory and process limits',flush=True)
def browser(args,**kw):return run(['docker','exec',cid,*args],**kw)
def browser_ip():
 p=browser(['curl','--fail','--silent','--max-time','15','https://api.ipify.org'])
 assert p.returncode==0,'VPN browser HTTPS failed'
 return p.stdout.strip()
home=check(['curl','--fail','--silent','--max-time','15','https://api.ipify.org']).strip()
exitip=browser_ip();assert exitip!=home,'Browser still uses home public IP'
print('PASS browser public address differs from management/home address',flush=True)
handshakes=check(['wg','show','vault-wg','latest-handshakes']).splitlines()
assert any(int(x.split()[-1])>time.time()-180 for x in handshakes)
print('PASS recent WireGuard handshake',flush=True)
counter_before=check(['iptables','-t','mangle','-L','VAULT-EARLY','-v','-n','-x'])
probes='''import socket,concurrent.futures
targets=[('Pi','192.168.1.10',22),('Windows','192.168.1.20',18089),('router','192.168.1.1',80),('VM host','172.30.80.1',443),('proxy','172.30.80.254',443),('management network','172.18.0.1',443),('metadata','169.254.169.254',80),('VM gateway','10.77.0.2',22),('IPv6 public','2606:4700:4700::1111',443)]
def probe(t):
 name,host,port=t
 try:s=socket.create_connection((host,port),timeout=2);s.close();return name,False
 except OSError:return name,True
for name,blocked in concurrent.futures.ThreadPoolExecutor(9).map(probe,targets):
 assert blocked,name+' unexpectedly reachable'
 print('PASS blocked '+name)
'''
for old, new in zip(['192.168.1.10','192.168.1.20','192.168.1.1'], settings['privateProbeAddresses']):
 probes=probes.replace(old,new)
p=run(['docker','exec','-i',cid,'python3','-'],input=probes)
assert p.returncode==0,p.stdout+p.stderr
print(p.stdout,flush=True)
counter_after=check(['iptables','-t','mangle','-L','VAULT-EARLY','-v','-n','-x'])
def private_packets(text):return sum(int(line.split()[0]) for line in text.splitlines() if 'DROP' in line and line.split()[0].isdigit())
assert private_packets(counter_after)>private_packets(counter_before),'No private-address drop counter increase'
print('PASS live private-address firewall counters increased during probes',flush=True)
marker='vault-dns-'+uuid.uuid4().hex
capture=subprocess.Popen(['tcpdump','-l','-n','-i','enp1s0','-A','port','53'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
tunnel_capture=subprocess.Popen(['tcpdump','-l','-n','-i','vault-wg','-A','port','53'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
time.sleep(1)
code=f'import socket\ntry:socket.gethostbyname("{marker}.example.com")\nexcept OSError:pass\n'
run(['docker','exec','-i',cid,'python3','-'],input=code,timeout=20)
capture.terminate();out,_=capture.communicate(timeout=5)
tunnel_capture.terminate();tunnel_out,_=tunnel_capture.communicate(timeout=5)
assert marker not in out,'Browser DNS leaked outside the VPN'
assert marker in tunnel_out,'DNS probe was not observed inside the VPN tunnel'
print('PASS unique browser DNS query observed inside VPN and absent from physical-interface DNS traffic',flush=True)
try:
 check(['systemctl','stop','wg-quick@vault-wg'])
 failed=browser(['curl','--fail','--silent','--connect-timeout','3','--max-time','5','https://1.1.1.1'])
 assert failed.returncode!=0,'Kill switch leaked direct public HTTPS'
 assert check(['nft','list','table','inet','vault_vpn'])
 assert 'unreachable default' in check(['ip','route','show','table','51820'])
 assert run(['curl','--fail','--silent','--max-time','10','https://example.com']).returncode==0,'Management Internet failed with VPN off'
 assert run(['curl','--silent','--max-time','5','http://127.0.0.1:8080/api/auth']).returncode==0,'Broker unreachable'
 print('PASS VPN disconnected: browser Internet blocked; kill switch persists; management and broker remain reachable',flush=True)
finally:check(['systemctl','start','wg-quick@vault-wg'])
for n in range(12):
 try:restored=browser_ip();assert restored!=home;break
 except AssertionError:
  if n==11:raise
  time.sleep(3)
print('PASS browser VPN recovered after reconnect',flush=True)
print('ALL_VPN_AND_ISOLATION_CHECKS_PASSED',flush=True)
