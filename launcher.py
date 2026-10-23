#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Portable bootstrap used by the three native terminal launchers."""
import sys
from pathlib import Path

def main():
    if sys.version_info < (3, 11):
        print('MegaMix TUI requires Python 3.11 or later. Install it, then launch again.', file=sys.stderr)
        return 1
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from megamix.cli import main as application
    return application()

if __name__ == '__main__':
    raise SystemExit(main())
