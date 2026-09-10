"""Exercise real GTK allocation and quota semantics under the current desktop."""
import importlib.util
import time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
spec = importlib.util.spec_from_file_location('native_popup', Path(__file__).resolve().parents[1] / 'codexbar-popup.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
for used, expected in [(0,100),(89,11),(100,0),(120,0),(-20,100),(None,None),(float('nan'),None)]:
    assert m.remaining_percent(used) == expected
sample = [{'provider':'codex','usage':{'primary':{'usedPercent':89},'secondary':{'usedPercent':100}}}]
m.load_cached = lambda: sample
m.CodexBarPopup.refresh = lambda *a, **k: None
app = m.CodexBarPopup()
app.set_application_id('dev.codexbar.linux.smoke')
app.register(None)
app.anchor = (2354,27)

def pump():
    until = time.monotonic() + .04
    while time.monotonic() < until:
        while m.GLib.MainContext.default().pending():
            m.GLib.MainContext.default().iteration(False)
        time.sleep(.001)

measurements = []
for _ in range(8):
    start = time.monotonic()
    app.do_activate()
    pump()
    width,height = app.window.get_size()
    assert width >= 310 and height > 200, (width,height)
    assert app.window.get_opacity() == 1
    measurements.append((width,height,round((time.monotonic()-start)*1000)))
    app.hide_window()
    pump()
assert len({(w,h) for w,h,_ in measurements}) == 1, measurements
for used, expected in [(0,100),(89,11),(100,0)]:
    section = app._section('Quota', {'usedPercent':used})
    bar = next(c for c in section.get_children() if isinstance(c,m.Gtk.LevelBar))
    assert bar.get_value() == expected
app.data[0]['usage']['extraRateWindows'] = [{'title':f'Quota {i}', 'window':{'usedPercent':i}} for i in range(35)]
app.render()
app.do_activate()
pump()
adj = app.content_scroll.get_vadjustment()
assert adj.get_upper() > adj.get_page_size(), (adj.get_upper(),adj.get_page_size())
adj.set_value(adj.get_upper() - adj.get_page_size())
pump()
assert adj.get_value() > 0
app.view = 'settings'
app.render()
pump()
app.view = 'usage'
app.render()
pump()
app.hide_window()
print('PASS: 8 stable native open/hide cycles; quota fill 0/11/100%; long content scroll; settings/back.')
print('Sizes and open-to-measure times (includes 40ms event drain):', measurements)
