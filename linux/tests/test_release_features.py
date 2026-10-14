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

    def test_popup_origin_single_and_dual_monitor(self):
        area=(0,27,2560,1413)  # one 5K monitor at scale 2, top panel
        self.assertEqual(popup.popup_origin((2400,14),(352,376),area),(2202,33))  # clamped at right edge
        self.assertEqual(popup.popup_origin((1000,14),(352,376),area),(824,33))
        self.assertEqual(popup.popup_origin((10,1430),(352,376),area)[1],27+1413-376-6)  # bottom panel
        self.assertEqual(popup.popup_origin((3000,5),(352,376),(2560,0,2560,1440)),(2824,6))  # second monitor

    def test_tray_bars_follow_remaining_usage(self):
        import importlib.util, sys
        sys.modules['gi.repository'].Gio.Application=type('Application',(),{})  # gi is stubbed by the popup loader
        spec=importlib.util.spec_from_file_location('codexbar_tray',ROOT/'codexbar-tray.py')
        tray=importlib.util.module_from_spec(spec);spec.loader.exec_module(tray)
        self.assertEqual(tray.remaining({'primary':{'usedPercent':24}},'primary'),76)
        self.assertIsNone(tray.remaining({},'primary'))
        self.assertEqual(tray.tray_level({'primary':{'usedPercent':10},'secondary':{'usedPercent':30}}),70)  # tightest window
        self.assertEqual(tray.tray_level({'secondary':{'usedPercent':24}}),76)
        self.assertIsNone(tray.tray_level({}))
        svg=tray.tray_svg(100,50)
        self.assertIn('y="5.5" width="15.00"',svg)
        self.assertIn('y="15.5" width="7.50"',svg)
        self.assertNotIn('y="5.5"',tray.tray_svg(0,None))  # empty / unknown → outline only
        self.assertIn('width="3.00"',tray.tray_svg(1,None))  # never thinner than its rounded cap
        self.assertIn('opacity="0.55" x="4.5" y="5.5"',tray.tray_svg(50,50,(True,False)))  # stale codex dimmed
        self.assertNotIn('opacity',tray.tray_svg(50,50))
        self.assertIn('circle',tray.tray_svg(50,50,incident=True))

        events=lambda before,after:[t for t,_ in tray.quota_events(before,after)]
        self.assertEqual(events({('codex','weekly'):60},{('codex','weekly'):45}),['Codex weekly quota low'])
        self.assertEqual(events({('codex','weekly'):60},{('codex','weekly'):10}),['Codex weekly quota low'])  # one per jump
        self.assertEqual(events({('codex','weekly'):45},{('codex','weekly'):40}),[])  # already below
        self.assertEqual(events({('claude','session'):5},{('claude','session'):0}),['Claude session depleted'])
        self.assertEqual(events({('claude','session'):0},{('claude','session'):100}),['Claude session restored'])
        self.assertEqual(events({},{('claude','session'):0}),[])  # first sighting is the baseline
        self.assertEqual(events({('codex','session'):60},{('codex','session'):None}),[])

    def test_chinese_language(self):
        import codexbar_i18n
        self.assertEqual(codexbar_i18n.language({'language':'zh'}),'zh')
        with patch.dict(os.environ,{'LANGUAGE':'zh_CN:en'}):
            self.assertEqual(codexbar_i18n.language({}),'zh')
        self.assertEqual(codexbar_i18n.language({'language':'en'}),'en')
        with patch.object(codexbar_i18n,'language',lambda: 'zh'):
            self.assertEqual(codexbar_i18n.t('{pct}% remaining',pct='76'),'剩余 76%')
            self.assertEqual(popup.format_reset_label({'resetDescription':'Resets in 2h 18m'},'provider'),'重置：2h 18m后')
            self.assertEqual(codexbar_i18n.t('Not translated'),'Not translated')
        with patch.object(popup,'language',lambda: 'zh'),patch.object(codexbar_i18n,'language',lambda: 'zh'):
            label=popup.format_reset_label({'resetDescription':'Oct 20 at 12:58 AM','resetsAt':'2031-10-20T04:58:00Z'},'provider')
            self.assertTrue(label.startswith('重置：2031年10月20日'),label)
        self.assertEqual(popup.format_reset_label({'resetDescription':'Resets in 2h 18m'},'provider'),'Resets in 2h 18m')
        self.assertEqual(popup.format_reset_label({'resetDescription':'7:10 AM'},'provider'),'Resets 7:10 AM')

    def test_claude_auto_enabled_once_when_signed_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);config=root/'config.json';state=root/'state.json'
            (root/'.credentials.json').write_text('{}')
            config.write_text(json.dumps({'version':1,'providers':[{'id':'codex','enabled':True},{'id':'claude','enabled':False}]}))
            with patch.object(popup,'CONFIG_PATH',config),patch.object(popup,'STATE_PATH',state),patch.dict(os.environ,{'CLAUDE_CONFIG_DIR':tmp}):
                popup.enable_detected_claude()
                self.assertEqual([p['enabled'] for p in json.loads(config.read_text())['providers']],[True,True])
                popup.save_config({'claude':False})
                popup.enable_detected_claude()  # user turned it off: respect that
                self.assertFalse(json.loads(config.read_text())['providers'][1]['enabled'])

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
