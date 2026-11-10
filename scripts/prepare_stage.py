#!/usr/bin/env python3
"""PortableApps staged tree. Never copy a previous user's Data into a new release."""
from pathlib import Path
import json
import shutil
import subprocess
import sys

ROOT = Path('work/stage/QBZDownloaderPortable')
APP = ROOT/'App/QBZDownloader'
INFO = ROOT/'App/AppInfo'
SRC = Path('work/upstream')

def main():
    if ROOT.exists(): raise RuntimeError('Stage exists, refusing to overwrite Data')
    image=SRC/'assets/desktop/icon.png'
    ico=SRC/'assets/desktop/icon.ico'
    if not ico.is_file() or not image.is_file(): raise RuntimeError('Missing official upstream icons')
    unpacked=SRC/'portable-unpacked/win-unpacked'
    if not (unpacked/'QBZ Downloader.exe').is_file(): raise RuntimeError('Missing upstream application EXE')
    shutil.copytree(unpacked,APP)
    INFO.mkdir(parents=True)
    shutil.copy2(ico, INFO/'appicon.ico')
    shutil.copy2(image, INFO/'appicon-source.png')
    ident=json.loads(Path('work/identity.json').read_text(encoding='utf-8'))
    v=ident['version']
    # PortableApps PackageVersion requires four numeric components.
    package_version=v+'.0'
    metadata=f'''[Format]
Type=PortableApps.comFormat
Version=3.8

[Details]
Name=QBZ Downloader Portable
AppID=QBZDownloaderPortable
Publisher=Muhammad Ibnu Fauzi (upstream); community portable repackaging
Homepage=https://github.com/ifauzeee/QBZ-Downloader
Category=Music & Video
Description=Portable Qobuz downloader and local music library manager
Language=English

[License]
Shareable=true
OpenSource=true
Freeware=true
CommercialUse=true

[Version]
PackageVersion={package_version}
DisplayVersion={v} Portable b1r3

[Control]
Icons=1
Start=QBZDownloaderPortable.exe
'''
    (INFO/'appinfo.ini').write_text(metadata,encoding='utf-8')
    shutil.copy2(Path('work/launcher/QBZDownloaderPortable.exe'),ROOT/'QBZDownloaderPortable.exe')
    (ROOT/'Data').mkdir()
    others=ROOT/'Other/Source';others.mkdir(parents=True)
    for f in ['LICENSE','README.md']:
        shutil.copy2(SRC/f,others/('UPSTREAM-'+f))
    for f in ['launcher/main.cpp','launcher/CMakeLists.txt','scripts/patch_upstream.py']:
        dest=others/f;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(f,dest)
    shutil.copy2('work/native-addon-identity.json',others/'native-addon-identity.json')
    (others/'build-identity.json').write_text(json.dumps(ident,indent=2)+'\n',encoding='utf-8')
    (ROOT/'README-PORTABLE.txt').write_text('''QBZ Downloader Portable (unofficial community build)\n\nLaunch QBZDownloaderPortable.exe, not App\\QBZDownloader\\QBZ Downloader.exe.\nData\\Electron: Electron browser profile/cache\nData\\Backend: SQLite database, keys, settings and queue history\nData\\Downloads: default audio destination for a new profile\nData\\Logs: Electron logs\n\nClose the application before moving or upgrading the folder. Preserve the entire Data directory.\nAn existing user-selected absolute download path can still point outside Data; review Settings.\nWindows-managed notifications, shell caches and machine-bound safeStorage credentials may not roam.\nNever merge with the installed QBZ Downloader profile automatically.\n''',encoding='utf-8')
    print('Staged',ROOT)

if __name__=='__main__': main()
