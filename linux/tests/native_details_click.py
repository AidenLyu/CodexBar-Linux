import importlib.util,time,ctypes
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
spec=importlib.util.spec_from_file_location('popup',Path(__file__).resolve().parents[1]/'codexbar-popup.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.load_cached=lambda:[{'provider':'codex','usage':{'primary':{'usedPercent':89}}}]
m.summarize_pace=lambda e:['First detail line','Second detail line']
m.CodexBarPopup.refresh=lambda *a,**k:None
app=m.CodexBarPopup();app.set_application_id('dev.codexbar.details.test');app.register(None);app.anchor=(2354,27);app.do_activate()
def pump():
 end=time.monotonic()+.25
 while time.monotonic()<end:
  while m.GLib.MainContext.default().pending():m.GLib.MainContext.default().iteration(False)
  time.sleep(.001)
pump()
e=next(c for c in app.body.get_children() if isinstance(c,m.Gtk.Expander))
x,y=e.translate_coordinates(app.window,30,12);wx,wy=app.window.get_position();scale=app.window.get_scale_factor()
xlib=ctypes.CDLL('libX11.so.6');xt=ctypes.CDLL('libXtst.so.6');xlib.XOpenDisplay.restype=ctypes.c_void_p;xlib.XFlush.argtypes=[ctypes.c_void_p]
xt.XTestFakeMotionEvent.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_ulong];xt.XTestFakeButtonEvent.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_int,ctypes.c_ulong]
d=xlib.XOpenDisplay(None)
xt.XTestFakeMotionEvent(d,0,(wx+x)*scale,(wy+y)*scale,0);xt.XTestFakeButtonEvent(d,1,1,0);xt.XTestFakeButtonEvent(d,1,0,0);xlib.XFlush(d)
pump()
assert e.get_expanded(), "Actual pointer click did not expand details"
assert e.get_allocation().height > 26
app.render();pump()
e=next(c for c in app.body.get_children() if isinstance(c,m.Gtk.Expander))
assert e.get_expanded(), "Re-render lost expanded state"
x,y=e.translate_coordinates(app.window,30,12);wx,wy=app.window.get_position()
xt.XTestFakeMotionEvent(d,0,(wx+x)*scale,(wy+y)*scale,0)
xt.XTestFakeButtonEvent(d,1,1,0);xt.XTestFakeButtonEvent(d,1,0,0);xlib.XFlush(d)
pump()
assert not e.get_expanded(), "Actual second click did not collapse details"
app.hide_window()
print("PASS: real pointer expand, state retained on render, real pointer collapse")
