#!/usr/bin/env bash
# Launcher for the Crossroads Simulator GUI.
# Works without sudo by using a locally extracted libxcb-cursor0.
# If libxcb-cursor0 is ever installed system-wide (sudo apt install libxcb-cursor0)
# this LD_LIBRARY_PATH prefix becomes a no-op and can be removed.

set -e
cd "$(dirname "$0")"

XCB_LIB=/tmp/xcb-cursor-lib/usr/lib/x86_64-linux-gnu

# Re-extract the library if /tmp was cleared since last run
if [ ! -f "$XCB_LIB/libxcb-cursor.so.0" ]; then
    echo "Re-extracting libxcb-cursor0 to /tmp ..."
    apt-get download libxcb-cursor0 -o Dir::Cache=/tmp 2>/dev/null \
        || { echo "ERROR: could not download libxcb-cursor0"; exit 1; }
    dpkg-deb -x /tmp/libxcb-cursor0_*.deb /tmp/xcb-cursor-lib
fi

exec env LD_LIBRARY_PATH="$XCB_LIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
    /usr/bin/python3 -m showcase gui "$@"
