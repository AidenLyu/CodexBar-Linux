#!/usr/bin/python3
"""Single-instance native X11 tray host for CodexBar Linux."""
import os
import signal
import subprocess
import sys
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio, GLib, GdkPixbuf
from codexbar_paths import ROOT, CACHE, STATE_PATH, read_json
from codexbar_i18n import t

VERSION = '1.0.3'


def remaining(usage, key):
    pct = (usage.get(key) or {}).get('usedPercent')
    if isinstance(pct, (int, float)) and not isinstance(pct, bool) and pct == pct:
        return 100 - min(100, max(0, pct))
    return None


def tray_level(usage):
    """Remaining % of whichever window runs out first, or None."""
    levels = [v for v in (remaining(usage, 'primary'), remaining(usage, 'secondary')) if v is not None]
    return min(levels) if levels else None


def tray_svg(codex, claude, dim=(False, False), incident=False):
    """Two battery-style bars (Codex on top, Claude below) filled by remaining %.

    Like the macOS icon, a bar showing cached (stale) data is dimmed, and a
    provider status incident adds a red dot.
    """
    def fill(y, pct, faded):
        if pct is None or pct <= 0:
            return ''
        opacity = ' opacity="0.55"' if faded else ''
        return (f'<rect fill="#eee"{opacity} x="4.5" y="{y}" width="{max(3, 15 * min(pct, 100) / 100):.2f}"'
                ' height="3" rx="1.5"/>')
    dot = '<circle fill="#ff453a" cx="21" cy="3" r="3"/>' if incident else ''
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
            '<g stroke="#eee" stroke-width="1.5" fill="none"><rect x="3" y="4" width="18" height="6" rx="3"/>'
            '<rect x="3" y="14" width="18" height="6" rx="3"/></g>'
            + fill(5.5, codex, dim[0]) + fill(15.5, claude, dim[1]) + dot + '</svg>')


def quota_events(before, after, thresholds=(50, 20)):
    """Notifications for remaining-% changes, keyed by (provider, window).

    Mirrors the macOS defaults: warn when crossing 50% / 20% left, and say when
    the session runs out or comes back. Unknown before/after values never fire.
    """
    events = []
    for (provider, window), now in after.items():
        was = before.get((provider, window))
        if was is None or now is None:
            continue
        name = provider.title()
        if window == 'session' and was > 0 >= now:
            events.append((t('{name} session depleted', name=name), t("0% left. Will notify when it's available again.")))
        elif window == 'session' and was <= 0 < now:
            events.append((t('{name} session restored', name=name), t('Session quota is available again.')))
        else:
            crossed = [t for t in thresholds if was > t >= now]
            if crossed:
                events.append((t('{name} {window} quota low', name=name, window=t(window)),
                               t('{pct}% left. Below your {limit}% warning.', pct=f'{now:g}', limit=min(crossed))))
    return events


def notify(title, body):
    Gio.bus_get_sync(Gio.BusType.SESSION, None).call(
        'org.freedesktop.Notifications', '/org/freedesktop/Notifications', 'org.freedesktop.Notifications',
        'Notify', GLib.Variant('(susssasa{sv}i)', ('CodexBar', 0, str(ROOT / 'codexbar-tray.svg'), title, body, [], {}, -1)),
        None, Gio.DBusCallFlags.NONE, -1, None, None, None)


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
        self.shown = self.target = (None, None)
        self.tween = None
        self.marks = ((False, False), False)  # (dimmed bars, incident)
        self.levels = None  # first read is the notification baseline
        self.icon = Gtk.StatusIcon.new_from_file(str(ROOT / 'codexbar-tray.svg'))
        self.icon.set_title('CodexBar Linux')
        self.icon.set_name('codexbar-linux')
        self.icon.connect('activate', self.toggle)
        self.icon.connect('popup-menu', self.menu)
        self.icon.set_visible(True)
        self.icon.connect('notify::embedded', lambda *_: print('Tray embedded:', self.icon.is_embedded(), flush=True))
        self.icon.connect('size-changed', lambda *_: self.draw() or False)
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
            item = Gtk.MenuItem(label=t(title))
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
        state = read_json(STATE_PATH, dict, {})
        selected = state.get('barProvider')
        lines = [t('CodexBar Linux · Click to view usage')]
        left, stale, levels, incident = {}, {}, {}, False
        for entry in data:
            if not isinstance(entry, dict):
                continue
            usage = entry.get('usage') or {}
            label = entry.get('provider', 'Unknown')
            left[label], stale[label] = tray_level(usage), bool(entry.get('stale'))
            levels[(label, 'session')], levels[(label, 'weekly')] = remaining(usage, 'primary'), remaining(usage, 'secondary')
            status = entry.get('status') if isinstance(entry.get('status'), dict) else {}
            incident = incident or status.get('indicator') not in (None, 'none')
            if selected and label != selected:
                continue
            values = [f"{t(name)}: {t('{pct}% remaining', pct=f'{pct:g}')}" for key, name in [('primary', 'Session'), ('secondary', 'Weekly')]
                      if (pct := remaining(usage, key)) is not None]
            suffix = ' · ' + t('cached') if entry.get('stale') else ''
            if status.get('indicator') not in (None, 'none'):
                suffix += f" · {status.get('description') or t('service issue')}"
            lines.append(f'{label}: ' + (' · '.join(values) or t('Usage unavailable')) + suffix)
        self.icon.set_tooltip_text('\n'.join(lines))
        if self.levels is not None and state.get('notifications', True):
            for title, body in quota_events(self.levels, levels):
                notify(title, body)
        self.levels = levels
        marks = ((stale.get('codex', False), stale.get('claude', False)), incident)
        if marks != self.marks:
            self.marks = marks
            self.draw()
        self.animate_to((left.get('codex'), left.get('claude')))
        return True

    def animate_to(self, target):
        if target == self.target:
            return
        start, self.target, step = self.shown, target, [0]
        if self.tween:
            GLib.source_remove(self.tween)
        def tick():
            step[0] += 1
            t = step[0] / 20
            self.shown = tuple(b if a is None or b is None else a + (b - a) * t for a, b in zip(start, target))
            self.draw()
            if step[0] < 20:
                return True
            self.tween = None
            return False
        self.tween = GLib.timeout_add(30, tick)  # ~600ms ease from old to new level

    def draw(self):
        size = max(16, self.icon.get_size())
        loader = GdkPixbuf.PixbufLoader()
        loader.set_size(size, size)
        loader.write(tray_svg(*self.shown, *self.marks).encode())
        loader.close()
        self.icon.set_from_pixbuf(loader.get_pixbuf())


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
