#!/usr/bin/env python3
"""Local static builder-kit verification; no false runtime-pass claims."""
import ast
from pathlib import Path
root=Path(__file__).resolve().parents[1]
for file in (root/'scripts').glob('*.py'):
    ast.parse(file.read_text(encoding='utf-8'),filename=str(file))
for required in ['.github/workflows/build.yml','.github/workflows/package-only.yml','launcher/main.cpp',
                 'launcher/CMakeLists.txt','scripts/patch_upstream.py','README.md','docs/AUDIT.md']:
    if not (root/required).is_file():raise AssertionError('Missing '+required)
source=(root/'launcher/main.cpp').read_text(encoding='utf-8')
assert 'CreateProcessW' in source and 'GetModuleFileNameW' in source
patch=(root/'scripts/patch_upstream.py').read_text(encoding='utf-8')
assert "'sessionData'" in patch and 'QBZ_DEFAULT_DOWNLOADS_PATH' in patch
assert 'TraceGuard' not in source and 'ShellGuard' not in source
print('STATIC-VALIDATED: builder-kit Python parses, files, launcher design and adapter guards')
