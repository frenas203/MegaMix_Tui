# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import json
import signal
import sys
from pathlib import Path
from . import __version__
from .engine import Engine, Cancelled
from .terminal import Terminal
from .tui import TUI

def main(argv=None):
    parser = argparse.ArgumentParser(description='MegaMix TUI, audio-CD preparation for Windows, Linux and macOS')
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('--tui', action='store_true', help='open the terminal interface (the default)')
    parser.add_argument('--project', type=Path, help='project to open, or the project for a headless action')
    parser.add_argument('--action', choices=['New','Import','ImportList','Export','Relink','Update','Prepare','Convert','Pauses','All','Cue'])
    parser.add_argument('--request', type=Path, help='JSON request for a headless action')
    parser.add_argument('--no-clear', action='store_true', help='keep previous terminal screens visible')
    parser.add_argument('--no-color', action='store_true', help='plain text without colour escapes')
    parser.add_argument('--width', type=int, default=0, help='override terminal width, 40 to 120 columns')
    parser.add_argument('--preview', action='store_true', help='render one dashboard without prompting')
    args = parser.parse_args(argv)
    if args.width and not 40 <= args.width <= 120:
        parser.error('--width must be 40 to 120, or 0 for automatic')
    if args.action and not args.project:
        parser.error('--action requires --project')
    if args.request and not args.action:
        parser.error('--request requires --action')
    if args.action and (args.tui or args.preview):
        parser.error('--action cannot be combined with --tui or --preview')
    for stream in [sys.stdout, sys.stderr]:
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    if not args.action:
        ui = Terminal(args.width, args.no_clear or args.preview, args.no_color)
        application = TUI(args.project, ui)
        if args.preview:
            application.dashboard()
            return 0
        return application.run()
    def cancelled(signum, frame):
        raise Cancelled()
    signal.signal(signal.SIGTERM, cancelled)
    try:
        request = json.loads(args.request.read_text(encoding='utf-8-sig')) if args.request else None
        Engine(lambda text: print(text, flush=True)).action(args.action, args.project, request)
        return 0
    except (KeyboardInterrupt, Cancelled):
        return 130
    except Exception as error:
        print(f'ERROR: {error}', file=sys.stderr, flush=True)
        return 1

if __name__ == '__main__':
    sys.exit(main())
