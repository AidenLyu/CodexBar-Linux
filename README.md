# CodexBar Linux

**基于 [steipete/CodexBar](https://github.com/steipete/CodexBar) 的 Linux 原生桌面状态栏版本。**

A community Linux GTK3/GDK desktop frontend based on **steipete/CodexBar**, with the initial GUI and adapter derived from **Marouan-chak/codexbar-waybar**. Upstream code and licenses are retained. This is not an official upstream Linux GUI release.

![CodexBar Linux — synthetic demonstration data](linux/assets/linux-preview.png)

**[Download the Debian package](https://github.com/AidenLyu/CodexBar-Linux/releases/latest)** · **[Install / 中文说明](linux/README.md)** · **[Validation report](linux/VALIDATION.md)**

- Native persistent tray and popup, without Electron.
- Colored bars show **remaining** quota; white shows consumed quota.
- Background refresh, provider settings, credits and expandable usage details.
- Debian amd64 package with a verified upstream CLI and bundled assets.
- Validated on Ubuntu 22.04 GNOME X11. Native Wayland is not supported in 1.0.

```sh
sudo apt install ./codexbar-linux_1.0.1_amd64.deb
codexbar-linux
```

The Linux implementation, tests and build scripts are in [`linux/`](linux/). The original macOS/CLI project remains in this fork; its documentation is preserved in [README.upstream.md](README.upstream.md).

## Credits

[steipete/CodexBar](https://github.com/steipete/CodexBar) — original application, CLI and icons, MIT.

[Marouan-chak/codexbar-waybar](https://github.com/Marouan-chak/codexbar-waybar) — initial GTK frontend and shell adapter, MIT.

Linux native adaptation and packaging by Aiden Lyu. This fork preserves the upstream licenses and does not imply upstream endorsement.
