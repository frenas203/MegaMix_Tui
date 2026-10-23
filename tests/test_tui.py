# SPDX-License-Identifier: GPL-3.0-or-later
"""Portable TUI interaction, platform adapter and cancellation checks."""
from pathlib import Path, PureWindowsPath
import copy
import io
import json
import ntpath
import os
import subprocess
import sys
import tempfile
import types
import unittest
import wave
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from megamix.engine import Engine, Cancelled, validate
from megamix.engine import filename
from megamix.platforms import project_lock
from megamix import platforms
from megamix.terminal import Terminal, cells, clipped
from megamix.tui import TUI, next_step

class TUITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='MegaMix TUI ')
        self.root = Path(self.temp.name)
        self.project = self.root / "Åsa's project.json"
    def tearDown(self):
        self.temp.cleanup()
    def fixture(self, count=18, status='Draft'):
        p = dict(schemaVersion=1,id='a'*32,name="Åsa's compilation",createdUtc='2026-10-17T10:00:00Z',revision=1,status=status,runId='',outputPath='',tracks=[],warnings=[],totalSamples=44100,totalCdFrames=75,settings=dict(discMinutes=80,safetySeconds=3,pregapSeconds=0,manualPauseSeconds=-1))
        for n in range(1,count+1):
            p['tracks'].append(dict(id=f'{n:032x}',order=n,sourcePath=str(self.root/f'source-{n}.wav'),workingPath='',title=f'Track {n} '+'long recording title '*3,artist='Artist',album='',sourceTrack=n,format='WAV',durationSeconds=1,sampleRate=44100,channels=2,bitDepth=16,codec='pcm_s16le',existingSilence=0,targetSilence=0,addedSilence=0,alignmentSilence=0,endingType='Not measured',lufs='',lra='',truePeak='',sourceHash=''))
        self.project.write_text(json.dumps(p),encoding='utf-8')
        return p
    def invoke(self, answers=(), *args):
        r = subprocess.run([sys.executable,str(ROOT/'launcher.py'),'--no-clear','--no-color',*map(str,args)],input='\n'.join(map(str,answers))+'\n',text=True,encoding='utf-8',capture_output=True,timeout=30)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        return r.stdout+r.stderr
    def test_widths_and_safe_terminal_text(self):
        p = self.fixture()
        p['name'] = 'Åsa 東京 \x1b[31m title'
        self.project.write_text(json.dumps(p),encoding='utf-8')
        for width in (40,60,75,76,96,120):
            with self.subTest(width=width):
                out = self.invoke([], '--preview','--width',width,'--project',self.project)
                for line in out.splitlines():
                    self.assertLessEqual(cells(line),width,line)
                self.assertNotIn('\x1b',out)
                for title in ('PROJECT AND IMPORT','TRACKLIST','PREPARE CD','OUTPUT AND HELP','Source estimate:','Next:'):
                    self.assertIn(title,out)
        self.assertLessEqual(cells(clipped('東京'*30,20)),20)
    def test_paging_full_details_and_missing_source(self):
        self.fixture()
        out = self.invoke(['L','N','P','18','','','Q'],'--project',self.project,'--width',80)
        self.assertIn('Page 2/',out)
        self.assertIn('TRACK 18',out)
        self.assertIn('long recording title long recording title',out)
        self.assertIn('Source is missing.',out)
    def test_unchanged_settings_preserve_ready(self):
        self.fixture(1,'Ready')
        before = self.project.read_bytes()
        out = self.invoke(['S','','','','','Q'],'--project',self.project)
        self.assertIn('Settings unchanged.',out)
        self.assertEqual(before,self.project.read_bytes())
    def test_cancel_and_unknown_command_preserve_project(self):
        self.fixture(1)
        before = self.project.read_bytes()
        out = self.invoke(['???','N','','Q'],'--project',self.project)
        self.assertIn('Unknown command.',out)
        self.assertIn('Cancelled. No changes saved.',out)
        self.assertEqual(before,self.project.read_bytes())
    def test_edit_move_and_confirm_removal(self):
        self.fixture(2)
        out = self.invoke(['E','1','Custom title','Custom artist','','M','1','2','','R','2','n','R','2','y','','Q'],'--project',self.project)
        p = json.loads(self.project.read_text())
        self.assertEqual(len(p['tracks']),1)
        self.assertEqual(p['tracks'][0]['sourceTrack'],2)
        self.assertEqual(p['tracks'][0]['order'],1)
        self.assertIn('Removal cancelled.',out)
        self.assertEqual(p['status'],'Draft')
    def test_unavailable_stages_do_not_change_project(self):
        self.fixture(1)
        before = self.project.read_bytes()
        out = self.invoke(['2','3','Q'],'--project',self.project)
        self.assertIn('Run [1]',out)
        self.assertIn('Run [2]',out)
        self.assertEqual(before,self.project.read_bytes())
    def test_decimal_comma_settings_and_invalid_numbers(self):
        self.fixture(1)
        out = self.invoke(['S','','','','0,75','Q'],'--project',self.project)
        p = json.loads(self.project.read_text())
        self.assertEqual(p['settings']['manualPauseSeconds'],0.75)
        out = self.invoke(['S','nan','Q'],'--project',self.project)
        self.assertIn('finite number',out)
        self.assertEqual(json.loads(self.project.read_text())['settings']['manualPauseSeconds'],0.75)
    def test_foreign_windows_paths_open_for_relinking(self):
        p = self.fixture(1,'Ready')
        if os.name != 'nt':
            p['tracks'][0]['sourcePath'] = 'C:\\Music\\recording.wav'
            self.project.write_text(json.dumps(p))
            out = self.invoke(['Q'],'--project',self.project)
            self.assertIn('Status: Draft',out)
    def test_eof_exits_without_spinning(self):
        r = subprocess.run([sys.executable,str(ROOT/'launcher.py'),'--no-color'],input='',capture_output=True,text=True,timeout=10)
        self.assertEqual(r.returncode,0)
        self.assertEqual(r.stdout.count('MEGAMIX TUI'),1)
    def test_diagnostics_without_project(self):
        out = self.invoke(['D','','Q'])
        self.assertIn('DIAGNOSTICS',out)
        self.assertIn('ffmpeg',out)
    def test_cue_shortcut_adds_cue_to_older_ready_output(self):
        p = self.fixture(1,'Ready')
        p['runId']='b'*32
        output=self.root/'CD_READY';output.mkdir()
        p['outputPath']=str(output)
        wav=output/filename(p['tracks'][0],'.wav')
        with wave.open(str(wav),'wb') as out:
            out.setparams((2,2,44100,0,'NONE','not compressed'));out.writeframes(b'\0'*4*44100)
        before=wav.read_bytes()
        self.project.write_text(json.dumps(p),encoding='utf-8')
        marker=dict(projectId=p['id'],runId=p['runId'],trackCount=1,totalSamples=p['totalSamples'],totalCdFrames=p['totalCdFrames'])
        (output/'VERIFIED.json').write_text(json.dumps(marker))
        out=self.invoke(['C','','','Q'],'--project',self.project)
        self.assertIn('Cue completed.',out)
        self.assertTrue((output/'MegaMix.cue').is_file())
        self.assertEqual(before,wav.read_bytes())
        self.assertEqual(json.loads(self.project.read_text())['status'],'Ready')
    def test_next_step(self):
        p = self.fixture(1,'Cancelled')
        self.assertIn('fresh preparation',next_step(p))

