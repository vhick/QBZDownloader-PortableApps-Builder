#!/usr/bin/env python3
"""Windows-only source build of the real upstream Electron app, preserving lockfile provenance."""
import hashlib
import json
import shutil
import struct
import os
import re
from pathlib import Path
import subprocess
import sys

def run(*argv,cwd=None):
    print('RUN:', ' '.join(argv),flush=True)
    subprocess.run(argv,cwd=cwd,check=True,env={**os.environ,'PYTHONIOENCODING':'utf-8'})

def sqlite_native_layout(module_root):
    """Resolve the binary used by the actual version's JS loader.

    better-sqlite3 v13+ prefers its Node-API prebuilds/win32-x64.node;
    v12 and older use build/Release/better_sqlite3.node. Never validate
    a legacy .node when the active loader will prefer a different prebuild.
    """
    module_root = Path(module_root)
    manifest = module_root/'package.json'
    if not manifest.is_file():
        raise RuntimeError('Missing SQLite package.json: '+str(manifest))
    pkg = json.loads(manifest.read_text(encoding='utf-8'))
    if pkg.get('name') != 'better-sqlite3':
        raise RuntimeError('Unexpected SQLite module identity')
    version = pkg.get('version', '')
    match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?:-[0-9A-Za-z.-]+)?',version)
    if not match:
        raise RuntimeError('Cannot determine better-sqlite3 version: '+repr(version))
    if int(match.group(1)) >= 13:
        rel = 'prebuilds/win32-x64.node'
        if not (module_root/'lib/binding.js').is_file():
            raise RuntimeError('v13+ SQLite binding.js missing; cannot verify loader contract')
    else:
        rel = 'build/Release/better_sqlite3.node'
    return rel, version


def native_addon_path(module_root):
    rel, _ = sqlite_native_layout(module_root)
    return Path(module_root)/rel


def inspect_pe_x64(path):
    """Require a nonempty x64 PE DLL; no substitute files or dummy binaries."""
    path = Path(path)
    if not path.is_file() or path.stat().st_size < 10000:
        raise RuntimeError(f'Missing/implausibly small native SQLite addon: {path}')
    with path.open('rb') as f:
        header = f.read(64)
        if len(header) != 64 or header[:2] != b'MZ':
            raise RuntimeError(f'SQLite addon not a Windows PE: {path}')
        offset = struct.unpack_from('<I', header, 0x3c)[0]
        if offset < 64 or offset + 6 > path.stat().st_size:
            raise RuntimeError(f'Invalid SQLite addon PE offset: {path}')
        f.seek(offset)
        if f.read(4) != b'PE\x00\x00' or struct.unpack('<H', f.read(2))[0] != 0x8664:
            raise RuntimeError(f'SQLite addon is not x64 PE: {path}')


