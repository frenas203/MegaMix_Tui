# SPDX-License-Identifier: GPL-3.0-or-later
"""CUE authoring invariants and repair of existing verified output."""
from pathlib import Path
import copy
import hashlib
import json
import re
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from megamix.cue import write_cue, regenerate_cue, cue_text
from megamix.engine import filename
from megamix.engine import Engine

class CueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="Åsa's CUE test ")
        self.directory = Path(self.temp.name)
        self.project = dict(name='Åsa MegaMix', id='a'*32, runId='b'*32, status='Ready', outputPath=str(self.directory), tracks=[], totalSamples=0, totalCdFrames=0)
        for number, title, artist in [(1,'Räven','Åsa'),(2,'One "quoted" title','Another Artist')]:
            track = dict(order=number,title=title,artist=artist)
            samples = 44100*(number+4)
            self.project['tracks'].append(track)
            with wave.open(str(self.directory/filename(track,'.wav')),'wb') as out:
                out.setparams((2,2,44100,0,'NONE','not compressed'))
                out.writeframes(b'\1\0\2\0'*samples)
            self.project['totalSamples'] += samples
        self.project['totalCdFrames'] = self.project['totalSamples']//588
        self.marker = dict(schemaVersion=1,projectId=self.project['id'],runId=self.project['runId'],trackCount=2,totalSamples=self.project['totalSamples'],totalCdFrames=self.project['totalCdFrames'])
        (self.directory/'VERIFIED.json').write_text(json.dumps(self.marker))
    def tearDown(self):
        self.temp.cleanup()
    def hashes(self):
        return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.directory.glob('*.wav')}
    def test_exact_order_relative_files_metadata_and_no_double_gaps(self):
        before = self.hashes()
        details = write_cue(self.project,self.directory,'utf-8-sig')
        data = (self.directory/'MegaMix.cue').read_bytes()
        self.assertTrue(data.startswith(b'\xef\xbb\xbf'))
        self.assertNotIn(b'\n',data.replace(b'\r\n',b''))
        text = data.decode('utf-8-sig')
        # CRLF is intentionally kept on read_bytes; splitlines is used for parsing.
        files = [re.fullmatch(r'FILE "([^"]+)" WAVE',line).group(1) for line in text.splitlines() if line.startswith('FILE ')]
        self.assertEqual(files,[filename(t,'.wav') for t in self.project['tracks']])
        self.assertTrue(all((self.directory/f).is_file() and Path(f).name==f for f in files))
        self.assertIn('TITLE "Åsa MegaMix"',text)
        self.assertIn('PERFORMER "Various Artists"',text)
        self.assertIn('TITLE "One \'quoted\' title"',text)
        self.assertEqual(text.count('INDEX 01 00:00:00'),2)
        self.assertNotRegex(text,r'(?m)^\s*(PREGAP|POSTGAP|INDEX 00)\b')
        self.assertEqual(details['totalSamples'],self.project['totalSamples'])
        self.assertEqual(details['cueSHA256'],hashlib.sha256(data).hexdigest())
        self.assertEqual(before,self.hashes())
    def test_regenerate_old_ready_output_preserves_audio_and_adds_verification(self):
        before = self.hashes()
        details = regenerate_cue(self.project)
        marker = json.loads((self.directory/'VERIFIED.json').read_text())
        self.assertEqual(marker['cueFile'],'MegaMix.cue')
        self.assertEqual(marker['cueSHA256'],details['cueSHA256'])
        self.assertEqual(marker['totalCdFrames'],self.marker['totalCdFrames'])
        self.assertEqual(before,self.hashes())
        self.assertTrue((self.directory/'BURN_WITH_EAC.txt').is_file())
    def test_windows_1252_round_trip_and_no_silent_character_loss(self):
        regenerate_cue(self.project,'cp1252')
        text = (self.directory/'MegaMix.cue').read_bytes().decode('cp1252')
        self.assertIn('Räven',text)
        old = (self.directory/'MegaMix.cue').read_bytes()
        self.project['name']='東京 MegaMix'
        with self.assertRaisesRegex(ValueError,'Windows-1252'):
            regenerate_cue(self.project,'cp1252')
        self.assertEqual(old,(self.directory/'MegaMix.cue').read_bytes())
    def test_missing_or_changed_audio_and_stale_marker_are_rejected(self):
        before = self.hashes()
        for key,value in [('projectId','c'*32),('runId','c'*32),('trackCount',1),('totalSamples',1)]:
            with self.subTest(key=key):
                marker = dict(self.marker,**{key:value})
                (self.directory/'VERIFIED.json').write_text(json.dumps(marker))
                with self.assertRaises(ValueError):regenerate_cue(self.project)
        (self.directory/'VERIFIED.json').write_text(json.dumps(self.marker))
        source = self.directory/filename(self.project['tracks'][0],'.wav')
        with wave.open(str(source),'wb') as out:
            out.setparams((2,2,44100,0,'NONE','not compressed'));out.writeframes(b'\0'*4*44100*7)
        with self.assertRaisesRegex(ValueError,'lengths changed'):regenerate_cue(self.project)
        source.unlink()
        with self.assertRaises(FileNotFoundError):regenerate_cue(self.project)
        self.assertFalse((self.directory/'MegaMix.cue').exists())
    def test_unaligned_audio_and_invalid_track_order_are_rejected(self):
        self.project['tracks'][0]['order']=2
        with self.assertRaisesRegex(ValueError,'sequential'):write_cue(self.project,self.directory)
        self.project['tracks'][0]['order']=1
        source=self.directory/filename(self.project['tracks'][0],'.wav')
        with wave.open(str(source),'wb') as out:
            out.setparams((2,2,44100,0,'NONE','not compressed'));out.writeframes(b'\0'*4*44101)
        with self.assertRaisesRegex(ValueError,'aligned'):write_cue(self.project,self.directory)
        self.assertFalse((self.directory/'MegaMix.cue').exists())
    def test_unknown_performers_and_metadata_cannot_inject_cue_commands(self):
        self.project['tracks'][0]['artist']=''
        self.project['tracks'][1]['artist']=''
        self.project['name']='Name"\r\nFILE "outside.wav" WAVE\x00'
        write_cue(self.project,self.directory)
        text=(self.directory/'MegaMix.cue').read_bytes().decode('cp1252')
        self.assertEqual(sum(line.startswith('FILE ') for line in text.splitlines()),2)
        self.assertNotIn('Unknown Artist',text)
        self.assertNotIn('Various Artists',text)
        self.assertEqual(len(cue_text('x'*200)),80)
    def test_automatic_encoding_prefers_eac_legacy_text_without_losing_unicode(self):
        details=write_cue(self.project,self.directory)
        self.assertEqual(details['cueEncoding'],'cp1252')
        self.assertIn('Räven',(self.directory/'MegaMix.cue').read_bytes().decode('cp1252'))
        self.project['name']='東京 MegaMix'
        details=write_cue(self.project,self.directory)
        self.assertEqual(details['cueEncoding'],'utf-8-sig')
        self.assertIn('東京',(self.directory/'MegaMix.cue').read_text(encoding='utf-8-sig'))
    def test_write_failure_cannot_leave_a_partial_final_cue(self):
        from megamix import cue
        with patch.object(cue.os,'replace',side_effect=OSError('simulated disk error')):
            with self.assertRaises(OSError):write_cue(self.project,self.directory)
        self.assertFalse((self.directory/'MegaMix.cue').exists())
        self.assertFalse(list(self.directory.glob('*.tmp')))
    def test_cue_failure_prevents_ready_publication(self):
        import shutil
        path=self.directory/'mix.json'
        engine=Engine(lambda _:None)
        p=engine.action('New',path,{'name':'CUE failure'})
        p.update(status='Converted',runId='c'*32,tracks=copy.deepcopy(self.project['tracks']))
        red=self.directory/('.megamix-'+p['id'])/p['runId']/'REDBOOK_READY'
        red.mkdir(parents=True)
        for number,track in enumerate(p['tracks'],1):
            track.update(id=f'{number:032x}',sourcePath=str(self.directory/filename(track,'.wav')))
            shutil.copy2(track['sourcePath'],red/filename(track,'.wav'))
        path.write_text(json.dumps(p))
        with patch.object(engine,'trailing',return_value=0),patch.object(engine,'ending',return_value=('Normal',0)),patch('megamix.engine.write_cue',side_effect=OSError('CUE disk failure')):
            with self.assertRaisesRegex(OSError,'CUE disk failure'):
                engine.action('Pauses',path)
        saved=json.loads(path.read_text())
        self.assertEqual(saved['status'],'Failed')
        self.assertEqual(saved['outputPath'],'')
        self.assertFalse((red.parent/'CD_READY').exists())

if __name__=='__main__':
    unittest.main(verbosity=2)
