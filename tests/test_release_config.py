import importlib.util
import json
import pathlib
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('release_config', pathlib.Path(__file__).resolve().parents[1]/'pi-admin/release_config.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.settings={'launcherOrigin':'https://vault.test.net','displayOrigin':'https://view.test.net','cloudflareAccess':{'issuer':'https://test.cloudflareaccess.com','audience':'a'*64,'email':'owner@test.net'},'privateProbeAddresses':['192.168.1.10','192.168.1.20','192.168.1.1']}

    def load(self):
        with tempfile.TemporaryDirectory() as directory:
            p=pathlib.Path(directory)/'settings.json'
            p.write_text(json.dumps(self.settings))
            return module.load(p)

    def test_valid(self):
        self.assertEqual(self.load()['displayHost'],'view.test.net')

    def test_invalid_origins(self):
        for value in ['http://view.test.net','https://view.test.net/a','https://user@view.test.net','https://view.test.net:444','https://view.example.com','https://view.test.net\nDNS:bad']:
            with self.subTest(value=value):
                self.settings['displayOrigin']=value
                with self.assertRaises(ValueError): self.load()

    def test_placeholders(self):
        self.settings['cloudflareAccess']['audience']='REPLACE_ME'
        with self.assertRaises(ValueError): self.load()

    def test_public_probe_rejected(self):
        self.settings['privateProbeAddresses'][0]='1.1.1.1'
        with self.assertRaises(ValueError): self.load()

if __name__=='__main__': unittest.main()