def sha256_file(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def snapshot_sqlite_module(src, destination):
    """Capture the source-verified module BEFORE electron-builder can prune it."""
    module = Path(src)/'node_modules/better-sqlite3'
    path = native_addon_path(module)
    inspect_pe_x64(path)
    for name in ['package.json','lib/index.js','lib/database.js']:
        if not (module/name).is_file():
            raise RuntimeError('Incomplete source SQLite module: '+name)
    destination = Path(destination)
    if destination.exists():
        raise RuntimeError('Existing SQLite snapshot; refusing to mix builds: '+str(destination))
    shutil.copytree(module, destination, symlinks=True)
    native = native_addon_path(destination)
    inspect_pe_x64(native)
    if sha256_file(native) != sha256_file(path):
        raise RuntimeError('SQLite source snapshot checksum mismatch')
    rel, version = sqlite_native_layout(destination)
    print('SQLITE SOURCE SNAPSHOT:', version, rel, sha256_file(native),flush=True)
    return destination


def ensure_packaged_sqlite(source_module, packaged):
    """Restore only the verified module if Electron omitted the active loader binary.

    `source_module` is the read-only snapshot made immediately after the
    upstream rebuild step; do NOT read mutable upstream node_modules after
    packaging. Never silently replace a different packaged native binary.
    """
    source_module=Path(source_module)
    packaged=Path(packaged)
    target_module=packaged/'resources/app/node_modules/better-sqlite3'
    rel, expected = sqlite_native_layout(source_module)
    source_native=source_module/rel
    target_native=target_module/rel
    inspect_pe_x64(source_native)
    if not target_native.is_file():
        print('PACKAGING REPAIR: SQLite active native addon missing from packaged Electron; '
              'copying only verified snapshot module tree',flush=True)
        shutil.copytree(source_module,target_module,dirs_exist_ok=True,symlinks=True)
    inspect_pe_x64(target_native)
    if sha256_file(source_native)!=sha256_file(target_native):
        raise RuntimeError('Packaged SQLite native binary differs from verified source snapshot')
    actual_rel, actual=sqlite_native_layout(target_module)
    if rel!=actual_rel or expected!=actual:
        raise RuntimeError(f'Packaged SQLite loader/version mismatch: {expected}/{rel} != {actual}/{actual_rel}')
    for name in ['package.json','lib/index.js','lib/database.js']:
        if not (target_module/name).is_file():
            raise RuntimeError('Missing packaged SQLite loader file: '+name)
    if int(expected.split('.')[0])>=13 and not (target_module/'lib/binding.js').is_file():
        raise RuntimeError('Packaged SQLite v13 binding.js missing')
    print('PACKAGED SQLITE VERIFIED:',target_native,'version',actual,
          'SHA256',sha256_file(target_native),flush=True)
    return target_native


def smoke_sqlite_under_packaged_electron(packaged):
    """Headless Electron-ABI require/SQLite query, no GUI or persistent user profile."""
    packaged=Path(packaged).resolve()
    exe=packaged/'QBZ Downloader.exe'
    app_root=packaged/'resources/app'
    node= native_addon_path(app_root/'node_modules/better-sqlite3')
    inspect_pe_x64(node)
    script = (
        "const path=require('path');"
        "const root=process.argv[1];"
        "const Database=require(path.join(root,'node_modules','better-sqlite3'));"
        "const db=new Database(':memory:');"
        "const v=db.prepare('SELECT 7 AS proof').get();"
        "db.close();"
        "if(v.proof!==7)process.exit(23);"
        "console.log('ELECTRON SQLITE RUNTIME OK',process.versions.electron,process.arch);"
    )
    env={**os.environ, 'ELECTRON_RUN_AS_NODE':'1', 'PYTHONIOENCODING':'utf-8'}
    print('HEADLESS ELECTRON SQLITE ABI TEST:',exe,flush=True)
    # A packaged Electron executable can run its embedded Node runtime when
    # ELECTRON_RUN_AS_NODE is set. Test lives entirely in memory.
    subprocess.run([str(exe), '-e', script, str(app_root)],cwd=app_root,env=env,
                   check=True,timeout=90)

def main():
    if os.name!='nt': raise RuntimeError('Application packaging must run on Windows runner')
    src=Path('work/upstream').resolve()
    if not (src/'electron/main.cjs').is_file(): raise RuntimeError('Source checkout missing')
    run('npm.cmd','ci','--no-audit','--no-fund',cwd=src)
    run('npm.cmd','run','build:full',cwd=src)
    run('npm.cmd','run','desktop:rebuild',cwd=src)
    sqlite_snapshot=snapshot_sqlite_module(src,Path('work/verified-sqlite-module'))
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
        # v26 supports asar:false. This avoids fragile native-addon ASAR
        # metadata and makes the Electron ABI module directly verifiable.
        'asar':False,
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
    native_addon=ensure_packaged_sqlite(sqlite_snapshot, produced.parent)
    smoke_sqlite_under_packaged_electron(produced.parent)
    electron_version=json.loads((src/'node_modules/electron/package.json').read_text(encoding='utf-8'))['version']
    addon_identity={'module':'better-sqlite3','electron_version':electron_version,
                    'native_path':native_addon.relative_to(produced.parent).as_posix(),
                    'module_version':sqlite_native_layout(sqlite_snapshot)[1],
                    'native_sha256':sha256_file(native_addon),
                    'verification':'headless Electron require + in-memory SQLite SELECT 7'}
    Path('work/native-addon-identity.json').write_text(
        json.dumps(addon_identity,indent=2)+'\n',encoding='utf-8')
    print('UPSTREAM WINDOWS APP PRODUCED',produced,flush=True)

if __name__=='__main__': main()
