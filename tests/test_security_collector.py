import importlib.util,io,os,pathlib,tarfile,tempfile,unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('collector',pathlib.Path(__file__).parents[1]/'pi-admin/security_collector.py')
collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)

class CollectorTests(unittest.TestCase):
    def test_untrusted_archive_paths_never_become_extracted_paths(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(collector.os,'chown'):
            root=pathlib.Path(temporary);archive=root/'downloads.tar';inbox=root/'inbox';inbox.mkdir()
            with tarfile.open(archive,'w') as tar:
                for name,content in [('Downloads/report.pdf.exe',b'MZ harmless test'),('../../escape',b'ordinary text'),('unfinished.part',b'partial')]:
                    info=tarfile.TarInfo(name);info.size=len(content);tar.addfile(info,io.BytesIO(content))
                link=tarfile.TarInfo('private-link');link.type=tarfile.SYMTYPE;link.linkname='/etc/passwd';tar.addfile(link)
            records,incomplete=collector.collect_files(archive,inbox,os.getgid())
            self.assertFalse(incomplete);self.assertEqual(len(records),4)
            self.assertTrue(all(len(p.name)==64 and p.is_file() for p in inbox.iterdir()))
            self.assertFalse((root/'escape').exists())
            self.assertTrue(records[0]['findings']);self.assertEqual(records[2]['status'],'pending')
            self.assertIsNone(records[3]['sha256']);self.assertEqual(records[3]['status'],'not_scanned')

    def test_enforced_file_size_and_limit_results_are_not_clean(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(collector.os,'chown'):
            root=pathlib.Path(temporary);inbox=root/'inbox';inbox.mkdir();archive=root/'data.tar'
            with tarfile.open(archive,'w') as tar:
                info=tarfile.TarInfo('large.zip');info.size=10;tar.addfile(info,io.BytesIO(b'1234567890'))
            with patch.object(collector,'MAX_FILE',4):records,_=collector.collect_files(archive,inbox,os.getgid())
            self.assertEqual(records[0]['status'],'not_scanned');self.assertFalse(list(inbox.iterdir()))

    def test_metadata_warnings_and_scan_errors(self):
        self.assertTrue(collector.file_warnings('notes.pdf',b'\x7fELF'))
        self.assertTrue(collector.file_warnings('notes\u202eexe.pdf',b'text'))
        self.assertFalse(collector.file_warnings('notes.txt',b'plain notes'))
        result=type('Result',(),{'returncode':1,'stdout':'/inbox/'+'a'*64+': Eicar-Test-Signature FOUND\nERROR: another file failed','stderr':''})()
        with patch.object(collector.subprocess,'run',return_value=result):code,found=collector.scan(pathlib.Path('/inbox'))
        self.assertEqual(code,2);self.assertIn('a'*64,found)

if __name__=='__main__':unittest.main(verbosity=2)
