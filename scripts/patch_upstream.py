#!/usr/bin/env python3
"""Fail-closed adaptation of verified QBZ Electron main process. No blanket APPDATA or TEMP redirection."""
import argparse
from pathlib import Path

MARKER = '// QBZ-PORTABLEAPPS-BUILDER-b1r2'
PROLOGUE = r'''// QBZ-PORTABLEAPPS-BUILDER-b1r2: opt-in from compiled root launcher only.
const qbzPortableRoot = process.env.QBZ_PORTABLE_DATA_ROOT || '';
if (qbzPortableRoot) {
  // Do not inherit an installed-app migration directive or external environment download override.
  delete process.env.QBZ_MIGRATE_FROM;
  delete process.env.DOWNLOADS_PATH;
  const portablePath = path.resolve(qbzPortableRoot);
  for (const folder of ['Electron', 'Electron/Session', 'Backend', 'Downloads', 'Logs']) {
    fs.mkdirSync(path.join(portablePath, folder), { recursive: true });
  }
  // Apply BEFORE ready, Chromium sessions, single-instance lock or backend startup.
  app.setPath('userData', path.join(portablePath, 'Electron'));
  app.setPath('sessionData', path.join(portablePath, 'Electron', 'Session'));
  app.setAppLogsPath(path.join(portablePath, 'Logs'));
}
'''

def replace_exact(s, a, b, name):
    count=s.count(a)
    if count!=1: raise RuntimeError(f'Upstream {name} pattern count {count}, expected 1. Needs re-audit; refusing silent patch.')
    return s.replace(a,b,1)

def patch(src):
    if MARKER in src: raise RuntimeError('Refusing to patch an already patched upstream file')
    src = replace_exact(src, "const fs = require('fs');\n", "const fs = require('fs');\n"+PROLOGUE, 'Electron entry')
    src = replace_exact(src, "function resolveRuntimeDir() {\n", "function resolveRuntimeDir() {\n  if (qbzPortableRoot) return path.join(path.resolve(qbzPortableRoot), 'Backend');\n", 'backend directory')
    src = replace_exact(src, "function migrateLegacyState(targetDir) {\n", "function migrateLegacyState(targetDir) {\n  if (qbzPortableRoot) return; // Never import an installed profile automatically into portable Data.\n", 'installed profile migration')
    src = replace_exact(src, "process.env.QBZ_DEFAULT_DOWNLOADS_PATH = path.join(app.getPath('downloads'), 'QBZ-Downloader');",
       "process.env.QBZ_DEFAULT_DOWNLOADS_PATH = qbzPortableRoot ? path.join(path.resolve(qbzPortableRoot), 'Downloads') : path.join(app.getPath('downloads'), 'QBZ-Downloader');", 'downloads default')
    src = replace_exact(src, "app.setAppUserModelId('com.ifauze.qbzdownloader');",
         "app.setAppUserModelId(qbzPortableRoot ? 'com.ifauze.qbzdownloader.portable' : 'com.ifauze.qbzdownloader');", 'portable AUMID')
    return src

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('source_dir'); args=ap.parse_args()
    target=Path(args.source_dir)/'electron/main.cjs'
    original=target.read_text(encoding='utf-8')
    changed=patch(original)
    target.write_text(changed,encoding='utf-8',newline='\n')
    assert MARKER in target.read_text(encoding='utf-8')
    print('Applied application-specific before-start portable data adapter:',target)

if __name__=='__main__': main()
