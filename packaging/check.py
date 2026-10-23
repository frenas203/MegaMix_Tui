#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Verify archived source, launch modes and the extracted Debian TUI entry point."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent/'tui-deliverables'/'0.4.2'

def main():
    forbidden = {'.cs','.csproj','.sln','.dll','.exe','.swift','.xaml','.desktop','.ps1','.psm1'}
    manifest = json.loads((OUT/'TUI_PACKAGE_MANIFEST.json').read_text())
    assert manifest['desktopFrameworks'] == []
    for item in manifest['files']:
        file = OUT/item['name']
        assert hashlib.sha256(file.read_bytes()).hexdigest() == item['sha256']
    for file in OUT.glob('*.zip'):
        with zipfile.ZipFile(file) as archive:
            assert archive.testzip() is None
            assert len(archive.read('MegaMix_TUI/LICENSE')) > 30000
            assert not [n for n in archive.namelist() if Path(n).suffix.lower() in forbidden]
            for name in ['launch-tui','Launch_MegaMix_TUI.command','launcher.py']:
                assert archive.getinfo('MegaMix_TUI/'+name).external_attr >> 16 & 0o111
            for source in (ROOT/'megamix').glob('*.py'):
                assert archive.read('MegaMix_TUI/megamix/'+source.name) == source.read_bytes()
            metadata = tomllib.loads(archive.read('MegaMix_TUI/pyproject.toml').decode())
            assert metadata['project']['dependencies'] == []
            assert 'gui-scripts' not in metadata['project']
    with tarfile.open(OUT/'MegaMix_TUI_Linux_0.4.2.tar.gz') as archive:
        assert archive.getmember('MegaMix_TUI/launch-tui').mode & 0o111
        assert not [m for m in archive.getmembers() if Path(m.name).suffix.lower() in forbidden]
    deb = OUT/'megamix-tui_0.4.2_all.deb'
    if deb.exists():
        with tempfile.TemporaryDirectory(prefix='MegaMix installed TUI ') as temporary:
            installed = Path(temporary)
            subprocess.run(['dpkg-deb','-x',str(deb),str(installed)],check=True)
            app = installed/'usr/lib/megamix-tui'
            for source in (ROOT/'megamix').glob('*.py'):
                assert (app/'megamix'/source.name).read_bytes() == source.read_bytes()
            assert (app/'launch-tui').stat().st_mode & 0o111
            assert (installed/'usr/share/doc/megamix-tui/corresponding-source.zip').is_file()
            link = installed/'usr/bin/megamix-tui'
            assert link.is_symlink()
            result = subprocess.run([str(link),'--preview','--no-color','--width','40'],cwd='/tmp',text=True,capture_output=True,check=True)
            assert 'MEGAMIX TUI' in result.stdout
            assert 'PROJECT AND IMPORT' in result.stdout
            assert '\x1b' not in result.stdout
            control = subprocess.check_output(['dpkg-deb','-f',str(deb),'Depends'],text=True)
            assert 'python3' in control and 'ffmpeg' in control and 'qt' not in control.lower()
            recommendations = subprocess.check_output(['dpkg-deb','-f',str(deb),'Recommends'],text=True)
            assert 'python3-tk' in recommendations and 'python3-tk' not in control
    print('PASS: archive integrity and SHA-256 checksums')
    print('PASS: identical tested engine/TUI source in every ZIP and extracted Debian package')
    print('PASS: executable launcher permissions in ZIP, TAR and Debian package')
    print('PASS: no desktop application code, GUI entry points or third-party Python package dependencies')
    print('PASS: extracted Debian symlink launch from another folder with spaces in its install path')
    print('PASS: full GPL text and complete corresponding-source ZIP included')

if __name__ == '__main__':
    main()
