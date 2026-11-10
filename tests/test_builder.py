"""Deterministic contract regression tests — these do NOT emulate Windows runtime."""
import sys
import json
import struct
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from patch_upstream import patch,MARKER
from resolve_upstream import VERSION,FULL_SHA
from build_application import ensure_packaged_sqlite, native_addon_path

class BuilderTests(unittest.TestCase):
    def test_numeric_stable_version_validation(self):
        self.assertTrue(VERSION.fullmatch('v5.6.3'))
        self.assertFalse(VERSION.fullmatch('v5.6.3-rc1'))
        self.assertGreater(tuple(map(int,VERSION.fullmatch('v5.10.0').groups())),
                           tuple(map(int,VERSION.fullmatch('v5.9.9').groups())))
        self.assertTrue(FULL_SHA.fullmatch('a'*40))
        self.assertFalse(FULL_SHA.fullmatch('a'*12))
    def test_portable_adapter_exact_sources_and_no_second_patch(self):
        fragment='\n'.join([
            "const { app } = require('electron');",
            "const path = require('path');",
            "const fs = require('fs');",
            "function resolveRuntimeDir() {",
            "function migrateLegacyState(targetDir) {",
            "  if (process.env.PORTABLE_EXECUTABLE_DIR) { return ''; }",
            "}",
            "process.env.QBZ_DEFAULT_DOWNLOADS_PATH = path.join(app.getPath('downloads'), 'QBZ-Downloader');",
            "app.setAppUserModelId('com.ifauze.qbzdownloader');",
        ])
        result=patch(fragment)
        self.assertIn(MARKER,result)
        self.assertLess(result.index("app.setPath('userData'"),result.index('function resolveRuntimeDir()'))
        self.assertIn('com.ifauze.qbzdownloader.portable',result)
        with self.assertRaises(RuntimeError):patch(result)
    def test_missing_rebuilt_module_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            with self.assertRaisesRegex(RuntimeError, 'Missing/implausibly small'):
                ensure_packaged_sqlite(base/'source',base/'packaged')

    def test_rebuilt_module_is_restored_only_from_source_module(self):
        # A synthetic PE fixture is generated in a temporary directory only;
        # it is not an executable shipped with the builder or release.
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            root=base/'source/node_modules/better-sqlite3'
            binary=native_addon_path(root)
            binary.parent.mkdir(parents=True)
            pe=bytearray(10240)
            pe[0:2]=b'MZ'
            struct.pack_into('<I',pe,0x3c,128)
            pe[128:132]=b'PE\x00\x00'
            struct.pack_into('<H',pe,132,0x8664)
            binary.write_bytes(pe)
            (root/'lib').mkdir()
            (root/'lib/database.js').write_text('module.exports = 1;',encoding='utf-8')
            (root/'package.json').write_text(json.dumps({'version':'13.0.3'}),encoding='utf-8')
            packaged=base/'packaged'
            dest=ensure_packaged_sqlite(base/'source',packaged)
            self.assertEqual(dest.read_bytes(),binary.read_bytes())
            self.assertTrue((dest.parents[2]/'lib/database.js').is_file())
            dest.write_bytes(b'corruption'+b'0'*10240)
            with self.assertRaisesRegex(RuntimeError, 'not a Windows PE'):
                ensure_packaged_sqlite(base/'source',packaged)

    def test_anchor_drift_is_fatal(self):
        with self.assertRaises(RuntimeError):patch('const fs = require(\'fs\');\n')

if __name__ == '__main__':unittest.main()
