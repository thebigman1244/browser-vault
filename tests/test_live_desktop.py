"""Manual deployment check; run only in a fresh desktop created for testing."""
import argparse,hashlib,json,pathlib,subprocess,urllib.request

def run(*args,stdin=None):
    return subprocess.check_output(args,input=stdin,text=True,timeout=45).strip()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['verify','seed','cleanup']);parser.add_argument('--private-targets',nargs=3)
    args=parser.parse_args()
    state=json.loads(pathlib.Path('/var/lib/browser-vault/session.json').read_text())
    assert state['browser']=='desktop' and state['state']=='running','Start a fresh desktop test session first'
    cs=json.loads(run('docker','inspect',*run('docker','ps','-q').split()))
    c=next(c for c in cs if state['id'] in c['Name'] or state['id'] in json.dumps(c['Config'].get('Labels',{})));cid=c['Id'];h=c['HostConfig']
    if args.mode=='verify':
        assert set(c['NetworkSettings']['Networks'])=={'vault_browsers'}
        assert not c['Mounts'] and not h['Privileged'] and h['CapDrop']==['ALL']
        assert c['Config']['User'] not in ('','0','root')
        assert h['PidsLimit']==512 and h['Memory']==h['MemorySwap']
        assert 'no-new-privileges:true' in h['SecurityOpt'] or 'no-new-privileges' in h['SecurityOpt']
        flags=run('docker','exec',cid,'sh','-c',"grep -E '^(CapBnd|NoNewPrivs|Seccomp):' /proc/1/status")
        assert 'Seccomp:\t2' in flags and 'NoNewPrivs:\t1' in flags and 'CapBnd:\t0000000000000000' in flags
        cpu=h.get('NanoCpus',0)/1e9 or h['CpuQuota']/h['CpuPeriod']
        print('PASS desktop hardening: non-root, no mounts, no capabilities, seccomp, no privilege escalation; CPU='+str(cpu)+' RAM GiB='+str(h['Memory']/1024**3))
        assert args.private_targets,'Provide Pi, workstation and router probe IPs'
        before=run('iptables','-t','mangle','-L','VAULT-EARLY','-v','-n','-x')
        targets=[('Pi',args.private_targets[0],22),('workstation',args.private_targets[1],18089),('router',args.private_targets[2],80),('VM host','172.30.80.1',443),('display proxy','172.30.80.254',443),('management network','172.18.0.1',443),('metadata','169.254.169.254',80),('VM gateway','10.77.0.2',22),('IPv6','2606:4700:4700::1111',443)]
        code='import socket,concurrent.futures\ntargets='+repr(targets)+'''\ndef probe(target):
 name,host,port=target
 try:s=socket.create_connection((host,port),timeout=2);s.close();return name,False
 except OSError:return name,True
for name,blocked in concurrent.futures.ThreadPoolExecutor(9).map(probe,targets):
 assert blocked,name+' unexpectedly reachable'
 print('PASS blocked '+name)
s=socket.create_connection(('example.com',443),timeout=10);s.close();print('PASS public HTTPS reachable')
'''
        print(run('docker','exec','-i',cid,'python3','-',stdin=code))
        after=run('iptables','-t','mangle','-L','VAULT-EARLY','-v','-n','-x')
        def drops(t):return sum(int(x.split()[0]) for x in t.splitlines() if 'DROP' in x and x.split()[0].isdigit())
        assert drops(after)>drops(before),'Expected live firewall drop counters'
        print('PASS private-address firewall drop counters increased')
        home=run('curl','--fail','--silent','--max-time','15','https://api.ipify.org')
        remote=run('docker','exec',cid,'curl','--fail','--silent','--max-time','15','https://api.ipify.org')
        assert home!=remote;print('PASS desktop uses a different public IP through its VPN')
    elif args.mode=='seed':
        with urllib.request.urlopen('https://secure.eicar.org/eicar.com.txt',timeout=30) as response:sample=response.read(1024)
        assert len(sample)==68
        files={'vault-test-eicar.txt':sample,'vault-test-notes.txt':b'Harmless plain text test notes.'}
        code='from pathlib import Path\np=Path("/home/kasm-user/Downloads");p.mkdir(exist_ok=True)\n'
        for name,data in files.items():code+='with (p/'+repr(name)+').open("xb") as f:f.write('+repr(data)+')\n'
        run('docker','exec','-i',cid,'python3','-',stdin=code)
        print('CREATED two harmless scanner test fixtures inside desktop Downloads only')
    else:
        code='''from pathlib import Path
p=Path('/home/kasm-user/Downloads')
for name in ['vault-test-eicar.txt','vault-test-notes.txt']:
 f=p/name
 if f.exists():
  data=f.read_bytes()
  assert data==b'Harmless plain text test notes.' or (len(data)==68 and b'EICAR-STANDARD-ANTIVIRUS-TEST-FILE' in data)
  f.unlink()
'''
        run('docker','exec','-i',cid,'python3','-',stdin=code)
        print('REMOVED only the two known test fixtures')

if __name__=='__main__':main()
