# TUI 0.4.2 validation, 17 October 2026

## Checks actually completed on Linux

- **20 audio-engine integration tests passed.** Generated WAV/FLAC/MP3/AAC/Ogg/Opus
  sources, original PCM preservation, folder/list imports, relinking, corruption
  and multichannel rejection, source preservation, track limits, duplicates,
  manual/automatic pauses and sample-exact 80-minute boundaries were exercised.
- The engine suite includes a real terminal interaction through New, Import,
  Move, Tracklist, All and Diagnostics, finishing with verified Ready output.
- **17 TUI/platform tests passed.** These cover widths 40 through 120, Unicode
  display widths, control-character sanitization, paging/full details, missing
  sources, editing/moving/removing entries, cancellation, settings defaults and
  decimal comma, stage guards, EOF exit and project-free tool diagnostics.
  The C shortcut was exercised against older Ready output and preserved WAV bytes.
- **10 optional file-browser tests passed.** The dialog boundary is simulated
  for selection, cancellation, missing Tk/display, JSON extensions and cleanup.
  Real project creation is exercised after selection, including the default
  project name, existing-file protection, typed fallback and preservation of an
  open project after cancellation or creation failure.
- **9 CUE tests passed.** These cover correct relative final filenames, ordered
  tracks, title/artist fields, Unicode/Windows-1252 encoding, no doubled gaps,
  stale verification/missing or changed WAV rejection, frame alignment, failed
  atomic writes and failure preventing new Ready output publication.
- Independent cuetools cueprint 1.4.1 parsed the Windows-1252 file directly and
  the Unicode body with its BOM removed for this older parser. Track count,
  titles and performers matched with no parser diagnostics. The UTF-8 BOM
  itself is not supported by this older parser; this is not an EAC import test.
- Native POSIX lock contention was tested across processes. The Windows byte
  lock call contract was tested with a simulated msvcrt module, not native Windows.
- Cancellation clears Ready/output state, releases the project lock and stops
  the running external audio process. Windows case handling and foreign POSIX
  path acceptance were also exercised through adapter tests.
- Python modules compiled successfully. Both shell launchers passed POSIX shell
  syntax checks. The Linux launcher was exercised directly and through a symlink.
  The Mac shell launcher was exercised on Linux; its Darwin-only OS guard was
  not executed here. CMD was inspected but not executed on Windows.

The current combined 56-test run is in all-tests.log; earlier component logs
are retained beside it. Optional browser results are in dialog-tests.log and
headless-dialog.log. Packaging checks are
recorded in packaging-tests.log after archive and Debian extraction validation.
New CUE results are in cue-tests.log and independent-cue-parser.log. In total,
56 automated engine/TUI/CUE/dialog tests passed on the Linux host.

## Native checks still pending

Windows CMD and console/VT behaviour, Windows native byte locking/process
cancellation, Explorer opening, macOS Terminal launch, macOS native Homebrew
discovery and both Apple Silicon/Intel execution need native tests. The included
GitHub Actions workflow targets Windows, Ubuntu, ARM64 macOS 15 and Intel macOS
15. It has not been run in this delivery and no repository was created.
EAC native CUE import, CD-Text handling and a physical CD-R burn were not run.
The generated CUE follows the documented multi-WAV command layout, and a
Windows-1252 compatibility option is available through the C shortcut.
The actual graphical Save As window was not exercised on native Windows or
macOS. Automated chooser tests simulate the Tk boundary; headless fallback is
checked using real Tk on Linux. The optional dialog needs a desktop session.

This delivery supplies runnable TUI source and launchers, not bundled interpreters
or compiled executables. Python 3.11+ and FFmpeg/FFprobe are external dependencies.
The macOS code is architecture-independent; it runs under a compatible installed
Python. The Debian package uses Architecture: all and contains only source.

## Packaging scope

No desktop application is present in the active tree or output archives. There
are no desktop GUI project files, mandatory GUI framework dependencies, Swift builds, PowerShell
scripts, desktop shortcuts or compiled runtime binaries. All packages carry the
same core and three tiny launchers so complete source and rebuilds stay portable.
The Debian package includes a separate complete corresponding-source ZIP.
All application source is GPL-3.0-or-later. Python/FFmpeg binaries are not bundled.
Tkinter is an optional system Python component for the requested file browser.
It is imported only when B is selected; typed paths and headless engine actions
do not need it. The Debian package recommends python3-tk rather than depending
on it unconditionally.
