"""Run inside the guest after installing the scanner. Uses harmless EICAR data."""
import hashlib,importlib.util,os,pathlib,pwd,shutil,tempfile,urllib.request
spec=importlib.util.spec_from_file_location('collector',pathlib.Path(__file__).parents[1]/'pi-admin/security_collector.py')
collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)
def main():
    root=pathlib.Path(tempfile.mkdtemp(prefix='av-check-',dir='/run/browser-vault-security'))
    try:
        group=pwd.getpwnam('vault-scan').pw_gid;os.chown(root,0,group);root.chmod(0o750)
        with urllib.request.urlopen('https://secure.eicar.org/eicar.com.txt',timeout=30) as response:sample=response.read(1024)
        assert len(sample)==68,'Unexpected test fixture'
        bad=hashlib.sha256(sample).hexdigest();good=hashlib.sha256(b'Harmless plain text notes.').hexdigest()
        for name,content in [(bad,sample),(good,b'Harmless plain text notes.')]:
            file=root/name;file.write_bytes(content);os.chown(file,0,group);file.chmod(0o440)
        code,found=collector.scan(root)
        assert code==1,(code,found)
        assert bad in found and 'eicar' in found[bad].lower(),found
        assert good not in found
        print('PASS real ClamAV detected harmless EICAR test data and did not flag plain notes.')
        print('PASS antivirus parser ran as vault-scan with no network, no capabilities, and resource limits.')
    finally:shutil.rmtree(root)

if __name__=='__main__':main()
