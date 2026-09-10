"""Render public documentation using only synthetic data, on an isolated display."""
import importlib.util
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('popup',ROOT/'codexbar-popup.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
sample=[{'provider':'codex','usage':{'identity':{'accountEmail':'demo@example.com','loginMethod':'Pro'},'primary':{'usedPercent':24,'resetDescription':'Resets in 2h 18m'},'secondary':{'usedPercent':61,'resetDescription':'Resets in 3d 4h'}},'credits':{'remaining':42.50}}]
m.load_cached=lambda:sample
m.summarize_pace=lambda _:['Synthetic demonstration data — no real account shown.']
m.CodexBarPopup.refresh=lambda *a,**k:None
app=m.CodexBarPopup();app.set_application_id('dev.codexbar.linux.preview');app.register(None);app.anchor=(700,30);app.do_activate()
until=time.monotonic()+.3
while time.monotonic()<until:
    while m.GLib.MainContext.default().pending():m.GLib.MainContext.default().iteration(False)
    time.sleep(.001)
w,h=app.window.get_size()
m.Gdk.pixbuf_get_from_window(m.Gdk.get_default_root_window(),*app.window.get_position(),w,h).savev(str(ROOT/'assets/linux-preview.png'),'png',[],[])
app.hide_window()
