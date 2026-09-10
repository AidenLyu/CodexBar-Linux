# Native GNOME tray

See [README.md](README.md) for installation, controls, configuration, upstream attribution and supported desktops, and [VALIDATION.md](VALIDATION.md) for the release test matrix.

The native window is an undecorated GTK3 TOPLEVEL with a POPUP_MENU hint; this avoids the HiDPI input-coordinate mismatch observed with GTK_WINDOW_POPUP. GDK positions it before mapping; there is no opacity polling or delayed Xlib movement.
