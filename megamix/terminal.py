# SPDX-License-Identifier: GPL-3.0-or-later
"""Dependency-free, width-aware terminal rendering with a plain-text fallback."""
import os
import re
import shutil
import sys
import unicodedata

COLORS = dict(cyan=96, white=97, gray=37, muted=90, green=92, yellow=93, red=91)

def clean(text):
    return re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', str(text))

def cells(text):
    return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in text)

def clipped(text, width, middle=False):
    text = clean(text)
    if cells(text) <= width:
        return text
    if width <= 0:
        return ''
    def take(value, limit):
        result = ''
        for c in value:
            if cells(result + c) > limit:
                break
            result += c
        return result
    if width <= 3:
        return take(text, width)
    if middle:
        left = (width - 3) // 2
        return take(text, left) + '...' + take(text[::-1], width - 3 - left)[::-1]
    return take(text, width - 3) + '...'

def padded(text, width):
    text = clipped(text, width)
    return text + ' ' * max(0, width - cells(text))

def windows_vt():
    try:
        import ctypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetStdHandle.argtypes = [ctypes.c_ulong]
        kernel.GetStdHandle.restype = ctypes.c_void_p
        kernel.GetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        kernel.SetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        handle = kernel.GetStdHandle(-11 & 0xffffffff)
        mode = ctypes.c_ulong()
        return bool(kernel.GetConsoleMode(handle, ctypes.byref(mode)) and kernel.SetConsoleMode(handle, mode.value | 4))
    except (ImportError, AttributeError, OSError):
        return False

class Terminal:
    def __init__(self, width=0, no_clear=False, no_color=False, output=None, reader=None):
        self.output = output or sys.stdout
        self.reader = reader or input
        self.requested_width = width
        tty = self.output.isatty()
        self.vt = tty and (windows_vt() if os.name == 'nt' else os.environ.get('TERM') != 'dumb')
        self.color = self.vt and not no_color and 'NO_COLOR' not in os.environ
        self.no_clear = no_clear or not self.vt

    @property
    def width(self):
        return max(40, min(120, self.requested_width or shutil.get_terminal_size((96, 30)).columns - 1))

    @property
    def page_size(self):
        return max(4, min(16, shutil.get_terminal_size((96, 30)).lines - 14))

    def paint(self, text, color):
        return f'\x1b[{COLORS[color]}m{text}\x1b[0m' if self.color else text

    def write(self, text='', color='gray', end='\n'):
        self.output.write(self.paint(text, color) + end)
        self.output.flush()

    def line(self, text='', color='gray'):
        self.write('  ' + clipped(text, self.width - 4), color)

    def wrap(self, text, color='gray'):
        for paragraph in str(text).splitlines() or ['']:
            remaining = clean(paragraph)
            while cells(remaining) > self.width - 4:
                piece = clipped(remaining, self.width - 4)
                # Do not count the display ellipsis as consumed source text.
                piece = piece[:-3] if piece.endswith('...') else piece
                cut = piece.rfind(' ')
                if cut >= len(piece) // 2:
                    piece = piece[:cut]
                if not piece:
                    piece = remaining[0]
                self.line(piece, color)
                remaining = remaining[len(piece):].lstrip()
            self.line(remaining, color)

    def rule(self):
        self.line('-' * (self.width - 4), 'muted')

    def heading(self, title='', subtitle=''):
        if not self.no_clear:
            self.write('\x1b[2J\x1b[H', end='')
        self.write()
        self.line('MEGAMIX TUI', 'cyan')
        if subtitle:
            self.line(subtitle, 'muted')
        self.rule()
        if title:
            self.line(title, 'white')
            self.write()

    def read(self, prompt):
        return self.reader('  ' + prompt + ': ').strip()

    def pause(self):
        self.write()
        self.read('Press Enter to return')

    def command(self, item, width):
        if item is None:
            return ' ' * width
        key, label, enabled = item
        key_color, text_color = ('cyan', 'gray') if enabled else ('muted', 'muted')
        return self.paint(f'  [{key}] ', key_color) + self.paint(padded(label, width - 6), text_color)

    def menu_pair(self, left_title, left, right_title, right):
        if self.width >= 76:
            cell = (self.width - 2) // 2
            self.line(padded(left_title, cell) + right_title, 'white')
            for i in range(max(len(left), len(right))):
                a = left[i] if i < len(left) else None
                b = right[i] if i < len(right) else None
                self.output.write(self.command(a, cell) + self.command(b, cell) + '\n')
        else:
            for title, items in [(left_title, left), (right_title, right)]:
                self.line(title, 'white')
                for item in items:
                    self.output.write(self.command(item, self.width - 2) + '\n')
                self.write()
        self.write()
