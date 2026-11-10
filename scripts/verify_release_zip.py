#!/usr/bin/env python3
"""Check publisher SHA256SUMS and extract ZIP safely for packaging-only operation."""
import hashlib
import json
from pathlib import Path
import zipfile
from validate_package import validate_stage,validate_zip

incoming=Path('work/incoming')
sums=(incoming/'SHA256SUMS.txt').read_text(encoding='utf-8')
zips=list(incoming.glob('QBZDownloaderPortable-*.zip'))
if len(zips)!=1:raise RuntimeError('Expected exactly one verified builder-release ZIP')
item=zips[0]
checks={}
for line in sums.splitlines():
    parts=line.split('  ',1)
    if len(parts)!=2 or len(parts[0])!=64:raise RuntimeError('Bad release SHA256SUMS format')
    checks[parts[1]]=parts[0].lower()
with item.open('rb') as stream:
    digest=hashlib.file_digest(stream,'sha256').hexdigest()
if checks.get(item.name)!=digest:raise RuntimeError('Release ZIP checksum mismatch')
validate_zip(item)
target=Path('work/stage');target.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(item) as z:
    for obj in z.infolist():
        name=obj.filename.replace('\\','/')
        parts=Path(name).parts
        if not parts or parts[0]!='QBZDownloaderPortable' or '..' in parts or ':' in name or name.startswith('/'):
            raise RuntimeError('Unsafe archive entry: '+name)
        # Ensure the archived file is not a symbolic link.
        if ((obj.external_attr>>16)&0o170000)==0o120000:raise RuntimeError('Symlink archive entry disallowed')
    z.extractall(target)
validate_stage(target/'QBZDownloaderPortable')
out=Path('out/release');out.mkdir(parents=True,exist_ok=True)
import shutil
shutil.copy2(item,out/item.name)
ident=json.loads((target/'QBZDownloaderPortable/Other/Source/build-identity.json').read_text(encoding='utf-8'))
print('Verified source revision:',ident['upstream_commit'])
with open('work/pack_identity.txt','w',encoding='utf-8') as fh:
    fh.write(f"portable-qbz-v{ident['version']}-{ident['upstream_commit'][:12]}-b1r2-pack-r2")
