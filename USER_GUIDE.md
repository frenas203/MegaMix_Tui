# Terminal controls

| Key | Action |
| --- | --- |
| N / O | New project / open a JSON project |
| B | New project using a Save As file browser |
| I / T | Import audio files or folders / import a TXT/CSV tracklist |
| L | Paginated tracklist; N / P change page, a track number shows full details |
| M / E / R | Move / edit title and optional artist / remove after confirmation |
| K / X | Relink a source recording / export TXT or CSV |
| S | Disc duration, reserves and automatic/manual trailing pause settings |
| A | Complete preparation, conversion, pause insertion and verification |
| 1 / 2 / 3 | Individual preparation / conversion / pause-verification stages |
| F / D | Open verified CD_READY output / diagnostics and tool discovery |
| C | Generate or repair an EAC CUE in existing Ready output, without editing audio |
| H / Q | Help / quit |
| Ctrl+C | Cancel the current prompt or audio operation |

Required path/title prompts cancel on blank input. Settings retain the current
value on Enter; an unchanged settings form preserves Ready status. An artist
prompt also keeps the current value on Enter. Both decimal comma and decimal
point work for settings. Quoted paths, spaces and Unicode names are supported.
The original source recording is preserved when a project entry is removed.

B opens a Save As browser for a new project JSON file. After choosing its folder
and filename, give the project a name or press Enter to use the filename. Cancel
leaves the current project untouched. An existing destination is never replaced.
If Tkinter or a desktop display is unavailable, the app offers a typed-path
fallback. N still accepts a typed path directly, which also works over SSH.

Operation output stays visible until Enter. The last result remains on the
dashboard. Logs keep complete original engine diagnostics. D shows the last 24
lines of the latest log and can open its folder. Missing tool instructions are
available in D even before you create a project.

Save a project in a writable folder. Editing tracks or settings resets output
to Draft. Run A again before burning. Changing the source OS or source paths
requires relinking. Never burn partial output or manually mark a project Ready.
The numbered WAV files in verified CD_READY are the files to give your burner.
For EAC, load the accompanying MegaMix.cue so order and metadata are retained.
The CUE is generated automatically during the final verification step. It never
adds a second set of gaps. Existing Ready output can get a CUE through C.

Automatic pause mode is -1. Manual mode accepts 0 to 10 seconds and adds only
the amount missing from the existing tail silence. The capacity reserve reduces
usable disc time. If necessary, only newly added pauses shrink to fit. Music and
existing source silence are not shortened. Excess music stops the workflow.

The terminal displays plain ASCII layout labels and uses colour where supported.
NO_COLOR or --no-color disables colour. Redirected output does not clear prior
screens or contain rendering escapes. --no-clear keeps a scrolling transcript.
At widths below 76 columns, menu groups stack. --width 40 to 120 overrides the
detected width; normal operation adapts to the terminal size.
