# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional save-file chooser. The terminal and engine do not require Tk."""
from pathlib import Path


class FileBrowserUnavailable(RuntimeError):
    pass


def choose_project_file(initial_directory=None):
    """Return a destination path, or None on Cancel, without opening a file."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as error:
        raise FileBrowserUnavailable(
            'File browser unavailable: this Python installation has no Tkinter support. '
            'On Debian/Ubuntu, install python3-tk, or enter a path in the terminal.'
        ) from error

    directory = Path(initial_directory).expanduser() if initial_directory else Path.home()
    if not directory.is_dir():
        directory = Path.home()
    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.title('MegaMix TUI')
        try:
            root.attributes('-topmost', True)
        except tk.TclError:
            pass
        root.update_idletasks()
        selected = filedialog.asksaveasfilename(
            parent=root,
            title='MegaMix: save new project',
            initialdir=str(directory),
            initialfile='My compilation.json',
            defaultextension='.json',
            filetypes=[('MegaMix project', '*.json')],
        )
        if not selected:
            return None
        path = Path(selected).expanduser().absolute()
        if path.suffix.lower() != '.json':
            path = path.with_name(path.name + '.json')
        return path
    except tk.TclError as error:
        raise FileBrowserUnavailable(
            'File browser could not open. A working desktop session and Python Tk support '
            'are needed. You can enter the project path in the terminal instead.'
        ) from error
    finally:
        if root is not None:
            try:
                root.destroy()
            except tk.TclError:
                pass
