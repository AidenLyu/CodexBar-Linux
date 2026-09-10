#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
test_home="$(mktemp -d)"
trap 'rm -rf "$test_home"' EXIT
for test in native_popup_smoke.py native_details_click.py native_lifecycle.py native_settings.py; do
    HOME="$test_home" XDG_CONFIG_HOME="$test_home/config" XDG_CACHE_HOME="$test_home/cache" \
      XDG_SESSION_TYPE=x11 GDK_SCALE=2 GTK_USE_PORTAL=0 NO_AT_BRIDGE=1 dbus-run-session --config-file tests/dbus.conf -- \
      xvfb-run -a -s '-screen 0 5120x2880x24' tests/with_wm.sh /usr/bin/python3 "tests/$test"
done
