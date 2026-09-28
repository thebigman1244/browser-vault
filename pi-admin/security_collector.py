#!/usr/bin/python3
"""Collect bounded download snapshots; scan under a separate, networkless user.

No Docker socket, host folder, or scanner report is exposed to a session.
Antivirus results describe the collected bytes, not a real-time execution gate.
"""
import hashlib,json,os,pathlib,pwd,re,selectors,shutil,signal,subprocess,tarfile,time

ROOT=pathlib.Path('/run/browser-vault-security')
CACHE=pathlib.Path('/var/lib/browser-vault-security/cache.json')
SESSION=pathlib.Path('/var/lib/browser-vault/session.json')
REQUEST=SESSION.with_name('scan-request.json')
MAX_FILE=32*1024**2
MAX_BATCH=128*1024**2
MAX_FILES=100
RISKY={'.exe','.dll','.msi','.scr','.bat','.cmd','.ps1','.vbs','.js','.jar','.apk','.deb','.rpm','.sh','.py','.desktop','.lnk','.iso','.docm','.xlsm','.pptm'}

def run(*args,timeout=10):
    return subprocess.run(args,check=True,capture_output=True,text=True,timeout=timeout).stdout.strip()

def atomic(file,data,mode=0o600):
    file.parent.mkdir(exist_ok=True,parents=True)
    temp=file.with_suffix('.tmp');temp.write_text(json.dumps(data)+'\n');temp.chmod(mode);os.replace(temp,file)

def load(file,default):
    try:return json.loads(file.read_text())
    except (OSError,ValueError):return default

def engine_status():
    definitions=[p for p in pathlib.Path('/var/lib/clamav').glob('*') if p.suffix in ('.cvd','.cld')]
    daily=[p for p in definitions if p.stem=='daily']
    stamp=0
    try:
        version=run('clamscan','--version');available=bool(daily)
        # The database build time matters, not when an old file was downloaded.
        try:stamp=time.mktime(time.strptime(version.split('/',2)[2],'%a %b %d %H:%M:%S %Y'))
        except (ValueError,IndexError):pass
    except Exception:version='Unavailable';available=False
    return dict(available=available,version=version,definitionsAt=int(stamp*1000) or None,definitionsFresh=bool(stamp and 0<=time.time()-stamp<48*3600))

def file_warnings(name,head):
    warnings=[];suffix=pathlib.PurePosixPath(name).suffix.lower()
    if suffix in RISKY:warnings.append('Executable, script, installer, or macro-capable file. Review before opening.')
    if any(c in name for c in '\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069'):warnings.append('Filename contains text-direction controls that can disguise its extension.')
    if re.search(r'\.(pdf|png|jpg|txt|docx)\.[^.]+$',name,re.I):warnings.append('Double file extension; check the real file type.')
    if head.startswith((b'MZ',b'\x7fELF')):warnings.append('Executable content detected'+(' despite its filename.' if suffix not in RISKY else '.'))
    return warnings

def download_snapshot(cid,destination):
    # Do not execute tools from the untrusted container. docker cp does not use -L.
    proc=subprocess.Popen(['docker','cp',cid+':/home/kasm-user/Downloads/.','-'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=True)
    selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ)
    total=0;deadline=time.monotonic()+20
    try:
        with destination.open('wb') as out:
            while selector.get_map():
                if time.monotonic()>deadline:raise RuntimeError('Download snapshot timed out. Some files were not scanned.')
                for key,_ in selector.select(.2):
                    data=os.read(key.fd,65536)
                    if not data:selector.unregister(key.fileobj);continue
                    total+=len(data)
                    if total>MAX_BATCH:raise RuntimeError('Downloads exceed the 128 MiB snapshot limit. Some files were not scanned.')
                    out.write(data)
        if proc.wait(timeout=3):raise RuntimeError('Downloads could not be read. The session may be starting or ending.')
    finally:
        selector.close()
        if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL)
        proc.wait();proc.stdout.close()

