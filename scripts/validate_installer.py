#!/usr/bin/env python3
import argparse
import hashlib
import shutil
from pathlib import Path
from validate_package import pe_info

p=argparse.ArgumentParser();p.add_argument('file');p.add_argument('--publish-dir',default='out/release');args=p.parse_args()
src=Path(args.file)
if not src.is_file() or not src.name.lower().endswith('.paf.exe'):raise RuntimeError('Installer output must be real .paf.exe')
pe_info(src)
if src.stat().st_size < 1024*1024:raise RuntimeError('Unexpectedly small installer payload')
folder=Path(args.publish_dir);folder.mkdir(parents=True,exist_ok=True)
out=folder/src.name
if out.exists():raise RuntimeError('Refuse to overwrite existing installer')
shutil.copy2(src,out)
with out.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
print('STATIC-VALIDATED shared installer PE:',out,'SHA256',digest)
print('NOTE: Installer click/install/upgrade are NOT validated by this static PE check')
