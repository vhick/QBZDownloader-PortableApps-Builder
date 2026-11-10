#!/usr/bin/env python3
"""Static PortableApps format, PE, app and ZIP validation. Not a substitute for GUI tests."""
import argparse
import configparser
import hashlib
import json
from pathlib import Path
import struct
import sys
import zipfile

ROOT='QBZDownloaderPortable'

def pe_info(path):
    with open(path,'rb') as f:
        header=f.read(64)
        if len(header)<64 or header[:2]!=b'MZ': raise ValueError(f'Not a PE: {path}')
        offset=struct.unpack_from('<I',header,0x3c)[0]
        if offset<64 or offset>path.stat().st_size-24: raise ValueError('Bad PE offset')
        f.seek(offset)
        if f.read(4)!=b'PE\x00\x00': raise ValueError('Missing PE header')
        machine=struct.unpack('<H',f.read(2))[0]
        if machine!=0x8664: raise ValueError(f'Expected Windows x64 PE, found {hex(machine)}')

def validate_stage(path):
    root=Path(path)
    paths=[root/'QBZDownloaderPortable.exe',root/'App/QBZDownloader/QBZ Downloader.exe',root/'App/AppInfo/appinfo.ini',
           root/'App/AppInfo/appicon.ico',root/'App/AppInfo/appicon_16.png',root/'App/AppInfo/appicon_32.png',
           root/'App/QBZDownloader/resources/app.asar',root/'App/QBZDownloader/resources/bin/win32-x64/ffmpeg.exe',
           root/'App/QBZDownloader/resources/bin/win32-x64/fpcalc.exe',root/'Other/Source/build-identity.json']
    for p in paths:
        if not p.is_file() or p.stat().st_size==0: raise ValueError('Missing or empty: '+str(p))
    if not (root/'Data').is_dir(): raise ValueError('Data missing')
    if any((root/'Data').rglob('*')): raise ValueError('Release stage must not contain a previous user profile')
    pe_info(paths[0]);pe_info(paths[1]);pe_info(paths[7]);pe_info(paths[8])
    unpacked = root/'App/QBZDownloader/resources/app.asar.unpacked'
    sqlite_nodes = list(unpacked.rglob('better_sqlite3.node')) if unpacked.is_dir() else []
    if len(sqlite_nodes) != 1: raise ValueError('Expected one rebuilt native better_sqlite3.node under app.asar.unpacked')
    pe_info(sqlite_nodes[0])
    if paths[3].read_bytes()[:4]!=b'\x00\x00\x01\x00': raise ValueError('Invalid ICO')
    for icon in paths[4:6]:
        if icon.read_bytes()[:8]!=b'\x89PNG\r\n\x1a\n': raise ValueError('Invalid PNG '+str(icon))
    parser=configparser.ConfigParser(interpolation=None)
    parser.read(paths[2],encoding='utf-8')
    if parser['Details']['AppID']!='QBZDownloaderPortable' or parser['Control']['Start']!='QBZDownloaderPortable.exe':
        raise ValueError('Incorrect metadata app identity/launcher')
    ident=json.loads(paths[9].read_text(encoding='utf-8'))
    if parser['Version']['PackageVersion']!=ident['version']+'.0': raise ValueError('Version mismatch')
    if ident['mode']!='PORTABLEAPPS' or not ident['upstream_commit']: raise ValueError('Bad source provenance')
    if not (root/'Other/Source/UPSTREAM-LICENSE').is_file(): raise ValueError('Missing upstream MIT license')
    if (root/'App/QBZDownloader/Uninstall QBZ Downloader.exe').exists():
        raise ValueError('Unexpected installed-app uninstaller in unpacked payload')
    print('STATIC-VALIDATED staging:',root,'version',ident['version'],'upstream',ident['upstream_commit'])
    return ident

def validate_zip(p):
    p=Path(p)
    with zipfile.ZipFile(p) as z:
        if z.testzip(): raise ValueError('Corrupted ZIP entry')
        members=z.namelist()
        for name in members:
            x=Path(name)
            if name.startswith('/') or '..' in x.parts or ':' in name: raise ValueError('Unsafe ZIP path: '+name)
        required=[f'{ROOT}/QBZDownloaderPortable.exe',f'{ROOT}/App/AppInfo/appinfo.ini',
          f'{ROOT}/App/QBZDownloader/QBZ Downloader.exe',f'{ROOT}/Other/Source/build-identity.json']
        if not all(x in members for x in required): raise ValueError('Missing packaged ZIP entries')
        source=json.loads(z.read(f'{ROOT}/Other/Source/build-identity.json'))
        if source['mode']!='PORTABLEAPPS':raise ValueError('Mode mismatch')
    with p.open('rb') as handle:
        digest=hashlib.file_digest(handle,'sha256').hexdigest()
    print('STATIC-VALIDATED ZIP:',p,'SHA256',digest)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--stage');ap.add_argument('--zip');args=ap.parse_args()
    if not args.stage and not args.zip:ap.error('Specify --stage or --zip')
    if args.stage:validate_stage(args.stage)
    if args.zip:validate_zip(args.zip)

if __name__=='__main__':main()