def collect_files(archive,inbox,group):
    records=[];total=0;incomplete=False
    with tarfile.open(archive,'r:') as tar:
        for member in tar:
            if member.isdir():continue
            if len(records)>=MAX_FILES:incomplete=True;break
            name=member.name.removeprefix('./')
            if name.startswith('Downloads/'):name=name[len('Downloads/'):]
            name=''.join(c if ord(c)>=32 else '?' for c in name)[:500]
            record=dict(name=name,size=max(0,member.size),sha256=None,status='not_scanned',scannedAt=None,findings=[])
            records.append(record)
            if not member.isfile():record['findings']=['Links and special files are not followed or scanned.'];continue
            if member.size>MAX_FILE or total+member.size>MAX_BATCH:record['findings']=['File exceeds the scan size limit.'];continue
            if name.lower().endswith(('.crdownload','.part','.partial','.download','.tmp')):record['status']='pending';record['findings']=['Download is still in progress.'];continue
            # Never extract names or paths supplied by the archive.
            temporary=inbox/('file-'+str(len(records)))
            digest=hashlib.sha256();head=b'';copied=0
            with tar.extractfile(member) as source,temporary.open('xb') as output:
                while True:
                    block=source.read(65536)
                    if not block:break
                    copied+=len(block)
                    if copied>member.size or copied>MAX_FILE:raise RuntimeError('Invalid download snapshot.')
                    if not head:head=block[:64]
                    digest.update(block);output.write(block)
            total+=copied
            if copied!=member.size:raise RuntimeError('Incomplete download snapshot.')
            record['sha256']=digest.hexdigest();record['status']='pending';record['findings']=file_warnings(name,head)
            destination=inbox/record['sha256']
            os.replace(temporary,destination);os.chown(destination,0,group);destination.chmod(0o440)
    return records,incomplete

def scan(inbox):
    # The parser is not root and cannot reach Docker, LAN, Internet, or writable
    # system paths. A timeout/limit/error is never interpreted as a clean scan.
    command=['systemd-run','--quiet','--wait','--pipe','--collect','--unit=browser-vault-scan-job',
        '-p','User=vault-scan','-p','Group=vault-scan','-p','NoNewPrivileges=yes',
        '-p','ProtectSystem=strict','-p','ProtectHome=yes','-p','PrivateTmp=yes',
        '-p','PrivateDevices=yes','-p','PrivateNetwork=yes','-p','ProtectKernelTunables=yes',
        '-p','ProtectKernelModules=yes','-p','ProtectControlGroups=yes','-p','ProtectProc=invisible',
        '-p','RestrictNamespaces=yes','-p','RestrictAddressFamilies=AF_UNIX','-p','CapabilityBoundingSet=',
        '-p','MemoryMax=1536M','-p','MemorySwapMax=0','-p','CPUQuota=75%','-p','TasksMax=32',
        '-p','RuntimeMaxSec=90','-p','LimitFSIZE=134217728','-p','SystemCallFilter=@system-service',
        '/usr/bin/clamscan','--stdout','--no-summary','--infected','--recursive',
        '--max-filesize=32M','--max-scansize=64M','--max-files=1000','--max-recursion=12',
        '--alert-encrypted=yes','--alert-exceeds-max=yes',str(inbox)]
    result=subprocess.run(command,capture_output=True,text=True,timeout=105)
    found={}
    for line in result.stdout.splitlines():
        match=re.fullmatch(re.escape(str(inbox))+r'/([a-f0-9]{64}): (.{1,300}) FOUND',line)
        if match:found[match[1]]=match[2]
    code=result.returncode
    if re.search(r'\b(ERROR|WARNING)\b',result.stdout+'\n'+result.stderr):code=2
    return code,found

def available_memory():
    return int(re.search(r'^MemAvailable:\s+(\d+)',pathlib.Path('/proc/meminfo').read_text(),re.M)[1])*1024

