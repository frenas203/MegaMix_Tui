#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build terminal-only source distributions and an architecture-all Debian package."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.4.2'
OUT = ROOT.parent / 'tui-deliverables' / VERSION
FORBIDDEN = {'.cs','.csproj','.sln','.dll','.exe','.swift','.xaml','.desktop','.ps1','.psm1'}

def sources():
    return sorted(p for p in ROOT.rglob('*') if p.is_file() and not any(part in {'__pycache__','.git','build','dist'} or part.endswith('.egg-info') for part in p.relative_to(ROOT).parts) and p.suffix != '.pyc')

def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()

def zip_package(destination, files, folder):
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
        for file in files:
            info = zipfile.ZipInfo.from_file(file, Path(folder)/file.relative_to(ROOT))
            info.create_system = 3
            executable = file.name in ['launch-tui','Launch_MegaMix_TUI.command','launcher.py']
            info.external_attr = (0o100755 if executable else 0o100644) << 16
            archive.writestr(info,file.read_bytes(),compress_type=zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    files = sources()
    assert not [p for p in files if p.suffix.lower() in FORBIDDEN], 'Desktop or legacy runtime code found in active project'
    metadata = tomllib.loads((ROOT/'pyproject.toml').read_text())
    assert metadata['project']['dependencies'] == []
    assert metadata['project']['license']['text'] == 'GPL-3.0-or-later'
    assert (ROOT/'LICENSE').stat().st_size > 30000
    for log in ['engine-tests.log','tui-tests.log','cue-tests.log','dialog-tests.log','all-tests.log']:
        assert '\nOK\n' in (ROOT/'docs'/log).read_text(), f'Run {log} before packaging'
    source = OUT/'MegaMix_Studio_Complete_Source.zip'
    zip_package(source, files, 'MegaMix_TUI')
    def platform_files(launcher):
        # All packages carry all three tiny launchers, keeping source/rebuilds complete.
        return files
    windows = OUT/'MegaMix_Toolkit_TUI.zip'
    mac = OUT/f'MegaMix_TUI_macOS_{VERSION}.zip'
    linux = OUT/f'MegaMix_TUI_Linux_{VERSION}.tar.gz'
    zip_package(windows, platform_files('Launch_MegaMix_TUI.cmd'), 'MegaMix_TUI')
    zip_package(mac, platform_files('Launch_MegaMix_TUI.command'), 'MegaMix_TUI')
    with tarfile.open(linux,'w:gz') as archive:
        for file in platform_files('launch-tui'):
            def permissions(info):
                info.mode = 0o755 if file.name in ['launch-tui','Launch_MegaMix_TUI.command','launcher.py'] else 0o644
                return info
            archive.add(file, arcname=Path('MegaMix_TUI')/file.relative_to(ROOT), recursive=False, filter=permissions)
    deb = None
    if shutil.which('dpkg-deb'):
        with tempfile.TemporaryDirectory(prefix='megamix-tui-deb-') as temporary:
            stage = Path(temporary)
            app = stage/'usr/lib/megamix-tui'
            for file in platform_files('launch-tui'):
                target = app/file.relative_to(ROOT)
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(file,target)
            binaries = stage/'usr/bin'
            binaries.mkdir(parents=True)
            for command in ['megamix-tui','megamix-cli']:
                (binaries/command).symlink_to('../lib/megamix-tui/launch-tui')
            docs = stage/'usr/share/doc/megamix-tui'
            docs.mkdir(parents=True)
            for name in ['README.md','USER_GUIDE.md','LICENSE','NOTICE']:
                shutil.copy2(ROOT/name, docs/name)
            shutil.copy2(source,docs/'corresponding-source.zip')
            (docs/'copyright').write_text('Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/\nUpstream-Name: MegaMix TUI\n\nFiles: *\nCopyright: 2026 MegaMix Studio contributors\nLicense: GPL-3.0-or-later\n The full licence is in LICENSE and /usr/share/common-licenses/GPL-3.\n')
            for p in stage.rglob('*'):
                if p.is_dir():
                    p.chmod(0o755)
                elif not p.is_symlink():
                    p.chmod(0o755 if p.name in ['launch-tui','launcher.py'] else 0o644)
            control = stage/'DEBIAN'
            control.mkdir()
            size = sum(p.stat().st_size for p in (stage/'usr').rglob('*') if p.is_file())//1024
            (control/'control').write_text(f'Package: megamix-tui\nVersion: {VERSION}\nArchitecture: all\nSection: sound\nPriority: optional\nMaintainer: MegaMix Studio contributors <megamix-studio@example.invalid>\nInstalled-Size: {size}\nDepends: python3 (>= 3.11), ffmpeg\nRecommends: xdg-utils, python3-tk\nConflicts: megamix-studio\nReplaces: megamix-studio\nDescription: Terminal audio-CD preparation and verification\n Shared Python terminal interface with tracklist editing, Red Book\n conversion, adaptive trailing pauses and sample-exact CD verification.\n No desktop GUI or Python package dependencies. GPL version 3 or later.\n Complete corresponding source is included.\n')
            md5 = [hashlib.md5(p.read_bytes()).hexdigest()+'  '+p.relative_to(stage).as_posix() for p in sorted((stage/'usr').rglob('*')) if p.is_file() and not p.is_symlink()]
            (control/'md5sums').write_text('\n'.join(md5)+'\n')
            deb = OUT/f'megamix-tui_{VERSION}_all.deb'
            subprocess.run(['dpkg-deb','--root-owner-group','-Zxz','--build',str(stage),str(deb)],check=True)
    products = [windows, mac, linux, source] + ([deb] if deb else [])
    (OUT/'SHA256SUMS_TUI_0.4.2.txt').write_text(''.join(digest(p)+'  '+p.name+'\n' for p in products))
    report = {'version':VERSION,'interface':'TUI only','engine':'Python standard library + external FFmpeg/FFprobe','python':'>=3.11','pythonDependencies':[],'license':'GPL-3.0-or-later','windows':'source with CMD launcher','linux':'source tar and Debian architecture-all package','macOS':'Sequoia 15+, architecture-independent source with .command launcher','desktopFrameworks':[],'bundledRuntime':False,'nativeWindowsMacTests':'pending; CI workflow included','files':[{'name':p.name,'bytes':p.stat().st_size,'sha256':digest(p)} for p in products]}
    report.update(cueGeneration='automatic in CD_READY; C shortcut and headless Cue action for existing Ready output',cueLayout='one relative FILE per verified WAV, INDEX 01 00:00:00, no extra gap commands',cueEncoding='automatic Windows-1252 or UTF-8 BOM; CRLF',nativeEacBurnTest='pending',projectBrowser='optional Tkinter Save As dialog via B, with typed-path fallback')
    (OUT/'TUI_PACKAGE_MANIFEST.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    main()
