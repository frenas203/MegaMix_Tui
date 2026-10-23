# MegaMix TUI 0.4.2

**The active project is now terminal-only for Windows, Linux and macOS.**
The desktop applications have been dropped from active development. This source
tree and its release packages contain no desktop GUI application or GUI build
path. Previous desktop downloads are historical releases and are superseded by
this TUI project.

One Python interface and one audio engine are shared across all platforms. The
application has no Python package dependencies. It requires **Python 3.11 or
later** and external **FFmpeg/FFprobe with SoXR support**. No PowerShell, .NET,
Qt, Swift, Cocoa or Xcode is required. The optional project file browser uses
Python's Tkinter support when available; the terminal workflow does not need it.
Licensed under **GPL-3.0-or-later**.

## Start

| Platform | Launcher | Requirements |
| --- | --- | --- |
| Windows | `Launch_MegaMix_TUI.cmd` | Python 3.11+ with its launcher or PATH option; FFmpeg/FFprobe on PATH or in `tools/` |
| Debian/Linux | `./launch-tui` | `sudo apt install python3 ffmpeg xdg-utils` |
| macOS Sequoia 15+ | `Launch_MegaMix_TUI.command` | Python 3.11+ and FFmpeg, e.g. `brew install python ffmpeg` |

Extract the entire archive into a writable folder. Open the matching launcher,
or run `python launcher.py` on Windows / `python3 launcher.py` on Linux/macOS.
The Python version must be 3.11+. The launchers check this before opening the UI.
There is no dependency installation, download or network access during launch.

For the Debian package:

```sh
sudo apt install ./megamix-tui_0.4.2_all.deb
megamix-tui
```

The new Debian package conflicts with the previous `megamix-studio` GUI package
because both provide `megamix-tui`. APT will resolve removal of the old package.
Your project JSON, audio sources and generated output are not package-owned data.

macOS has one architecture-independent source package for **Apple Silicon and
Intel**. Run it with a matching Python installation. It needs no separate Swift
compile or app bundle. If an archive extractor loses executable permissions,
use `chmod +x Launch_MegaMix_TUI.command` or run it through `sh` in Terminal.
Linux users can likewise run `sh launch-tui`.

## Workflow

Use B to create a project through a file browser, N to type a new project path,
or O to open a saved one. I / T import audio or a TXT/CSV list,
L to review recordings, S to adjust settings and A to prepare the complete CD.
F opens verified output for an external Disc-At-Once audio-CD burning tool.
The TUI does not burn discs directly. H shows help; D shows tools and diagnostics.

## Create a project with a file browser

Press **B, New project (browse)**. A Save As dialog lets you choose the folder
and JSON filename. Confirm the destination, then enter a project name in the
terminal, or press Enter to use the filename as the project name. This selects
a new project file; it does not import audio. The app is still operated in the
terminal, and the dialog closes after selection.

Cancel closes the dialog without creating a project or changing the current
one. Existing project files are never overwritten; use O to open them. The
browser adds a `.json` extension if needed. N remains the direct typed-path
route and requires no graphical display or Tkinter support.

The optional browser requires Tkinter/Tcl-Tk and a desktop session. Debian/Ubuntu
users can install `python3-tk`; the Debian package recommends it. On Windows,
enable the Tcl/Tk component in the Python installer if it is missing. On macOS,
use Tk support compatible with your Python installation. If Tk or a display is
unavailable, B explains the issue and asks for a typed path instead. No packages
are installed automatically.

## CUE files for Exact Audio Copy

Every successful complete preparation (A), or final pause/verification step (3),
now creates **MegaMix.cue** and **BURN_WITH_EAC.txt** inside CD_READY. The CUE
references the numbered final WAV files in project order using relative filenames.
It includes the project name as the disc title, each track's title/artist and,
when known, the common disc artist or Various Artists for a mixed compilation.
No barcode, ISRC or original-disc subcode is invented.

The pauses are already in the WAVs. Each separate FILE has INDEX 01 00:00:00.
The CUE adds no extra PREGAP, POSTGAP or INDEX 00. In EAC, open Tools > Write CD-R,
load the CUE (rather than appending the WAVs), check the layout and use DAO with
extra inter-track gaps disabled. Keep the whole folder together. Native EAC
loading and physical burning have not been tested here.

For output prepared by an earlier version, open its Ready project and choose
**C, Generate EAC CUE**. It rechecks the WAV format, frame alignment, total length
and verification identity before writing the CUE. It does not re-encode or edit
the WAVs. Enter chooses automatic encoding: Windows-1252 when all text fits, otherwise
UTF-8 with a BOM. U / W explicitly select UTF-8 / Windows-1252.
Windows-1252 refuses unsupported characters instead of silently replacing them.
CD-Text quotes/control characters are normalized and display fields are limited
to 80 characters; full original metadata stays in the project JSON. Filename
references always match the actual final WAV names.

Headless generation for existing Ready output is also available:

```sh
python3 -m megamix.cli --action Cue --project '/path/My mix.json'
```

See `docs/EAC_CUE.md` for layout, encoding and burning instructions.

The cleaner grouped dashboard, project summary, capacity meter, pause mode and
next-step hints are now shared by all platforms. Narrow terminals stack menu
groups. Tracklists have paging and full recording details. Existing menu keys
are retained. E now edits a title and optionally its artist.

The capacity display is a **source estimate** until final verification. Ready
output includes actual pauses and CD-frame alignment. Existing source silence
is preserved, music is never trimmed, and loudness is measured without
normalizing it. Noncompliant mono/stereo inputs are converted to 44.1 kHz,
16-bit PCM stereo. Multichannel material stops for an explicit external downmix.

## Existing projects

Existing schema-version-1 Windows PowerShell and Linux/macOS project JSON files
remain supported. Open the original JSON using O. Keep its `.bak`, `.logs` and
adjacent `.megamix-<id>` workspace with it. Never delete original audio to make
space for a new release. Cross-OS source paths may need K to relink recordings.
Foreign-OS paths invalidate old Ready status before a fresh preparation.

The Windows runtime dependency changes from PowerShell to Python in this
consolidated release. The earlier PowerShell TUI is superseded, so there is no
second Windows interface to maintain. This is a source-based distribution, not
a standalone executable with a bundled interpreter.

## CLI and development

```sh
python3 launcher.py --project '/path/My mix.json'
python3 launcher.py --no-clear --no-color
python3 launcher.py --preview --width 96
python3 -m megamix.cli --action All --project '/path/My mix.json'
python3 -m unittest discover -s tests -v
python3 packaging/build.py
```

Headless actions and JSON requests remain available for automation. `--request`
accepts a request JSON file alongside `--action` and `--project`. Output is UTF-8.
`MEGAMIX_FFMPEG` and `MEGAMIX_FFPROBE` accept absolute tool paths. A local `tools/`
directory is checked before PATH. macOS also checks standard Homebrew locations.
No shell interpolation is used to invoke audio tools or open folders.

The optional package-install route is `python -m pip install .`, which uses a
standard setuptools build and creates `megamix-tui` and `megamix-cli` commands.
Running from an extracted release needs no pip installation or Python packages.

See `USER_GUIDE.md`, `docs/PROJECT_SCOPE.md` and `docs/VALIDATION.md` for controls,
scope and actual platform test status. Native Windows/macOS testing is pending;
an included CI workflow runs the same tests on all four OS/architecture targets.
