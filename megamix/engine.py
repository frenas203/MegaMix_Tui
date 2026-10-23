# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared audio engine. Only Python's standard library and FFmpeg are required."""
from __future__ import annotations
import contextlib, csv, datetime, hashlib, json, math, os, re, shutil, struct, subprocess, uuid
from collections import Counter
from .platforms import find_tool, project_lock
from .cue import write_cue, regenerate_cue
from pathlib import Path, PureWindowsPath, PurePosixPath

EXTENSIONS={'.wav','.flac','.mp3','.m4a','.aac','.aif','.aiff','.ogg','.opus','.wma','.alac'}
PROCESSING={'Prepare','Convert','Pauses','All'}
class Cancelled(Exception): pass
def uid(): return uuid.uuid4().hex
def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def title_for(path): return re.sub(r'^\s*\d{1,3}\s+-\s+','',Path(path).stem).strip()
def filename(track,extension):
    title=re.sub(r'[\x00-\x1f\\/:*?"<>|]','_',track['title']).strip().rstrip('.')[:100] or 'Untitled'
    return f"{track['order']:02} - {title}{extension.lower()}"
def sha256(path):
    with open(path,'rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()
def cd_frames(samples): return (samples+587)//588
def validate(p):
    if p.get('schemaVersion')!=1 or not re.fullmatch('[a-f0-9]{32}',p.get('id','')): raise ValueError('Unsupported or invalid project manifest.')
    if p.get('runId') and not re.fullmatch('[a-f0-9]{32}',p['runId']): raise ValueError('Invalid run identifier.')
    tracks=p.get('tracks',[])
    if len(tracks)>99: raise ValueError('An audio CD supports at most 99 tracks.')
    paths=set(); ids=set()
    for t in tracks:
        if not re.fullmatch('[a-f0-9]{32}',t.get('id','')) or t['id'] in ids or not str(t.get('title','')).strip(): raise ValueError('Invalid track identifier or title.')
        ids.add(t['id']); source=Path(t['sourcePath'])
        windows=PureWindowsPath(t['sourcePath']).is_absolute() and not source.is_absolute()
        posix=PurePosixPath(t['sourcePath']).is_absolute() and not source.is_absolute()
        if not source.is_absolute() and not windows and not posix: raise ValueError('Source paths must be absolute.')
        key=str(PureWindowsPath(t['sourcePath'])).casefold() if windows else str(PurePosixPath(t['sourcePath'])) if posix else os.path.normcase(str(source.resolve()))
        if key in paths: raise ValueError(f'Duplicate source reference: {source}')
        paths.add(key)
    settings=p['settings']; minutes=float(settings['discMinutes']); safety=float(settings['safetySeconds']); pregap=float(settings['pregapSeconds']); pause=float(settings['manualPauseSeconds'])
    if not all(map(math.isfinite,[minutes,safety,pregap,pause])) or not 0<minutes<=80 or min(safety,pregap)<0 or safety+pregap>=minutes*60 or not (pause==-1 or 0<=pause<=10): raise ValueError('Invalid disc or pause settings.')
def load(path):
    p=json.loads(Path(path).read_text(encoding='utf-8-sig'));validate(p)
    # Foreign Windows/POSIX paths can open for relinking, without trusting old output.
    if any(not Path(t['sourcePath']).is_absolute() for t in p['tracks']):invalidate(p)
    return p
def save(p,path):
    validate(p);path=Path(path);p['revision']=int(p.get('revision',0))+1;temp=path.with_name(path.name+'.'+uid()+'.tmp')
    try:
        with temp.open('x',encoding='utf-8') as out:
            json.dump(p,out,ensure_ascii=False,indent=2,allow_nan=False);out.write('\n');out.flush();os.fsync(out.fileno())
        if path.exists():
            backup=path.with_name(path.name+'.bak.tmp');shutil.copyfile(path,backup);os.replace(backup,str(path)+'.bak')
        os.replace(temp,path)
    finally: temp.unlink(missing_ok=True)
def invalidate(p):
    p.update(status='Draft',runId='',outputPath='',totalSamples=0,totalCdFrames=0)
    for i,t in enumerate(p['tracks'],1): t['order']=i
    p['warnings']=[f'Duplicate title, check recording: {title}' for title,count in Counter(t['title'].casefold() for t in p['tracks']).items() if count>1]
def workspace(p,path):
    root=Path(path).parent/('.megamix-'+p['id'])
    def redirected(file):
        return file.is_symlink() or bool(getattr(file.lstat(),'st_file_attributes',0)&0x400)
    if root.is_symlink() or (root.exists() and (redirected(root) or any(redirected(f) for f in root.rglob('*')))): raise ValueError('Workspace contains a symbolic link or reparse point.')
    return root
def run_path(p,path):
    if not p.get('runId'): raise ValueError('Run Prepare first.')
    return workspace(p,path)/p['runId']

class Engine:
    def __init__(self,log=print): self.log=log
    def native(self,tool,args):
        executable=find_tool(tool)
        options={'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP} if os.name=='nt' else {'start_new_session':True}
        with subprocess.Popen([executable,*map(str,args)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace',**options) as child:
            try: stdout,stderr=child.communicate()
            except (KeyboardInterrupt,Cancelled):
                child.terminate()
                try: child.communicate(timeout=3)
                except subprocess.TimeoutExpired: child.kill();child.communicate()
                raise
            if child.returncode: raise RuntimeError(f'{tool} exited {child.returncode}:\n{stderr}\n{stdout}')
            return stdout,stderr
    def metadata(self,path):
        text,_=self.native('ffprobe',['-v','error','-select_streams','a:0','-show_streams','-show_format','-of','json',path]);j=json.loads(text)
        if not j.get('streams'): raise ValueError(f'No audio stream: {path}')
        s=j['streams'][0];tags={}
        for obj in [j.get('format',{}),s]: tags.update({k.lower():str(v) for k,v in obj.get('tags',{}).items()})
        number=re.match(r'^(\d+)',tags.get('track','')) or re.match(r'^\s*(\d{1,3})\s+-\s+',Path(path).name)
        bits=int(s.get('bits_per_raw_sample') or s.get('bits_per_sample') or 0)
        return {'title':tags.get('title') or title_for(path),'artist':tags.get('artist',''),'album':tags.get('album',''),'sourceTrack':int(number[1]) if number else 0,'durationSeconds':float(j.get('format',{}).get('duration') or s.get('duration') or 0),'sampleRate':int(s.get('sample_rate',0)),'channels':int(s.get('channels',0)),'bitDepth':bits,'codec':s.get('codec_name',''),'sampleFmt':s.get('sample_fmt','')}
    def import_files(self,p,path,paths,recursive=False):
        files=[]
        for value in paths:
            source=Path(value).expanduser().absolute()
            if source.is_dir():files.extend(f for f in (source.rglob('*') if recursive else source.iterdir()) if f.is_file() and f.suffix.lower() in EXTENSIONS)
            elif source.is_file() and source.suffix.lower() in EXTENSIONS:files.append(source)
            else:raise ValueError(f'Missing or unsupported source: {source}')
        if not files: raise ValueError('No supported audio files found.')
        if len(files)+len(p['tracks'])>99:raise ValueError('Import would exceed the 99-track limit.')
        root=workspace(p,path).resolve();seen={os.path.normcase(str(Path(t['sourcePath']).resolve())) for t in p['tracks']};pending=[]
        for file in sorted(files):
            resolved=file.resolve();key=os.path.normcase(str(resolved))
            if resolved.is_relative_to(root):raise ValueError('Import originals from outside the project workspace.')
            if key in seen: raise ValueError(f'Duplicate source reference: {file}')
            seen.add(key);meta=self.metadata(file);meta.pop('sampleFmt')
            pending.append(dict(id=uid(),order=0,sourcePath=str(file),workingPath='',format=file.suffix[1:].upper(),existingSilence=0.0,targetSilence=0.0,addedSilence=0.0,alignmentSilence=0.0,endingType='Not measured',lufs='',lra='',truePeak='',sourceHash='',**meta))
            self.log(f"Imported: {meta['title']}")
        pending.sort(key=lambda t:(t['sourceTrack'] or 100000,t['sourcePath']))
        p['tracks'].extend(pending);invalidate(p)
    def import_list(self,p,path,request):
        if p['tracks']:raise ValueError('Import a tracklist into an empty project.')
        source=Path(request['sourceDirectory']).expanduser().absolute();file=Path(request['tracklist']);is_csv=file.suffix.lower()=='.csv'
        with file.open(encoding='utf-8-sig',newline='') as stream:
            if is_csv:rows=list(csv.DictReader(stream))
            elif file.suffix.lower()=='.txt':rows=[{'Title':line.strip()} for line in stream if line.strip() and not line.strip().startswith('#')]
            else:raise ValueError('Tracklist must be TXT or CSV.')
        if not rows:raise ValueError('Tracklist is empty.')
        files=[f for f in source.rglob('*') if f.is_file() and f.suffix.lower() in EXTENSIONS]
        for row in rows:
            if row.get('File'):
                target=Path(row['File']);target=target if target.is_absolute() else source/target;candidates=[target] if target.is_file() else []
            else:candidates=[f for f in files if title_for(f).casefold()==row['Title'].casefold() or f.name.casefold()==row['Title'].casefold()]
            if len(candidates)!=1:raise ValueError(f"Tracklist entry must resolve to one exact recording, found {len(candidates)}: {row.get('Title','')}. Use CSV File paths.")
            self.import_files(p,path,candidates)
            if is_csv:
                for key in ['Title','Artist']:
                    if row.get(key):p['tracks'][-1][key.lower()]=row[key]
        invalidate(p)
    def prepare(self,p,path):
        if not p['tracks']:raise ValueError('Select 1 to 99 tracks.')
        for t in p['tracks']:
            if not Path(t['sourcePath']).is_file():raise ValueError(f"Source missing or offline. Relink track {t['order']}: {t['sourcePath']}")
        p.update(runId=uid(),outputPath='',status='Preparing');out=run_path(p,path)/'MEGAMIX_WORK';out.mkdir(parents=True)
        for t in p['tracks']:
            self.log(f"Prepare {t['order']}/{len(p['tracks'])}: {t['title']}");source=Path(t['sourcePath']);dest=out/filename(t,source.suffix);before=sha256(source);shutil.copyfile(source,dest)
            if sha256(dest)!=before or sha256(source)!=before:raise ValueError(f'Source changed during copy: {source}')
            t.update(workingPath=str(dest),sourceHash=before)
        p['status']='Prepared'
    def convert(self,p,path):
        if p['status']!='Prepared':raise ValueError('Run Prepare successfully before conversion.')
        p['status']='Converting';run=run_path(p,path);out=run/'REDBOOK_READY';out.mkdir()
        for t in p['tracks']:
            self.log(f"Convert {t['order']}/{len(p['tracks'])}: {t['title']}");source=Path(t['workingPath']);expected=run/'MEGAMIX_WORK'/filename(t,Path(t['sourcePath']).suffix)
            if source!=expected or sha256(source)!=t['sourceHash']:raise ValueError('Working copy changed. Run Prepare again.')
            meta=self.metadata(source);channels=meta['channels'];bits=meta['bitDepth'];fmt=meta['sampleFmt'];codec=meta['codec'];rate=meta['sampleRate']
            if channels not in [1,2]:raise ValueError('Only mono/stereo supported. Choose an explicit multichannel downmix outside this workflow.')
            processing_bits=bits or (24 if fmt in ['s32','s32p'] else 32 if fmt in ['flt','fltp'] else 64 if fmt in ['dbl','dblp'] else 16 if fmt in ['s16','s16p'] else 0)
            dest=out/filename(t,'.wav')
            if source.suffix.lower()=='.wav' and rate==44100 and channels==2 and bits==16 and codec=='pcm_s16le':shutil.copyfile(source,dest)
            else:
                filters=[]
                if channels==1:filters.append('pan=stereo|c0=c0|c1=c0')
                if rate!=44100 or processing_bits>16 or not processing_bits or channels!=2:filters.append('aresample=44100:resampler=soxr:precision=28:cutoff=0.95:dither_method=triangular_hp')
                args=['-hide_banner','-nostdin','-v','error','-n','-i',source,'-map','0:a:0','-map_metadata','-1','-vn']
                if filters:args+=['-af',','.join(filters)]
                self.native('ffmpeg',args+['-ar','44100','-ac','2','-c:a','pcm_s16le',dest])
            wave=wave_info(dest);t['durationSeconds']=wave['samples']/44100
            _,analysis=self.native('ffmpeg',['-hide_banner','-nostats','-nostdin','-i',dest,'-af','loudnorm=I=-23:LRA=7:TP=-2:print_format=json','-f','null','-'])
            match=re.search(r'\{\s*"input_i".*?\}',analysis,re.S)
            values=json.loads(match[0]) if match else {}
            for key,field in [('lufs','input_i'),('lra','input_lra'),('truePeak','input_tp')]:t[key]=str(values.get(field,''))
        p['status']='Converted'
    def trailing(self,path,duration):
        tail=min(12,duration)
        if tail<=.10:return 0.0
        _,text=self.native('ffmpeg',['-hide_banner','-nostats','-nostdin','-sseof',f'-{tail:.3f}','-i',path,'-af','silencedetect=noise=-50dB:d=0.05','-f','null','-'])
        ends=re.findall(r'silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)',text)
        if ends and float(ends[-1][0])>=tail-.12:return max(0,float(ends[-1][1]))
        starts=re.findall(r'silence_start:\s*([0-9.]+)',text)
        if starts and float(starts[-1])>(float(ends[-1][0]) if ends else -1):return max(0,tail-float(starts[-1]))
        return 0.0
    def mean(self,path,start,length):
        _,text=self.native('ffmpeg',['-hide_banner','-nostats','-nostdin','-ss',f'{max(0,start):.3f}','-t',f'{length:.3f}','-i',path,'-af','volumedetect','-f','null','-'])
        match=re.search(r'mean_volume:\s*(-?[0-9.]+)\s*dB',text);return float(match[1]) if match else None
    def ending(self,path,duration,tail):
        audible=max(0,duration-tail)
        if audible<.6:return 'Short',.55
        end_start=max(0,audible-.35);pre_start=max(0,audible-2)
        end=self.mean(path,end_start,.35);pre=self.mean(path,pre_start,max(.1,end_start-pre_start))
        return profile_for(duration,end,pre)
    def pauses(self,p,path):
        if p['status']!='Converted':raise ValueError('Run conversion successfully before pauses.')
        p['status']='Analyzing pauses';run=run_path(p,path);red=run/'REDBOOK_READY';pending=run/'CD_READY.partial';ready=run/'CD_READY'
        if pending.exists() or ready.exists():raise ValueError('Run Prepare to create a fresh generation.')
        settings=p['settings'];limit=math.floor((settings['discMinutes']*60-settings['safetySeconds']-settings['pregapSeconds'])*75);analysis=[]
        for t in p['tracks']:
            self.log(f"Analyze pauses {t['order']}/{len(p['tracks'])}: {t['title']}");file=red/filename(t,'.wav');wave=wave_info(file);duration=wave['samples']/44100;tail=self.trailing(file,duration);kind,target=self.ending(file,duration,tail)
            if settings['manualPauseSeconds']>=0:target=settings['manualPauseSeconds']
            requested=math.ceil(max(0,target-tail)*44100);extra=cd_frames(wave['samples']+requested)-wave['cdFrames']
            analysis.append(dict(track=t,file=file,wave=wave,tail=tail,target=target,ending=kind,requested=requested,extra=extra))
        base=sum(a['wave']['cdFrames'] for a in analysis);extras=sum(a['extra'] for a in analysis)
        if base>limit:raise ValueError(f'Music plus frame alignment exceeds capacity by {math.ceil((base-limit)/75)} seconds. Remove tracks; music was not shortened.')
        scale=min(1,(limit-base)/extras) if extras else 1
        if scale<1:p['warnings'].append('Added pauses were reduced to fit disc capacity.')
        pending.mkdir();total=0;samples=0
        for a in analysis:
            t=a['track'];final=(a['wave']['cdFrames']+math.floor(a['extra']*scale))*588;dest=pending/a['file'].name
            padded_wave(a['file'],dest,final);verified=wave_info(dest)
            if verified['samples']!=final or final%588:raise ValueError('Final sample-count verification failed.')
            total+=verified['cdFrames'];samples+=final;added=final-a['wave']['samples']
            t.update(existingSilence=a['tail'],targetSilence=a['target'],endingType=a['ending'],addedSilence=min(a['requested'],added)/44100,alignmentSilence=max(0,added-a['requested'])/44100)
            self.log(f"Verified {t['order']}: {final} samples, {verified['cdFrames']} CD frames")
        if total>limit or len(list(pending.glob('*.wav')))!=len(p['tracks']):raise ValueError('Final compilation verification failed.')
        cue=write_cue(p,pending)
        if cue['totalSamples']!=samples or cue['totalCdFrames']!=total:raise ValueError('CUE layout sample-count verification failed.')
        self.log(f"CUE generated: {cue['cueFile']} ({len(p['tracks'])} tracks, embedded pauses preserved)")
        with (pending/'Verification.csv').open('w',encoding='utf-8',newline='') as f:
            fields=['order','title','artist','existingSilence','targetSilence','addedSilence','alignmentSilence','endingType','lufs','lra','truePeak'];writer=csv.DictWriter(f,fields,extrasaction='ignore');writer.writeheader();writer.writerows(p['tracks'])
        (pending/'VERIFIED.json').write_text(json.dumps(dict(schemaVersion=1,projectId=p['id'],runId=p['runId'],trackCount=len(p['tracks']),capacityCdFrames=limit,verifiedUtc=utc(),**cue),indent=2))
        pending.rename(ready);p.update(outputPath=str(ready),totalSamples=samples,totalCdFrames=total,status='Ready')
    def action(self,action,path,request=None):
        path=Path(path).expanduser().absolute();path.parent.mkdir(parents=True,exist_ok=True);request=request or {};p=None
        with project_lock(path):
            logdir=Path(str(path)+'.logs');logdir.mkdir(exist_ok=True)
            with (logdir/(datetime.datetime.now().strftime('%Y%m%dT%H%M%S')+'-'+action+'-'+uid()+'.log')).open('w',encoding='utf-8') as transcript:
                previous=self.log
                def log(line):transcript.write(str(line)+'\n');transcript.flush();previous(str(line))
                self.log=log
                try:
                    if action=='New':
                        if path.exists():raise ValueError('Project already exists. Open it instead.')
                        p=dict(schemaVersion=1,id=uid(),name=request['name'],createdUtc=utc(),revision=0,status='Draft',runId='',outputPath='',tracks=[],warnings=[],totalSamples=0,totalCdFrames=0,settings=dict(discMinutes=80.0,safetySeconds=3.0,pregapSeconds=0.0,manualPauseSeconds=-1.0));save(p,path)
                    else:p=load(path)
                    if action=='Import':self.import_files(p,path,request['paths'],request.get('recursive',False));save(p,path)
                    elif action=='ImportList':self.import_list(p,path,request);save(p,path)
                    elif action=='Export':
                        dest=Path(request['path'])
                        if dest.suffix.lower() not in ['.csv','.txt']:raise ValueError('Export must use .csv or .txt, never an audio filename.')
                        with dest.open('w',encoding='utf-8',newline='') as out:
                            if dest.suffix.lower()=='.csv':
                                writer=csv.DictWriter(out,['Track','Title','Artist','File']);writer.writeheader();writer.writerows(dict(Track=t['order'],Title=t['title'],Artist=t['artist'],File=t['sourcePath']) for t in p['tracks'])
                            else:out.write(''.join(t['title']+'\n' for t in p['tracks']))
                    elif action=='Relink':
                        t=next(t for t in p['tracks'] if t['id']==request['trackId']);source=Path(request['sourcePath']).expanduser().absolute()
                        if source.suffix.lower() not in EXTENSIONS:raise ValueError('Unsupported source format.')
                        meta=self.metadata(source);meta.pop('sampleFmt');meta.pop('title');meta.pop('artist');meta.pop('album');t.update(meta,sourcePath=str(source),workingPath='',sourceHash='',format=source.suffix[1:].upper());invalidate(p);save(p,path)
                    elif action=='Update':
                        if request['expectedRevision']!=p['revision']:raise ValueError('Project changed in another window. Reopen before editing.')
                        if 'tracks' in request:p['tracks']=request['tracks']
                        if 'settings' in request:p['settings']=request['settings']
                        invalidate(p);save(p,path)
                    elif action=='Cue':
                        cue=regenerate_cue(p,request.get('encoding','auto'))
                        log(f"CUE generated: {cue['cueFile']} ({cue['cueTrackCount']} tracks, {cue['cueEncoding']})")
                    elif action in PROCESSING:
                        for stage in (['Prepare','Convert','Pauses'] if action=='All' else [action]):
                            getattr(self,{'Prepare':'prepare','Convert':'convert','Pauses':'pauses'}[stage])(p,path);save(p,path)
                    elif action!='New':raise ValueError(f'Unknown action: {action}')
                    log(f"COMPLETE: {action}, status {p['status']}");return p
                except (Cancelled,KeyboardInterrupt):
                    if p and action in PROCESSING:p.update(status='Cancelled',outputPath='');save(p,path)
                    log('CANCELLED: incomplete output is not ready to burn.');raise
                except Exception as error:
                    import traceback
                    log('FAILED: '+action+'\n'+traceback.format_exc())
                    if p and action in PROCESSING:p.update(status='Failed',outputPath='');save(p,path)
                    raise
                finally:self.log=previous

def profile_for(duration,end,pre):
    kind='Normal';desired=.78
    if end is not None and pre is not None:
        drop=pre-end
        if drop>=8 or end<=-32:kind='Fade/Soft';desired=1.0
        elif end>=-18 and drop<4:kind='Hard/Punchy';desired=.60
    if duration<150:desired-=.10
    elif duration>300:desired+=.10
    return kind,max(.45,min(1.15,desired))

def wave_info(path):
    with open(path,'rb') as f:
        header=f.read(12)
        if len(header)!=12 or header[:4]!=b'RIFF' or header[8:]!=b'WAVE':raise ValueError(f'Not a RIFF WAV: {path}')
        size=os.fstat(f.fileno()).st_size
        if struct.unpack_from('<I',header,4)[0]+8>size:raise ValueError('Truncated WAV container.')
        fmt=None;data=None
        while f.tell()+8<=size:
            chunk,length=struct.unpack('<4sI',f.read(8));start=f.tell()
            if start+length>size:raise ValueError('Truncated WAV chunk.')
            if chunk==b'fmt ':
                if length<16:raise ValueError('Invalid PCM format chunk.')
                fmt=struct.unpack('<HHIIHH',f.read(16))
            elif chunk==b'data':
                if data is not None:raise ValueError('Multiple audio data chunks are unsupported.')
                data=(start,length)
            f.seek(start+length+(length%2))
        if fmt!=(1,2,44100,176400,4,16) or not data or not data[1] or data[1]%4:raise ValueError(f'WAV is not verified 44.1 kHz, 16-bit PCM stereo: {path}')
        return dict(offset=data[0],bytes=data[1],samples=data[1]//4,cdFrames=cd_frames(data[1]//4))
def padded_wave(source,dest,samples):
    info=wave_info(source)
    if samples<info['samples'] or samples*4+36>2**32-1:raise ValueError('Invalid output sample count.')
    with open(source,'rb') as src,open(dest,'xb') as out:
        out.write(struct.pack('<4sI4s4sIHHIIHH4sI',b'RIFF',samples*4+36,b'WAVE',b'fmt ',16,1,2,44100,176400,4,16,b'data',samples*4));src.seek(info['offset']);remaining=info['bytes']
        while remaining:
            data=src.read(min(1024*1024,remaining))
            if not data:raise ValueError('Unexpected audio EOF.')
            out.write(data);remaining-=len(data)
        remaining=(samples-info['samples'])*4;zeros=b'\0'*(1024*1024)
        while remaining:n=min(len(zeros),remaining);out.write(zeros[:n]);remaining-=n
