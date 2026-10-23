#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
set -eu
app_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ "$(uname -s)" = Darwin ]; then
    mac_major=$(sw_vers -productVersion | cut -d. -f1)
    if [ "$mac_major" -lt 15 ]; then
        echo 'This edition targets macOS Sequoia 15 or later.'
        exit 1
    fi
fi
for python_bin in /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
    if command -v "$python_bin" >/dev/null 2>&1 && "$python_bin" -c 'import sys;sys.exit(sys.version_info < (3,11))' 2>/dev/null; then
        exec "$python_bin" "$app_dir/launcher.py" "$@"
    fi
done
echo 'Install Python 3.11+ and FFmpeg, then launch again. Homebrew: brew install python ffmpeg'
exit 1
