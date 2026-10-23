# Active scope

The user ended desktop application development on 17 October 2026. The active
product is MegaMix TUI for Windows, Debian/Linux and macOS Sequoia or later.

## Kept

- Import, metadata inspection, tracklist editing, list import/export and relinking.
- Red Book conversion, source preservation and analysis without normalization.
- Adaptive trailing pauses, frame alignment, capacity protection and verification.
- The improved grouped terminal interface and original keyboard shortcuts.
- GPL version 3 or later, full source, automated engine/TUI checks and platform CI.

## Consolidated

The Python engine previously shared by Linux and Mac now has portable Windows
locking, process cancellation, case-aware path handling and folder/tool adapters.
The previous Windows PowerShell interface is superseded by the same Python TUI
used everywhere. Native launchers are thin entry points to identical code.

The user later requested a file-browser option for project creation. B now opens
an optional Tkinter Save As dialog. This is a temporary path chooser, not a
desktop application or a return to separate GUI frontends. Typed paths remain
available without Tk or a desktop session.

## Dropped from the active tree and release packages

- Windows C#/.NET/Avalonia desktop project and GUI publishing steps.
- Linux PySide6/Qt GUI, desktop shortcuts and GUI runtime dependencies.
- macOS Swift/AppKit/Liquid Glass application and Xcode build kits.
- GUI screenshots, Qt/Swift tests and desktop framework licence bundles.

Historical downloads are not the active product. Old desktop archive files have
not been deleted from the user's saved files. No account files or original audio
were removed. The consolidated complete-source archive replaces the previous
active complete-source download; its contents now contain only the TUI project.
