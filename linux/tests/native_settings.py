import importlib.util
import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('popup',ROOT/'codexbar-popup.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
with tempfile.TemporaryDirectory() as tmp:
    m.CONFIG_PATH=Path(tmp)/'config.json';m.STATE_PATH=Path(tmp)/'state.json'
    m.CONFIG_PATH.write_text(json.dumps({'version':1,'providers':[{'id':'codex','enabled':True,'apiKey':'FAKE-KEY'}]}))
    m.load_cached=lambda:[{'provider':'codex','usage':{'primary':{'usedPercent':24}}}]
    original=m.CodexBarPopup.refresh
    m.CodexBarPopup.refresh=lambda *a,**k:None
    app=m.CodexBarPopup();app.set_application_id('dev.codexbar.settings.test');app.register(None);app.anchor=(700,28);app.do_activate()
    app._on_settings_call()
    app.settings_switches['codex'].set_active(False)
    app._on_reset_format_change('utc')
    assert not app.settings_switches['codex'].get_active(),'Changing format discarded an unsaved toggle'
    app._on_settings_save()
    result=json.loads(m.CONFIG_PATH.read_text())
    provider=next(p for p in result['providers'] if p['id']=='codex')
    assert not provider['enabled'] and provider['apiKey']=='FAKE-KEY'
    assert m.load_state()['resetTimeFormat']=='utc'
    app._on_bar_provider_change('codex');assert m.load_state()['barProvider']=='codex'
    app._on_popup_provider_change('codex');assert m.load_state()['popupProvider']=='codex'
    app.data=[{'provider':'codex','account':f'Account {i}','usage':{'primary':{'usedPercent':i}}} for i in range(8)]
    app.active_pid=m.entry_key(app.data[0]);app.render()
    app._select(m.entry_key(app.data[-1]));assert app.active_pid==m.entry_key(app.data[-1])
    deadline=time.monotonic()+.1
    while time.monotonic()<deadline:
        while m.GLib.MainContext.default().pending():m.GLib.MainContext.default().iteration(False)
        time.sleep(.001)
    assert app.tab_scroll.get_hadjustment().get_upper() > app.tab_scroll.get_hadjustment().get_page_size()
    assert app.window.get_size().width < 600
    with patch.object(m.subprocess,'Popen') as opened:
        app._on_about_call()
        assert opened.call_args.args[0]==['xdg-open','https://github.com/AidenLyu/CodexBar-Linux']
        assert not app.window.get_visible()
    # Exercise a slow refresh with real GLib dispatch; repeated clicks coalesce.
    app.refreshing=False
    calls=[]
    def fetch():
        calls.append(1);time.sleep(.15);return m.load_cached()
    m.fetch_fresh=fetch
    m.CodexBarPopup.refresh=original
    app.refresh(background=True);app.refresh(background=True)
    ticks=[]
    m.GLib.timeout_add(10,lambda: ticks.append(1) or len(ticks)<8)
    until=time.monotonic()+.3
    while time.monotonic()<until:
        while m.GLib.MainContext.default().pending():m.GLib.MainContext.default().iteration(False)
        time.sleep(.001)
    assert len(calls)==1 and len(ticks)>=5 and not app.refreshing
    print('PASS: multi-account tabs, settings save/format/provider preferences, credential preservation, About action, nonblocking/coalesced refresh')