class AdapterTests(unittest.TestCase):
    def test_cancelled_run_clears_ready_and_releases_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'mix.json'
            engine = Engine(lambda _: None)
            engine.action('New',path,{'name':'Cancellation test'})
            with patch.object(engine,'prepare',side_effect=KeyboardInterrupt()):
                with self.assertRaises(KeyboardInterrupt):
                    engine.action('All',path)
            result = json.loads(path.read_text())
            self.assertEqual(result['status'],'Cancelled')
            self.assertEqual(result['outputPath'],'')
            with project_lock(path):
                pass
    def test_windows_path_case_and_foreign_posix_validation(self):
        class WindowsShape(PureWindowsPath):
            def resolve(self):
                return self
        project = dict(schemaVersion=1,id='a'*32,runId='',settings=dict(discMinutes=80,safetySeconds=3,pregapSeconds=0,manualPauseSeconds=-1),tracks=[dict(id='1'*32,title='One',sourcePath='C:\\Music\\One.wav'),dict(id='2'*32,title='Two',sourcePath='c:\\music\\one.wav')])
        with patch('megamix.engine.Path',WindowsShape),patch('megamix.engine.os.path.normcase',ntpath.normcase):
            with self.assertRaisesRegex(ValueError,'Duplicate'):
                validate(project)
            project['tracks'][0]['sourcePath']='/home/music/One.wav'
            project['tracks'][1]['sourcePath']='/home/music/one.wav'
            validate(project)
    def test_lock_contention_across_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)/'mix.json'
            with project_lock(project):
                code = 'from pathlib import Path;from megamix.platforms import project_lock;\nwith project_lock(Path(__import__("sys").argv[1])): pass'
                child = subprocess.run([sys.executable,'-c',code,str(project)],cwd=ROOT,capture_output=True,text=True)
                self.assertNotEqual(child.returncode,0)
                self.assertIn('busy',child.stderr)
            with project_lock(project):
                pass
    @unittest.skipIf(os.name == 'nt','Native Windows contention is covered by the cross-process test')
    def test_windows_byte_lock_adapter_contract(self):
        calls = []
        fake = types.SimpleNamespace(LK_NBLCK=2,LK_UNLCK=0,locking=lambda fd,mode,count:calls.append((mode,count)))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'mix.json'
            with patch.dict(sys.modules,{'msvcrt':fake}), patch.object(platforms.os,'name','nt'):
                with project_lock(path):
                    pass
            self.assertEqual(calls,[(2,1),(0,1)])
            self.assertGreaterEqual(Path(str(path)+'.lock').stat().st_size,1)
    def test_external_tool_terminated_when_cancelled(self):
        child = Mock()
        child.communicate.side_effect = [KeyboardInterrupt(), ('','')]
        process = Mock()
        process.__enter__ = Mock(return_value=child)
        process.__exit__ = Mock(return_value=False)
        with patch('megamix.engine.find_tool',return_value='ffmpeg'),patch('megamix.engine.subprocess.Popen',return_value=process):
            with self.assertRaises(KeyboardInterrupt):
                Engine().native('ffmpeg',['-version'])
        child.terminate.assert_called_once()
        self.assertEqual(child.communicate.call_count,2)

if __name__=='__main__':
    unittest.main(verbosity=2)
