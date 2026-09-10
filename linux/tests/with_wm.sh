#!/usr/bin/env bash
set -euo pipefail
openbox > /dev/null 2>&1 &
wm_pid=$!
trap 'kill "$wm_pid" 2>/dev/null || true' EXIT
# Wait for the window manager to initialize before creating any popup.
for _attempt in {1..50}; do
    if xprop -root _NET_SUPPORTING_WM_CHECK 2>/dev/null | grep -q 'window id'; then break; fi
    sleep 0.02
done
"$@"
