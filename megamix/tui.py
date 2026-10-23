# SPDX-License-Identifier: GPL-3.0-or-later
"""One terminal interface for Windows, Linux and macOS."""
import json
import math
import os
from pathlib import Path
import sys

from . import __version__
from .engine import Engine, Cancelled, load
from .platforms import find_tool, open_folder
from .dialogs import choose_project_file, FileBrowserUnavailable
from .terminal import Terminal, clipped, padded

class UserCancelled(Exception):
    pass

def duration(seconds):
    seconds = math.ceil(max(0, float(seconds)))
    return f'{seconds // 60:02}:{seconds % 60:02}'

def next_step(project):
    if project is None:
        return '[B] Browse for a new project, [N] type a path, or [O] open.'
    if not project['tracks']:
        return '[I] Import audio files/folders or [T] import a tracklist.'
    return {
        'Prepared': '[2] Convert working copies, or [A] run the complete workflow.',
        'Converted': '[3] Add pauses and verify the final CD files.',
        'Ready': '[F] Open output and load MegaMix.cue in EAC. [C] Regenerate CUE.',
        'Failed': '[D] Read diagnostics, then [1] start a fresh preparation.',
        'Cancelled': '[1] Start a fresh preparation when you are ready.',
    }.get(project['status'], '[A] Prepare complete CD, or [S] review disc and pause settings.')