def main():
    ROOT.mkdir(exist_ok=True,mode=0o755)
    report=dict(version=1,checkedAt=int(time.time()*1000),sessionId=None,state='idle',message='No active session.',files=[],engine=engine_status())
    state=load(SESSION,None)
    if not state or not re.fullmatch(r'[a-f0-9-]{36}',str(state.get('id',''))):
        CACHE.unlink(missing_ok=True)
        if (ROOT/'inbox').exists():shutil.rmtree(ROOT/'inbox')
        (ROOT/'snapshot.tar').unlink(missing_ok=True)
        atomic(ROOT/'status.json',report,0o644);return
    report['sessionId']=state['id']
    try:
        ids=run('docker','ps','-q').splitlines()
        containers=json.loads(run('docker','inspect',*ids)) if ids else []
        matches=[c for c in containers if state['id'] in c['Name'] or state['id'] in json.dumps(c.get('Config',{}).get('Labels',{}))]
        if len(matches)!=1:raise RuntimeError('Waiting for the active session container.')
        container=matches[0]
        if set(container['NetworkSettings']['Networks'])!={'vault_browsers'}:raise RuntimeError('Unexpected session network; scanner stopped.')
        inbox=ROOT/'inbox'
        if inbox.exists():shutil.rmtree(inbox)
        group=pwd.getpwnam('vault-scan').pw_gid
        inbox.mkdir(mode=0o750);os.chown(inbox,0,group);inbox.chmod(0o750)
        archive=ROOT/'snapshot.tar'
        try:
            download_snapshot(container['Id'],archive)
            records,incomplete=collect_files(archive,inbox,group)
        finally:archive.unlink(missing_ok=True)
        cache=load(CACHE,{})
        if cache.get('sessionId')!=state['id']:cache={}
        request=REQUEST.stat().st_mtime_ns if REQUEST.exists() else 0
        force=request!=cache.get('request',0)
        previous={r['name']:r for r in cache.get('files',[])}
        todo=[]
        for entry in records:
            old=previous.get(entry['name'],{})
            stable=entry['sha256'] and entry['sha256']==old.get('sha256')
            if stable and old.get('scannedAt') and not force and cache.get('definitionsAt')==report['engine']['definitionsAt']:
                entry.update(status=old['status'],scannedAt=old['scannedAt'],findings=old['findings'])
            elif stable or (force and entry['sha256']):todo.append(entry)
        wanted={entry['sha256'] for entry in todo}
        for file in inbox.iterdir():
            if file.name not in wanted:file.unlink()
        report.update(files=records,state='monitoring',message='Monitoring completed downloads. Files are checked after their contents stop changing.')
        if incomplete:report['message']='Only the first 100 files were inspected. Additional files were not scanned.'
        if todo:
            if not report['engine']['available']:
                report.update(state='unavailable',message='Antivirus definitions are not ready; only file-type warnings are available.')
            elif available_memory()<1700*1024**2:
                report.update(state='deferred',message='Antivirus scan is waiting for memory. A smaller session profile leaves more room for scanning.')
            else:
                report['state']='scanning';atomic(ROOT/'status.json',report,0o644)
                code,found=scan(inbox)
                for entry in todo:
                    signature=found.get(entry['sha256'])
                    if signature:entry.update(status='flagged',scannedAt=int(time.time()*1000),findings=entry['findings']+[signature])
                    elif code==0 or (code==1 and found):entry.update(status='no_detection',scannedAt=int(time.time()*1000))
                    else:entry.update(status='error',findings=entry['findings']+['Antivirus scan did not complete. This file has not been cleared.'])
                report['state']='monitoring' if code in (0,1) else 'error'
                report['message']='Scan completed. No detection is not a guarantee of safety.' if code in (0,1) else 'Some files could not be scanned; review their status below.'
        atomic(CACHE,dict(sessionId=state['id'],files=records,request=request,definitionsAt=report['engine']['definitionsAt']))
        shutil.rmtree(inbox)
    except Exception as error:
        report.update(state='error',message=str(error)[:350] if isinstance(error,RuntimeError) else 'The download monitor could not complete this check. Files may be unscanned.')
    finally:
        if (ROOT/'inbox').exists():shutil.rmtree(ROOT/'inbox')
        (ROOT/'snapshot.tar').unlink(missing_ok=True)
    report['checkedAt']=int(time.time()*1000)
    atomic(ROOT/'status.json',report,0o644)

if __name__=='__main__':main()
