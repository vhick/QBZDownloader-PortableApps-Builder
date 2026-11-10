#!/usr/bin/env python3
"""Deterministic ZIP member metadata; records directory entries including empty Data/ folder."""
from pathlib import Path
import hashlib
import json
import zipfile

stage=Path('work/stage/QBZDownloaderPortable')
identity=json.loads((stage/'Other/Source/build-identity.json').read_text(encoding='utf-8'))
name=f"QBZDownloaderPortable-{identity['version']}-{identity['upstream_commit'][:12]}-b1r2.zip"
dest=Path('out/release')/name
dest.parent.mkdir(parents=True,exist_ok=True)
if dest.exists():raise RuntimeError('Refusing to overwrite existing ZIP')
with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as archive:
    for p in sorted([stage]+list(stage.rglob('*'))):
        relative=p.relative_to(stage.parent).as_posix()
        if p.is_symlink():raise RuntimeError('Refusing symlink in stage: '+str(p))
        if p.is_dir():
            info=zipfile.ZipInfo(relative+'/');info.date_time=(2020,1,1,0,0,0);info.external_attr=(0o40755<<16)|0x10
            archive.writestr(info,b'')
        else:
            info=zipfile.ZipInfo(relative);info.date_time=(2020,1,1,0,0,0);info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            with p.open('rb') as f,archive.open(info,'w') as dest_f:
                while chunk:=f.read(1024*1024):dest_f.write(chunk)
print('Created:',dest)
print('SHA256:',hashlib.file_digest(dest.open('rb'),'sha256').hexdigest())
