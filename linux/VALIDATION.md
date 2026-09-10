# Release 1.0.0 validation

Target: Ubuntu 22.04 amd64, GNOME 42, X11, GTK 3.24; two monitors at 2x scaling. CLI: official static-musl CodexBar 0.58.0. Native tests also run in isolated Xvfb/Openbox sessions with private temporary configuration and D-Bus; they do not access developer credentials.

| Area | Verification |
|---|---|
| Quota semantics | Actual GTK level-bar values checked for 0%, 89%, 100% used; invalid/unknown values and clamping tested |
| Open/close | Eight repeated native cycles with stable full allocations; Escape and outside dismissal exercised on desktop |
| Usage details | Actual XTest pointer clicks expand and collapse; expansion survives re-render |
| Long content | 35 extra quota rows scroll; settings/back remain usable |
| Provider selection | Six unit tests for configured, unavailable, unhealthy and highest-usage choices |
| Settings | Save preserves credential/options fields; disabled-all stays disabled; files are atomically written with mode 0600 |
| Preferences | Tray provider, popup provider, and UTC reset mode persisted; unsaved provider toggles survive preference changes |
| Refresh | Slow fixture refresh runs in a worker while GLib timers continue; concurrent refresh requests coalesce |
| Offline state | Successful cache → provider failure → stale snapshot → recovery tested; stale/error state reaches GUI cache |
| Lifecycle | Tray startup, popup startup, remote open, single instance, explicit Quit and child-process cleanup tested |
| About | Correct public-repository URL emitted through xdg-open, and popup dismissed first |
| Distribution | Pinned upstream CLI SHA-256, Debian control/dependencies/conffiles, desktop launcher, user service, icons and licenses included |
| Public screenshot | Synthetic demo@example.com account and fictional figures; no real usage or credentials |

Commands:

```sh
/usr/bin/python3 -m unittest discover -s tests -v   # 10 tests
bash tests/run_native.sh                         # four native test programs
shellcheck -S warning codexbar.sh codexbar-popup-launch.sh packaging/codexbar-linux tests/*.sh
/usr/bin/python3 packaging/build_deb.py
lintian dist/codexbar-linux_1.0.0_amd64.deb
```

The official CLI is distributed byte-for-byte from its verified archive. Lintian exceptions for its static linking, embedded curl/zlib and upstream debug symbols are explicitly documented in `packaging/lintian-overrides`; they are distribution choices, not claimed fixes to upstream binaries.

## Limits

- Codex usage is the only provider tested against an authenticated real account. Generic provider rendering, selection and error paths use fixtures. No claim is made that every upstream provider login/cookie integration works on Linux.
- Native Wayland, ARM, other distributions and desktop shells have not been validated for this release.
- The unmodified upstream macOS project remains in the fork. Its root `make check` was attempted but requires unavailable macOS `plutil`; root `make test` was attempted but no Swift toolchain is installed. Those are not successful upstream test runs. The Python/GTK Linux frontend and packaged official CLI are validated separately above.
