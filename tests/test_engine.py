# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared portable engine integration suite, generated audio only."""
from pathlib import Path
import argparse, csv, hashlib, json, os, shutil, struct, subprocess, sys, tempfile, unittest, wave

ROOT = Path(__file__).resolve().parents[1]



class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='megamix-tests-')
        cls.root = Path(cls.temp.name)
        cls.audio = cls.root / "Åsa's music"; cls.audio.mkdir()
        cls.files = []
        for name, rate, channels, codec, extra in [
            ('82 Chevy.wav',44100,2,'pcm_s16le',[]),
            ('03 - Räven.flac',48000,2,'flac',['-sample_fmt','s32']),
            ('Memo.wav',96000,2,'pcm_s24le',[]),
            ('Mono.wav',44100,1,'pcm_s16le',[]),
            ('Compressed.mp3',44100,2,'libmp3lame',[]),
            ('AAC.m4a',48000,2,'aac',[]),
            ('Vorbis.ogg',44100,2,'libvorbis',[]),
            ('Opus.opus',48000,2,'libopus',[]),
        ]:
            path = cls.audio / name
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=1.1','-ar',str(rate),'-ac',str(channels),'-c:a',codec,*extra,str(path)],check=True)
            cls.files.append(path)
        cls.silent = cls.audio/'Natural silence.wav'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=duration=1','-af','apad=pad_dur=2','-ar','44100','-ac','2','-c:a','pcm_s16le',str(cls.silent)],check=True)
        (cls.audio/'ignored.txt').write_text('not audio')
        (cls.audio/'nested').mkdir();shutil.copy(cls.files[0],cls.audio/'nested'/'Other.wav')
        cls.hashes = {p:hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.audio.rglob('*') if p.is_file()}
        cls.count = 0

    @classmethod
    def tearDownClass(cls):
        for path, expected in cls.hashes.items():
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise AssertionError(f'Original changed: {path}')
        # Keep the compact test report; temporary audio is deliberately discarded.
        cls.temp.cleanup()

    def invoke(self,action,path,request=None,ok=True):
        args=[sys.executable,'-m','megamix.cli','--action',action,'--project',str(path)]
        if request is not None:
            req=path.parent/(action+'-request.json');req.write_text(json.dumps(request),encoding='utf-8');args+=['--request',str(req)]
        r=subprocess.run(args,text=True,capture_output=True,timeout=90,cwd=ROOT)
        if ok: self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        else: self.assertNotEqual(r.returncode,0,r.stdout+r.stderr)
        return r

    def project(self,files=None):
        type(self).count+=1
        folder=self.root/f'project-{self.count}';folder.mkdir();p=folder/'compilation.json'
        self.invoke('New',p,{'name':'Åsa compilation'})
        if files:self.invoke('Import',p,{'paths':[str(f) for f in files],'recursive':False})
        return p

    def load(self,p):return json.loads(p.read_text(encoding='utf-8-sig'))
    def save(self,p,j):p.write_text(json.dumps(j),encoding='utf-8')
    def test_01_title_preservation_and_metadata(self):
        p=self.project(self.files[:2]);j=self.load(p)
        self.assertEqual({t['title'] for t in j['tracks']},{'82 Chevy','Räven'})
        self.assertEqual(j['tracks'][0]['title'],'Räven')
        self.assertEqual(j['tracks'][0]['bitDepth'],24)
    def test_02_all_formats_complete_and_pcm_preserved(self):
        p=self.project(self.files+[self.silent]);self.invoke('All',p);j=self.load(p)
        self.assertEqual(j['status'],'Ready');out=Path(j['outputPath'])
        self.assertEqual(len(list(out.glob('*.wav'))),9)
        total=0
        for t in j['tracks']:
            f=next(out.glob(f"{t['order']:02} - *.wav"))
            with wave.open(str(f),'rb') as w:
                self.assertEqual((w.getframerate(),w.getsampwidth(),w.getnchannels()),(44100,2,2));self.assertEqual(w.getnframes()%588,0);total+=w.getnframes()
                pcm=w.readframes(w.getnframes())
            if t['title']=='82 Chevy':
                with wave.open(str(self.files[0]),'rb') as src: original=src.readframes(src.getnframes())
                self.assertEqual(pcm[:len(original)],original);self.assertTrue(all(b==0 for b in pcm[len(original):]))
            if t['title']=='Natural silence':self.assertGreater(t['existingSilence'],1.9);self.assertEqual(t['addedSilence'],0)
        self.assertEqual(total,j['totalSamples']);self.assertEqual(total//588,j['totalCdFrames'])
        marker=json.loads((out/'VERIFIED.json').read_text())
        cue=(out/'MegaMix.cue').read_bytes().decode(marker['cueEncoding'])
        self.assertEqual(cue.count('INDEX 01 00:00:00'),9)
        self.assertNotRegex(cue,r'(?m)^\s*(PREGAP|POSTGAP|INDEX 00)\b')
        self.assertEqual([line for line in cue.splitlines() if line.startswith('FILE ')],[f'FILE "{t["order"]:02} - {t["title"]}.wav" WAVE' for t in j['tracks']])
        self.assertEqual(marker['cueFile'],'MegaMix.cue')
        self.assertEqual(marker['cueSHA256'],hashlib.sha256((out/'MegaMix.cue').read_bytes()).hexdigest())
        before={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in out.glob('*.wav')}
        self.invoke('Cue',p,{'encoding':'cp1252'})
        self.assertEqual(before,{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in out.glob('*.wav')})
    def test_03_duplicate_references_rejected_atomically(self):
        p=self.project([self.files[0]]);before=p.read_bytes();self.invoke('Import',p,{'paths':[str(self.files[0])],'recursive':False},ok=False);self.assertEqual(p.read_bytes(),before)
    def test_04_empty_unsupported_and_offline(self):
        empty=self.root/'empty';empty.mkdir()
        p=self.project()
        for file in [empty,self.audio/'ignored.txt',self.root/'offline']:
            self.invoke('Import',p,{'paths':[str(file)],'recursive':False},ok=False)
            self.assertEqual(self.load(p)['tracks'],[])
    def test_05_nested_import(self):
        p=self.project();self.invoke('Import',p,{'paths':[str(self.audio)],'recursive':False});self.assertEqual(len(self.load(p)['tracks']),9)
        p=self.project();self.invoke('Import',p,{'paths':[str(self.audio)],'recursive':True});self.assertEqual(len(self.load(p)['tracks']),10)
    def test_06_missing_source_stops_before_conversion(self):
        p=self.project([self.files[0]]);j=self.load(p);j['tracks'][0]['sourcePath']=str(self.root/'offline.wav');self.save(p,j)
        r=self.invoke('All',p,ok=False);self.assertIn('Relink',r.stdout);j=self.load(p);self.assertEqual(j['status'],'Failed');self.assertEqual(j['outputPath'],'')
        self.assertFalse(list(p.parent.rglob('REDBOOK_READY')))
    def test_07_capacity_reduces_only_added_silence(self):
        p=self.project(self.files[:2]);j=self.load(p);j['settings'].update(discMinutes=0.04,safetySeconds=0,pregapSeconds=0);self.save(p,j)
        self.invoke('All',p);j=self.load(p);self.assertLessEqual(j['totalCdFrames'],180);self.assertTrue(any('reduced' in w for w in j['warnings']))
        self.assertGreaterEqual(j['totalSamples'],2*1.1*44100)
    def test_08_music_over_capacity_has_no_ready_output(self):
        p=self.project([self.files[0]]);j=self.load(p);j['settings'].update(discMinutes=0.01,safetySeconds=0);self.save(p,j)
        self.invoke('All',p,ok=False);j=self.load(p);self.assertEqual(j['status'],'Failed');self.assertEqual(j['outputPath'],'');self.assertFalse(list(p.parent.rglob('CD_READY')))
    def test_09_corrupt_input_and_multi_channel(self):
        p=self.project([self.files[0]]);self.invoke('Prepare',p);j=self.load(p);Path(j['tracks'][0]['workingPath']).write_text('broken')
        self.invoke('Convert',p,ok=False);self.assertEqual(self.load(p)['status'],'Failed')
        bad=self.root/'Surround.wav';subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','anullsrc=r=44100:cl=5.1','-t','0.2','-c:a','pcm_s16le',str(bad)],check=True)
        p=self.project([bad]);self.invoke('All',p,ok=False);self.assertEqual(self.load(p)['outputPath'],'')
    def test_10_same_titles_are_explicit_and_safe(self):
        other=self.root/'different recording';other.mkdir();shutil.copy(self.files[0],other/self.files[0].name)
        p=self.project([self.files[0],other/self.files[0].name]);self.assertTrue(self.load(p)['warnings']);self.invoke('All',p);self.assertEqual(len(list(Path(self.load(p)['outputPath']).glob('*.wav'))),2)
    def test_11_tracklist_order_and_ambiguity(self):
        txt=self.root/'wanted.txt';txt.write_text('82 Chevy\nMemo\n',encoding='utf-8');p=self.project();self.invoke('ImportList',p,{'tracklist':str(txt),'sourceDirectory':str(self.audio)})
        self.assertEqual([t['title'] for t in self.load(p)['tracks']],['82 Chevy','Memo'])
        txt.write_text('Nonexistent\n');p=self.project();self.invoke('ImportList',p,{'tracklist':str(txt),'sourceDirectory':str(self.audio)},ok=False);self.assertEqual(self.load(p)['tracks'],[])
    def test_12_invalid_schema_and_limit(self):
        p=self.project();j=self.load(p);j['schemaVersion']=2;self.save(p,j);self.invoke('Prepare',p,ok=False)
        many=self.root/'100 files';many.mkdir()
        for i in range(100):shutil.copy(self.files[0],many/f'{i:03} - Track.wav')
        p=self.project();self.invoke('Import',p,{'paths':[str(many)],'recursive':False},ok=False);self.assertEqual(self.load(p)['tracks'],[])
    def test_13_workspace_path_traversal_and_symlink(self):
        p=self.project([self.files[0]]);j=self.load(p);j['runId']='../../outside';self.save(p,j);self.invoke('Convert',p,ok=False)
        p=self.project([self.files[0]]);j=self.load(p);root=p.parent/('.megamix-'+j['id']);root.symlink_to(self.audio,target_is_directory=True);self.invoke('All',p,ok=False)
    def test_14_single_track_reopen_and_new_generation(self):
        p=self.project([self.files[0]]);self.invoke('All',p);j=self.load(p);old=Path(j['outputPath']);self.invoke('All',p);j=self.load(p);self.assertNotEqual(str(old),j['outputPath']);self.assertTrue(old.is_dir());self.assertEqual(j['status'],'Ready')
    def test_15_manual_pause_and_frame_rounding(self):
        p=self.project([self.files[0]]);j=self.load(p);j['settings']['manualPauseSeconds']=2;self.save(p,j);self.invoke('All',p);j=self.load(p)
        self.assertGreater(j['tracks'][0]['addedSilence'],1.99);self.assertLess(j['tracks'][0]['alignmentSilence'],1/75+0.0001)
    def test_16_import_failure_does_not_expose_stale_ready(self):
        p=self.project([self.files[0]]);self.invoke('All',p);self.invoke('Import',p,{'paths':[str(self.files[1])],'recursive':False});j=self.load(p);self.assertEqual(j['status'],'Draft');self.assertEqual(j['outputPath'],'')
    def test_17_real_80_minute_boundary_uses_samples(self):
        # Sparse PCM fixture tests the actual WAV parser and finalizer at the 80-minute boundary.
        for delta,ok in [(-1,True),(1,False)]:
            p=self.project([self.files[0]]);j=self.load(p);j['runId']='a'*32;j['status']='Converted';self.save(p,j)
            red=p.parent/('.megamix-'+j['id'])/j['runId']/'REDBOOK_READY';red.mkdir(parents=True)
            count=359775*588+delta;f=red/'01 - 82 Chevy.wav'
            with f.open('wb') as w:
                w.write(struct.pack('<4sI4s4sIHHIIHH4sI',b'RIFF',count*4+36,b'WAVE',b'fmt ',16,1,2,44100,176400,4,16,b'data',count*4));w.seek(count*4+43);w.write(b'\0')
            self.invoke('Pauses',p,ok=ok);j=self.load(p)
            if ok:self.assertEqual(j['totalCdFrames'],359775);self.assertEqual(j['totalSamples'],359775*588)
            else:self.assertEqual(j['outputPath'],'')
    def test_18_tui_create_import_reorder_and_process(self):
        p=self.root/'tui-project.json'
        answers=f'N\n{p}\nConsole project\n\nI\n{self.files[0]}\n{self.files[1]}\n\nn\n\nM\n1\n2\n\nL\n\nA\n\nD\n\nQ\n'
        r=subprocess.run([sys.executable,'-m','megamix.cli','--tui'],input=answers,text=True,capture_output=True,timeout=90,cwd=ROOT)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr);j=self.load(p);self.assertEqual(j['status'],'Ready');self.assertEqual(j['tracks'][0]['title'],'82 Chevy')
        self.assertIn('COMPLETE: All',r.stdout);self.assertTrue(list(p.parent.glob(p.name+'.logs/*.log')))
    def test_19_long_paths_and_duplicate_batch(self):
        folder=self.root/('long directory '*9)/('nested directory '*9);folder.mkdir(parents=True);long=folder/"Åsa's [82] $song.wav";shutil.copy(self.files[0],long)
        p=self.project([long]);self.invoke('All',p);self.assertEqual(self.load(p)['status'],'Ready')
        p=self.project();self.invoke('Import',p,{'paths':[str(long),str(long)],'recursive':False},ok=False);self.assertEqual(self.load(p)['tracks'],[])
    def test_20_export_roundtrip_and_relink(self):
        p=self.project([self.files[0]]);j=self.load(p);j['tracks'][0]['title']='Custom title';self.save(p,j)
        csvfile=self.root/'Export.csv';self.invoke('Export',p,{'path':str(csvfile)});self.assertTrue(csvfile.is_file())
        q=self.project();self.invoke('ImportList',q,{'tracklist':str(csvfile),'sourceDirectory':str(self.audio)});self.assertEqual(self.load(q)['tracks'][0]['title'],'Custom title')
        self.invoke('Relink',q,{'trackId':self.load(q)['tracks'][0]['id'],'sourcePath':str(self.files[2])});j=self.load(q);self.assertEqual(j['tracks'][0]['sampleRate'],96000);self.assertEqual(j['tracks'][0]['bitDepth'],24);self.assertEqual(j['status'],'Draft')
        txt=self.root/'Export.txt';self.invoke('Export',q,{'path':str(txt)});self.assertEqual(txt.read_text().strip(),'Custom title')
        self.invoke('Export',q,{'path':str(self.files[0])},ok=False)

if __name__=='__main__': unittest.main(verbosity=2)
