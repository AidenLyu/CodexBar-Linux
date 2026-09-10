import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from test_popup_provider_selection import popup

ROOT = Path(__file__).resolve().parents[1]

class ReleaseFeatures(unittest.TestCase):
    def test_remaining_boundaries_and_unknown(self):
        for used, remaining in [(0,100),(89,11),(100,0),(120,0),(-1,100),(None,None),(True,None),(float('nan'),None)]:
            self.assertEqual(popup.remaining_percent(used),remaining)

    def test_save_preserves_options_and_all_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'config.json'
            config={'version':1,'futureOption':{'keep':True},'providers':[{'id':'codex','enabled':True,'apiKey':'FAKE-TEST-KEY','options':{'keep':7}}]}
            path.write_text(json.dumps(config))
            with patch.object(popup,'CONFIG_PATH',path):
                popup.save_config({'codex':False,'claude':False})
                result=json.loads(path.read_text())
            self.assertFalse(result['providers'][0]['enabled'])
            self.assertEqual(result['providers'][0]['apiKey'],'FAKE-TEST-KEY')
            self.assertEqual(result['providers'][0]['options'],{'keep':7})
            self.assertEqual(result['futureOption'],{'keep':True})
            self.assertEqual(path.stat().st_mode & 0o777,0o600)

    def test_corrupt_cache_is_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'last.json'
            with patch.object(popup,'LAST_GOOD',path):
                for content in ['{bad','{}','null','[{},2]']:
                    path.write_text(content)
                    self.assertIsInstance(popup.load_cached(),list)

    def test_backend_success_failure_recovery_disable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);config=root/'config.json';fixture=root/'fixture.json'
            fake=root/'fake-cli'
            fake.write_text('#!/usr/bin/python3\nimport os\nfrom pathlib import Path\nprint(Path(os.environ["TEST_FIXTURE"]).read_text())\n')
            fake.chmod(0o755)
            env=dict(os.environ,HOME=tmp,XDG_CACHE_HOME=str(root/'cache'),XDG_CONFIG_HOME=str(root/'config'),CODEXBAR_CONFIG=str(config),CODEXBAR_BIN=str(fake),TEST_FIXTURE=str(fixture),CODEXBAR_STAGGER='0')
            env.pop('CODEXBAR_PROVIDERS',None)
            def run(payload):
                fixture.write_text(json.dumps(payload))
                proc=subprocess.run(['bash',str(ROOT/'codexbar.sh')],env=env,capture_output=True,text=True,timeout=15)
                self.assertEqual(proc.returncode,0,proc.stderr)
                json.loads(proc.stdout)
                return json.loads((root/'cache/codexbar-waybar/last.json').read_text())
            config.write_text(json.dumps({'version':1,'providers':[{'id':'codex','enabled':True}]}))
            healthy=[{'provider':'codex','usage':{'primary':{'usedPercent':89}}}]
            self.assertEqual(run(healthy)[0]['usage']['primary']['usedPercent'],89)
            stale=run([{'provider':'codex','error':{'message':'offline'}}])
            self.assertTrue(stale[0]['stale'])
            self.assertEqual(stale[0]['usage']['primary']['usedPercent'],89)
            self.assertNotIn('stale',run(healthy)[0])
            config.write_text(json.dumps({'version':1,'providers':[{'id':'codex','enabled':False}]}))
            self.assertEqual(run(healthy),[])

if __name__=='__main__':unittest.main()
