#!/usr/bin/python3
"""Single-instance native X11 tray host for CodexBar Linux."""
import os
import signal
import subprocess
import sys
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio, GLib
from codexbar_paths import ROOT, CACHE, STATE_PATH, read_json

VERSION = '1.0.2'

class Tray(Gio.Application):
    def __init__(self):
        super().__init__(application_id='dev.codexbar.linux.tray', flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)

    def do_startup(self):
        Gio.Application.do_startup(self)
        self.hold()
        self.popup = None
        self.ready = False
        self.pending_anchor = None
        for name, callback in [('quit', self.exit_all), ('toggle', self.toggle)]:
            action = Gio.SimpleAction.new(name, None)
            action.connect('activate', callback)
            self.add_action(action)
        self.actions = Gio.DBusActionGroup.get(Gio.bus_get_sync(Gio.BusType.SESSION, None),
            'dev.codexbar.linux.popup', '/dev/codexbar/linux/popup')
        self.actions.connect('action-added', self.action_added)
        self.actions.list_actions()
        self.ensure_popup()
        self.icon = Gtk.StatusIcon.new_from_file(str(ROOT / 'codexbar-tray.svg'))
        self.icon.set_title('CodexBar Linux')
        self.icon.set_name('codexbar-linux')
        self.icon.connect('activate', self.toggle)
        self.icon.connect('popup-menu', self.menu)
        self.icon.set_visible(True)
        self.icon.connect('notify::embedded', lambda *_: print('Tray embedded:', self.icon.is_embedded(), flush=True))
        self.update()
        GLib.timeout_add_seconds(15, self.update)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self.exit_all)

    def do_command_line(self, command_line):
        args = command_line.get_arguments()[1:]
        if '--quit' in args:
            self.exit_all()
        elif '--popup' in args:
            self.toggle()
        return 0

    def action_added(self, _group, name):
        if name == 'toggle' and self.pending_anchor is not None:
            anchor, self.pending_anchor = self.pending_anchor, None
            self.actions.activate_action('toggle', GLib.Variant('(ii)', anchor))

    def ensure_popup(self):
        if self.popup is None or self.popup.poll() is not None:
            self.popup = subprocess.Popen([sys.executable, str(ROOT / 'codexbar-popup.py'), '--background'])

    def toggle(self, *_):
        self.ensure_popup()
        # StatusIcon.get_geometry() reports the XEmbed socket inside gnome-shell,
        # which is often stale/offscreen (popup jumped around on single-monitor
        # setups). The pointer is on the icon when it is clicked, so use that.
        _screen, x, y = self.icon.get_screen().get_display().get_default_seat().get_pointer().get_position()
        anchor = (x, y)
        if self.actions.has_action('toggle'):
            self.actions.activate_action('toggle', GLib.Variant('(ii)', anchor))
        else:
            self.pending_anchor = anchor

    def menu(self, icon, button, timestamp):
        self.context = Gtk.Menu()
        for title, callback in [('Show usage', self.toggle), ('Quit CodexBar', self.exit_all)]:
            item = Gtk.MenuItem(label=title)
            item.connect('activate', callback)
            self.context.append(item)
        self.context.show_all()
        self.context.popup(None, None, Gtk.StatusIcon.position_menu, icon, button, timestamp)

    def exit_all(self, *_):
        self.actions.activate_action('quit', None)
        self.icon.set_visible(False)
        self.quit()
        return False

    def do_shutdown(self):
        if self.popup and self.popup.poll() is None:
            self.popup.terminate()
            try:
                self.popup.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.popup.kill()
                self.popup.wait()
        Gio.Application.do_shutdown(self)

    def update(self):
        self.ensure_popup()
        data = read_json(CACHE / 'last.json', list, [])
        selected = read_json(STATE_PATH, dict, {}).get('barProvider')
        lines = ['CodexBar Linux · Click to view usage']
        for entry in data:
            if not isinstance(entry, dict) or selected and entry.get('provider') != selected:
                continue
            usage = entry.get('usage') or {}
            values = []
            for key, name in [('primary', 'Session'), ('secondary', 'Weekly')]:
                pct = (usage.get(key) or {}).get('usedPercent')
                if isinstance(pct, (int, float)) and not isinstance(pct, bool):
                    values.append(f'{name}: {100-min(100,max(0,pct)):g}% remaining')
            label = entry.get('provider', 'Unknown')
            suffix = ' · cached' if entry.get('stale') else ''
            lines.append(f'{label}: ' + (' · '.join(values) or 'Usage unavailable') + suffix)
        self.icon.set_tooltip_text('\n'.join(lines))
        return True


def main():
    if '--version' in sys.argv:
        print('CodexBar Linux ' + VERSION)
        return 0
    if os.environ.get('XDG_SESSION_TYPE') == 'wayland':
        print('CodexBar Linux 1.0 requires an X11 desktop session. Select Ubuntu on Xorg at login.', file=sys.stderr)
        return 1
    if not Gtk.init_check()[0]:
        print('No graphical display available.', file=sys.stderr)
        return 1
    return Tray().run(sys.argv)

if __name__ == '__main__':
    sys.exit(main())
