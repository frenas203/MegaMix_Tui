# SPDX-License-Identifier: GPL-3.0-or-later
"""Small OS adapters shared by the TUI and headless audio engine."""
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import subprocess
import sys


def find_tool(tool):
    override = os.environ.get('MEGAMIX_' + tool.upper())
    if override:
        candidate = Path(override).expanduser()
        if candidate.is_absolute() and candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
        raise FileNotFoundError(f'MEGAMIX_{tool.upper()} must name an executable absolute path.')
    suffix = '.exe' if os.name == 'nt' else ''
    local = Path(__file__).resolve().parent.parent / 'tools' / (tool + suffix)
    if local.is_file() and os.access(local, os.X_OK):
        return str(local)
    found = shutil.which(tool)
    if found:
        return found
    if sys.platform == 'darwin':
        for directory in ('/opt/homebrew/bin', '/usr/local/bin'):
            candidate = Path(directory) / tool
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
    instructions = ('Install FFmpeg and FFprobe, then add their bin folder to PATH or put the executables in tools/.' if os.name == 'nt'
                    else 'Install with: brew install ffmpeg' if sys.platform == 'darwin'
                    else 'Install with: sudo apt install ffmpeg')
    raise FileNotFoundError(f'{tool} was not found. {instructions}')


def open_folder(path):
    path = Path(path).resolve()
    if not path.is_dir():
        raise FileNotFoundError(f'Folder does not exist: {path}')
    if os.name == 'nt':
        os.startfile(str(path))
    else:
        command = 'open' if sys.platform == 'darwin' else 'xdg-open'
        subprocess.Popen([command, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@contextmanager
def project_lock(path):
    """Nonblocking POSIX flock or Windows byte lock, released on every exit."""
    with open(str(path) + '.lock', 'a+b') as stream:
        if os.name == 'nt':
            import msvcrt
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b'\0')
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise ValueError('Project is busy in another terminal.') from error
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError('Project is busy in another terminal.') from error
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)
