#!/usr/bin/env python3
"""Carry app's direct dependency license notices; do not claim exhaustive license coverage."""
import json
from pathlib import Path

src=Path('work/upstream')
root=json.loads((src/'package.json').read_text(encoding='utf-8'))
output=Path('work/stage/QBZDownloaderPortable/Other/Source/DEPENDENCY-NOTICES.txt')
lines=['QBZ Downloader b1r3 direct runtime dependency notices',
       'This is not an exhaustive compliance review of transitive Electron/npm dependencies.',
       'Check the actual packaged dependencies and applicable licenses before public redistribution.','']
for name,requested in sorted(root['dependencies'].items()):
    loc=src/'node_modules'/name
    desc=loc/'package.json'
    if not desc.is_file():raise RuntimeError(f'Missing installed dependency package: {name}')
    pkg=json.loads(desc.read_text(encoding='utf-8'))
    lines.append(f"{name} version {pkg.get('version','?')} license field {pkg.get('license','UNSPECIFIED')}")
    candidates=sorted([x for x in loc.iterdir() if x.is_file() and x.name.lower().startswith(('license','licence','copying'))])
    if candidates:
        f=candidates[0]
        if f.stat().st_size <= 250000:
            try:
                lines.append('--- License text from '+str(f.relative_to(src))+' ---')
                lines.append(f.read_text(encoding='utf-8',errors='replace'))
                lines.append('--- End ---\n')
            except OSError as err:
                lines.append(f'Unable to read license text: {err}')
    else:
        lines.append('NOTICE: no direct LICENSE file located at this package root; audit before redistribution.\n')
lines.append('Media helper licenses: FFmpeg (https://ffmpeg.org/legal.html); Chromaprint (https://github.com/acoustid/chromaprint).')
output.write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('Recorded direct runtime package license notices:',output)