class TUI:
    def __init__(self, project=None, terminal=None):
        self.ui = terminal or Terminal()
        self.path = Path(project).expanduser().absolute() if project else None
        self.notice = ''
        self.notice_color = 'gray'
        self.engine = Engine(self.engine_log)

    def engine_log(self, text):
        if str(text).startswith('FAILED:'):
            self.ui.line('Operation failed. Full engine details are in Diagnostics.', 'red')
        else:
            self.ui.wrap(text)

    def message(self, text, color='green'):
        self.notice, self.notice_color = str(text), color

    def required(self, prompt):
        value = self.ui.read(prompt)
        if not value:
            raise UserCancelled()
        return value

    def input_path(self, prompt):
        value = self.required(prompt)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ['"', "'"]:
            value = value[1:-1]
        if not value:
            raise UserCancelled()
        return Path(os.path.expandvars(value)).expanduser().absolute()

    def project(self):
        if self.path is None:
            raise ValueError('Create or open a project with N / O first.')
        return load(self.path)

    def dashboard(self):
        project, error = None, ''
        if self.path:
            try:
                project = load(self.path)
            except Exception as ex:
                error = str(ex)
        platform = 'WINDOWS' if os.name == 'nt' else 'MACOS' if sys.platform == 'darwin' else 'LINUX'
        ui = self.ui
        ui.heading(subtitle=f'{platform}  /  Audio-CD preparation  /  {__version__}')
        if project:
            ui.line('Project  ' + project['name'], 'white')
            ui.line('File     ' + clipped(str(self.path), ui.width - 13, middle=True), 'muted')
            state = project['status']
            ui.line(f"{len(project['tracks']):02} tracks   |   Status: {state}", 'green' if state == 'Ready' else 'red' if state == 'Failed' else 'gray')
            settings = project['settings']
            exact = state == 'Ready'
            seconds = project['totalSamples'] / 44100 if exact else sum(t['durationSeconds'] for t in project['tracks'])
            budget = math.floor((settings['discMinutes'] * 60 - settings['safetySeconds'] - settings['pregapSeconds']) * 75) / 75
            over = seconds > budget
            ui.wrap(f"{'Verified output' if exact else 'Source estimate'}: {duration(seconds)} / {duration(budget)}   |   {duration(abs(budget-seconds))} {'over capacity' if over else 'remaining'}", 'yellow' if over else 'gray')
            bars = min(32, ui.width - 8)
            filled = max(0, min(bars, math.floor(seconds / max(1, budget) * bars)))
            pause = 'Automatic' if settings['manualPauseSeconds'] == -1 else f"{settings['manualPauseSeconds']:g} s"
            ui.wrap('[' + '#' * filled + '.' * (bars - filled) + ']  Pause: ' + pause, 'muted')
            if project['warnings']:
                ui.line(f"Warnings: {len(project['warnings'])}. [L] View tracklist for details.", 'yellow')
        else:
            ui.line('No project open', 'white')
            ui.line('Create a compilation or reopen a saved project.', 'muted')
            if error:
                ui.wrap('Could not read project: ' + error, 'red')
        ui.rule()
        ui.write()
        exists, tracks = project is not None, bool(project and project['tracks'])
        ui.menu_pair('PROJECT AND IMPORT', [
            ('N', 'New project (type path)', True), ('B', 'New project (browse)', True),
            ('O', 'Open project', True),
            ('I', 'Import files / folders', exists), ('T', 'Import TXT / CSV', exists),
            ('S', 'Disc and pause settings', exists),
        ], 'TRACKLIST', [
            ('L', 'View tracklist', exists), ('M', 'Move track', tracks), ('E', 'Edit title / artist', tracks),
            ('R', 'Remove track', tracks), ('K', 'Relink source', tracks), ('X', 'Export TXT / CSV', tracks),
        ])
        ui.menu_pair('PREPARE CD', [
            ('A', 'Prepare complete CD', tracks), ('1', 'Prepare working copies', tracks),
            ('2', 'Convert to Red Book', tracks and project['status'] == 'Prepared'),
            ('3', 'Add pauses and verify', tracks and project['status'] == 'Converted'),
        ], 'OUTPUT AND HELP', [
            ('F', 'Open verified CD_READY', exists and project['status'] == 'Ready'),
            ('C', 'Generate EAC CUE', exists and project['status'] == 'Ready'),
            ('D', 'Diagnostics and tools', True), ('H', 'Help and shortcuts', True), ('Q', 'Quit', True),
        ])
        ui.wrap('Next: ' + next_step(project), 'cyan')
        if project and project['status'] != 'Ready':
            ui.line('Duration is an estimate until pauses and frame alignment are verified.', 'muted')
        if self.notice:
            ui.wrap(self.notice, self.notice_color)
        ui.rule()

    def action(self, name, request=None, path=None):
        self.ui.write()
        self.ui.rule()
        self.ui.line('Running: ' + name, 'cyan')
        try:
            result = self.engine.action(name, path or self.path, request)
            self.message(name + ' completed.')
            self.ui.wrap(self.notice, self.notice_color)
            return result
        except (KeyboardInterrupt, Cancelled):
            self.message('Cancelled. Incomplete output is not ready to burn.', 'yellow')
            self.ui.wrap(self.notice, self.notice_color)
            return None
        except Exception as error:
            self.message('Error: ' + str(error), 'red')
            self.ui.wrap(self.notice, 'red')
            self.ui.wrap('Use [D] Diagnostics for the operation log.', 'muted')
            return None

    def update(self, project, **values):
        return self.action('Update', dict(expectedRevision=project['revision'], **values))

    def choose_track(self, project, prompt='Track number'):
        for track in project['tracks'][:12]:
            self.ui.line(f"{track['order']:2}  {track['title']}")
        if len(project['tracks']) > 12:
            self.ui.line('Use [L] on the dashboard for the complete tracklist.', 'muted')
        number = int(self.required(prompt))
        if not 1 <= number <= len(project['tracks']):
            raise ValueError('Choose a track number from the tracklist.')
        return number - 1

    def tracklist(self):
        page = 0
        while True:
            project = self.project()
            tracks = project['tracks']
            ui = self.ui
            size = ui.page_size
            pages = max(1, math.ceil(len(tracks) / size))
            page = max(0, min(pages - 1, page))
            ui.heading('TRACKLIST / ' + project['name'], f"{len(tracks)} tracks | Page {page+1}/{pages} | {project['status']}")
            width = ui.width - 4
            wide = width >= 72
            title_width = width - (43 if wide else 13)
            header = ' #   ' + padded('TITLE', title_width)
            if wide:
                header += '  ' + padded('ARTIST', 19)
            ui.line(header + '    TIME' + ('  FORMAT' if wide else ''), 'muted')
            ui.rule()
            for t in tracks[page * size:(page + 1) * size]:
                row = f"{t['order']:2}   " + padded(t['title'], title_width)
                if wide:
                    row += '  ' + padded(t['artist'], 19)
                row += '  ' + duration(t['durationSeconds']).rjust(6)
                if wide:
                    row += '  ' + clipped(t['format'], 6)
                ui.line(row)
            if not tracks:
                ui.line('No recordings yet. Use [I] or [T].', 'muted')
            for warning in project['warnings']:
                ui.wrap('Warning: ' + warning, 'yellow')
            ui.rule()
            ui.wrap('[N] Next  [P] Previous  Track number: details  [Enter] Back', 'muted')
            answer = ui.read('Tracklist').upper()
            if not answer:
                return
            if answer == 'N':
                page += 1
            elif answer == 'P':
                page -= 1
            elif answer.isdigit() and 1 <= int(answer) <= len(tracks):
                t = tracks[int(answer)-1]
                ui.heading('TRACK ' + answer, 'Recording details')
                for key in ['title', 'artist', 'album', 'format', 'sourcePath']:
                    ui.wrap(f'{key}: {t[key]}')
                ui.wrap(f"{t['sampleRate']} Hz / {t['bitDepth']} bit / {t['channels']} channels / {duration(t['durationSeconds'])}")
                ui.wrap(f"Loudness: {t['lufs'] or 'Not measured'} LUFS / Peak: {t['truePeak'] or 'Not measured'} dBTP")
                ui.wrap(f"Ending: {t['endingType']} / Existing silence: {t['existingSilence']:.3f}s / Added: {t['addedSilence']:.3f}s / Alignment: {t['alignmentSilence']:.3f}s")
                if not Path(t['sourcePath']).is_file():
                    ui.wrap('Source is missing. Use [K] Relink on the dashboard.', 'yellow')
                ui.pause()

    def settings(self, project):
        self.ui.heading('DISC AND PAUSE SETTINGS', 'Enter keeps the current value. Decimal point or comma is accepted.')
        labels = [('discMinutes', 'Disc minutes, maximum 80'), ('safetySeconds', 'Safety reserve, seconds'),
                  ('pregapSeconds', 'Authoring pregap reserve, seconds'), ('manualPauseSeconds', 'Trailing pause, -1 automatic or 0 to 10 seconds')]
        values = dict(project['settings'])
        for key, label in labels:
            text = self.ui.read(f'{label} [{values[key]:g}]')
            if text:
                number = float(text.replace(',', '.'))
                if not math.isfinite(number):
                    raise ValueError('Enter a finite number.')
                values[key] = number
        if values == project['settings']:
            self.message('Settings unchanged. Current output status preserved.', 'muted')
        else:
            if self.update(project, settings=values):
                self.message('Settings saved. Output reset to Draft.')

    def diagnostics(self):
        ui = self.ui
        ui.heading('DIAGNOSTICS', 'Tool discovery and original engine logs')
        ui.wrap(f'Python {sys.version.split()[0]} / {sys.platform} / {__version__}')
        for tool in ['ffmpeg', 'ffprobe']:
            try:
                ui.wrap(f'{tool}: {find_tool(tool)}', 'green')
            except FileNotFoundError as error:
                ui.wrap(str(error), 'yellow')
        logs = []
        folder = Path(str(self.path) + '.logs') if self.path else None
        if folder:
            ui.wrap('Logs: ' + str(folder))
            logs = sorted(folder.glob('*.log'), key=lambda f: f.stat().st_mtime, reverse=True)
        if logs:
            ui.line('Most recent logs', 'white')
            for file in logs[:6]:
                ui.line(file.name)
            ui.write()
            ui.line('LATEST LOG, FINAL 24 LINES', 'cyan')
            for line in logs[0].read_text(encoding='utf-8', errors='replace').splitlines()[-24:]:
                ui.wrap(line)
            if ui.read('[O] Open log folder / [Enter] Back').upper() == 'O':
                open_folder(folder)
        else:
            ui.line('No operation logs yet.', 'muted')
            ui.pause()

    def help(self):
        self.ui.heading('HELP AND SHORTCUTS', 'The same terminal workflow on Windows, Linux and macOS')
        for text in [
            '1. B creates a project using a Save As browser. N accepts a typed path; O reopens one.',
            '2. I imports files/folders. T imports a TXT/CSV list into an empty project.',
            '3. L shows tracks. M moves, E edits title/artist, K relinks and R removes an entry.',
            '4. S controls disc capacity, safety/pregap reserves and trailing pauses.',
            '5. A prepares, converts, adds pauses and verifies. Stages 1, 2 and 3 also work separately.',
            '6. F opens CD_READY. Load MegaMix.cue in EAC for Disc-At-Once burning.',
            'C adds or regenerates a CUE in existing Ready output without changing audio.',
            'Grey commands need a project, recordings or the preceding stage.',
            'Required prompts: blank cancels. Settings and artist prompts: Enter keeps the value.',
            'Ctrl+C cancels the current operation. Incomplete files are never marked Ready.',
            'Existing source silence stays intact. Only added pauses may shrink to fit the disc.',
            'Source duration is an estimate. Ready output includes pauses and CD-frame alignment.',
            'Moving a project between operating systems may require K to relink its sources.',
            'D shows diagnostics and FFmpeg discovery. Q exits; completed edits are already saved.',
        ]:
            self.ui.wrap(text)
        self.ui.pause()

    def dispatch(self, choice):
        ui = self.ui
        if choice == 'H':
            return self.help()
        if choice == 'D':
            return self.diagnostics()
        if choice in ['N', 'B']:
            if choice == 'B':
                ui.heading('NEW PROJECT / BROWSE', 'Choose a new JSON filename. Existing projects are never overwritten.')
                try:
                    candidate = choose_project_file(self.path.parent if self.path else None)
                except FileBrowserUnavailable as error:
                    ui.wrap(str(error), 'yellow')
                    candidate = self.input_path('Save project as (.json)')
                if candidate is None:
                    raise UserCancelled()
                if candidate.exists():
                    raise ValueError('Project already exists. Use O to open it, or choose a new filename.')
                ui.wrap('Save to: ' + str(candidate), 'muted')
                suggested = candidate.stem.strip() or 'New compilation'
                ui.wrap('Suggested project name: ' + suggested)
                name = ui.read('Project name [Enter uses suggested name]') or suggested
            else:
                ui.heading('NEW PROJECT', 'Enter a JSON path and name. Blank input cancels.')
                candidate = self.input_path('Save project as (.json)')
                name = self.required('Project name')
            if self.action('New', {'name': name}, candidate):
                self.path = candidate
            ui.pause()
            return
        if choice == 'O':
            ui.heading('OPEN PROJECT', 'Paste a saved project JSON path. Blank input cancels.')
            candidate = self.input_path('Project JSON path')
            p = load(candidate)
            self.path = candidate
            self.message('Opened: ' + p['name'])
            return
        if choice not in ['I','T','L','M','R','E','K','X','S','1','2','3','A','F','C']:
            raise ValueError('Unknown command. Use a shortcut shown above, or H for help.')
        p = self.project()
        if choice in ['M','R','E','K','X','1','2','3','A'] and not p['tracks']:
            raise ValueError('Import recordings with I / T first.')
        if choice == '2' and p['status'] != 'Prepared':
            raise ValueError('Run [1] Prepare working copies before conversion.')
        if choice == '3' and p['status'] != 'Converted':
            raise ValueError('Run [2] Convert successfully before adding pauses.')
        if choice == 'I':
            ui.heading('IMPORT AUDIO', 'One file/folder path per line. Blank input finishes.')
            paths = []
            while True:
                try:
                    paths.append(str(self.input_path(f'Path {len(paths)+1}')))
                except UserCancelled:
                    break
            if paths:
                recursive = ui.read('Include subfolders? [y/N]').lower() in ['y','yes']
                self.action('Import', dict(paths=paths, recursive=recursive))
                ui.pause()
            else:
                self.message('Import cancelled.', 'muted')
        elif choice == 'T':
            ui.heading('IMPORT TRACKLIST', 'TXT: one title per line. CSV: Title, optional Artist and File.')
            file = self.input_path('TXT / CSV path')
            folder = self.input_path('Source audio directory')
            self.action('ImportList', dict(tracklist=str(file), sourceDirectory=str(folder)))
            ui.pause()
        elif choice == 'L':
            self.tracklist()
        elif choice in ['M','R','E','K']:
            ui.heading({'M':'MOVE TRACK','R':'REMOVE TRACK','E':'EDIT TITLE / ARTIST','K':'RELINK SOURCE'}[choice], 'Blank at a required prompt cancels.')
            index = self.choose_track(p)
            track = p['tracks'][index]
            if choice == 'M':
                target = int(self.required('New position')) - 1
                if not 0 <= target < len(p['tracks']):
                    raise ValueError('Invalid track position.')
                p['tracks'].insert(target, p['tracks'].pop(index))
            elif choice == 'R':
                ui.wrap('Remove: ' + track['title'], 'yellow')
                ui.wrap('The source recording is preserved.', 'muted')
                if ui.read('Confirm removal? [y/N]').lower() not in ['y','yes']:
                    self.message('Removal cancelled.', 'muted')
                    return
                p['tracks'].pop(index)
            elif choice == 'E':
                track['title'] = self.required('New title')
                artist = ui.read('Artist [Enter keeps current]')
                if artist:
                    track['artist'] = artist
            else:
                file = self.input_path('Replacement source path')
                self.action('Relink', dict(trackId=track['id'], sourcePath=str(file)))
                ui.pause()
                return
            if self.update(p, tracks=p['tracks']):
                self.message('Tracklist saved. Output reset to Draft.')
            ui.pause()
        elif choice == 'X':
            ui.heading('EXPORT TRACKLIST', 'CSV preserves source paths. TXT exports titles.')
            self.action('Export', dict(path=str(self.input_path('Save as (.txt / .csv)'))))
            ui.pause()
        elif choice == 'S':
            self.settings(p)
            if self.notice_color == 'red':
                ui.pause()
        elif choice in ['1','2','3','A']:
            action = {'1':'Prepare','2':'Convert','3':'Pauses','A':'All'}[choice]
            ui.heading('PREPARE COMPLETE CD' if choice == 'A' else action.upper(), 'Working copies -> Red Book -> Pauses -> Verification')
            self.action(action)
            ui.pause()
        elif choice == 'C':
            ui.heading('GENERATE EAC CUE', 'Uses verified output WAVs. Audio is not modified.')
            if p['status'] != 'Ready':
                raise ValueError('Complete preparation before generating a CUE.')
            option = ui.read('Encoding: [Enter] Auto / [U] UTF-8 / [W] Windows-1252').upper()
            if option not in ['', 'U', 'W']:
                raise ValueError('Choose Enter for Auto, U for UTF-8 or W for Windows-1252.')
            self.action('Cue', {'encoding': {'':'auto','U':'utf-8-sig','W':'cp1252'}[option]})
            ui.pause()
        elif choice == 'F':
            if p['status'] != 'Ready' or not p['outputPath']:
                raise ValueError('No verified output. Run a complete preparation first.')
            marker = Path(p['outputPath']) / 'VERIFIED.json'
            verified = json.loads(marker.read_text())
            if any(verified.get(k) != p[k] for k in ['totalSamples','totalCdFrames']) or verified.get('projectId') != p['id'] or verified.get('runId') != p['runId']:
                raise ValueError('Output verification does not match this project. Prepare again.')
            open_folder(p['outputPath'])
            self.message('Opened verified CD_READY output.')

    def run(self):
        while True:
            try:
                self.dashboard()
                choice = self.ui.read('Choose command').upper()
                if choice == 'Q':
                    self.ui.line('MegaMix TUI closed. Completed changes remain saved.', 'muted')
                    return 0
                if choice:
                    self.dispatch(choice)
            except EOFError:
                return 0
            except UserCancelled:
                self.message('Cancelled. No changes saved.', 'muted')
            except (KeyboardInterrupt, Cancelled):
                self.message('Cancelled.', 'yellow')
            except Exception as error:
                self.message('Error: ' + str(error), 'red')
