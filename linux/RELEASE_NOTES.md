# CodexBar Linux 1.0.0

Native GTK3/GDK Linux desktop adaptation of **steipete/CodexBar**, with the initial frontend/adapter based on **Marouan-chak/codexbar-waybar**. Both upstream projects and licenses are credited. This is a community port, not an official upstream Linux GUI release.

## Download and install

Supported and validated: **Ubuntu 22.04 GNOME X11/Xorg, amd64**.

Download the `.deb` and `SHA256SUMS` into one directory:

```sh
sha256sum -c SHA256SUMS
sudo apt install ./codexbar-linux_1.0.0_amd64.deb
codexbar-linux
```

The package bundles the SHA-256-verified official **CodexBar CLI 0.58.0 static Linux build**, provider assets and Inter font. Authenticate your own providers separately. No developer credentials, account cache or real-account screenshots are included.

## Highlights

- Persistent native tray and full-size popup with stable high-DPI input coordinates.
- Colored progress = **remaining quota**; white = consumed quota.
- Background/coalesced refresh, stale-cache recovery and explicit errors.
- Provider/account tabs, reset formatting, preserved configuration fields and private atomic settings writes.
- Working Usage details expand/collapse that survives refresh; long content scrolls.
- Desktop launcher, login autostart, optional user service and clean Quit.

## Validation before publication

- 10 unit/backend tests passed.
- Four native Xvfb/Openbox test programs passed: repeated open/close, real pointer clicks, details persistence, scrolling, multiple accounts, settings save, About action, responsive refresh, singleton lifecycle and child cleanup.
- Python compilation and ShellCheck passed.
- Debian package installed on the target desktop; runtime files match release source; `dpkg --verify` passed.
- Packaged tray embedding and real Codex usage confirmed on GNOME X11.
- Lintian has no unhandled diagnostics. Four documented overrides retain the official CLI unchanged (static binary, embedded curl/zlib, upstream debug symbols).

Native Wayland/ARM/other desktops are not validated. Codex is the only provider authenticated for live testing; other provider login flows are not claimed as tested. Original macOS `make check`/`make test` could not run here because macOS `plutil` and the Swift toolchain are unavailable; see `linux/VALIDATION.md`.

## 中文

这是基于原版 CodexBar 的 Linux 原生状态栏版本，并注明 codexbar-waybar 界面代码来源。安装包已在 Ubuntu GNOME X11 上安装实测，包含官方固定版本 CLI，无需 Conda。彩色表示剩余、白色表示已用；明细点击、设置保存、后台刷新和退出均已测试。

请注意：本次验证了真实 Codex 账号；其他提供商需要自行登录，不能将本次发布理解为所有提供商都已完成真实账号验证。Wayland 和 ARM 暂不支持。
