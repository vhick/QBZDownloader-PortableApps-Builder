#!/usr/bin/env python3
"""Windows-only source build of the real upstream Electron app, preserving lockfile provenance."""
import json
import os
from pathlib import Path
import subprocess
import sys

def run(*argv,cwd=None):
    print('RUN:', ' '.join(argv),flush=True)
    subprocess.run(argv,cwd=cwd,check=True,env={**os.environ,'PYTHONIOENCODING':'utf-8'})

def main():
    if os.name!='nt': raise RuntimeError('Application packaging must run on Windows runner')
    src=Path('work/upstream').resolve()
    if not (src/'electron/main.cjs').is_file(): raise RuntimeError('Source checkout missing')
    run('npm.cmd','ci','--no-audit','--no-fund',cwd=src)
    run('npm.cmd','run','build:full',cwd=src)
    run('npm.cmd','run','desktop:rebuild',cwd=src)
    run('npm.cmd','run','bundle-binaries',cwd=src)
    for binary in ['ffmpeg.exe','fpcalc.exe']:
        p=src/'bin/win32-x64'/binary
        if not p.is_file() or p.stat().st_size<10000: raise RuntimeError(f'Required upstream media helper missing: {p}')
    # The upstream package.json main points to the backend. Set the Electron
    # main entry for THIS package only, without mutating upstream release metadata.
    config={
        'appId':'com.ifauze.qbzdownloader.portable',
        'productName':'QBZ Downloader',
        'executableName':'QBZ Downloader',
        'asar':True,
        'asarUnpack':['**/*.node'],
        'npmRebuild':False,
        'buildDependenciesFromSource':False,
        'directories':{'output':'portable-unpacked','buildResources':'assets/desktop'},
        'files':['dist/**/*','electron/**/*','assets/desktop/**/*','package.json','node_modules/**/*','!**/*.map','!**/*.ts'],
        'extraResources':[{'from':'bin/win32-x64','to':'bin/win32-x64'}],
        'extraMetadata':{'main':'electron/main.cjs'},
        'win':{'icon':'assets/desktop/icon.ico'}
    }
    config_path=src/'portable-builder.generated.json'
    config_path.write_text(json.dumps(config,indent=2),encoding='utf-8')
    run('npx.cmd','--no-install','electron-builder','--win','--x64','--dir','--config',str(config_path),cwd=src)
    produced=src/'portable-unpacked/win-unpacked/QBZ Downloader.exe'
    if not produced.is_file(): raise RuntimeError('Expected unpacked QBZ Downloader.exe missing')
    print('UPSTREAM WINDOWS APP PRODUCED',produced,flush=True)

if __name__=='__main__': main()
