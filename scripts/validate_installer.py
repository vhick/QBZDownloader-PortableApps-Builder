#!/usr/bin/env python3
"""Validate the pinned custom-NSIS installer executable before publication.

The installer EXE is x86 (IMAGE_FILE_MACHINE_I386 0x014c), even when the
app/launcher and bundled native modules inside it are Windows x64. PE
signature validation is a *static* check, not proof of successful installation.
"""
import argparse
import hashlib
import shutil
from pathlib import Path
from validate_package import pe_info

NSIS_STUB_MACHINE = 0x014c
MIN_INSTALLER_BYTES = 1024 * 1024


def validate_installer(file, publish_dir='out/release'):
    src = Path(file)
    if not src.is_file() or not src.name.lower().endswith('.paf.exe'):
        raise RuntimeError('Installer output must be a real .paf.exe file')
    if src.stat().st_size < MIN_INSTALLER_BYTES:
        raise RuntimeError('Unexpectedly small installer payload')
    machine = pe_info(src, allowed_machines=(NSIS_STUB_MACHINE,))
    folder = Path(publish_dir)
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / src.name
    if out.exists():
        raise RuntimeError('Refuse to overwrite existing installer')
    shutil.copy2(src, out)
    with out.open('rb') as f:
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    print('STATIC-VALIDATED shared custom-NSIS installer PE:', out,
          'machine', hex(machine), 'SHA256', digest)
    print('NOTE: Installer click/install/upgrade are NOT validated by this static PE check')
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('file')
    p.add_argument('--publish-dir', default='out/release')
    args = p.parse_args()
    validate_installer(args.file, args.publish_dir)


if __name__ == '__main__':
    main()
