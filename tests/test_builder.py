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
from build_application import ensure_packaged_sqlite, native_addon_path, sqlite_native_layout, snapshot_sqlite_module

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
    @staticmethod
    def fixture(module, version='13.0.3'):
        """Synthetic PE, only in the test's temporary directory, never shipped."""
        module=Path(module)
        (module/'lib').mkdir(parents=True)
        for name in ['index.js','database.js','binding.js']:
            (module/'lib'/name).write_text('//synthetic test only',encoding='utf-8')
        (module/'package.json').write_text(json.dumps({'name':'better-sqlite3','version':version}),encoding='utf-8')
        binary=native_addon_path(module)
        binary.parent.mkdir(parents=True)
        pe=bytearray(10240)
        pe[:2]=b'MZ'
        struct.pack_into('<I',pe,0x3c,128)
        pe[128:132]=b'PE\x00\x00'
        struct.pack_into('<H',pe,132,0x8664)
        binary.write_bytes(pe)
        return binary

    def test_missing_prebuild_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            module=base/'source/node_modules/better-sqlite3'
            (module/'lib').mkdir(parents=True)
            (module/'lib/binding.js').write_text('// fixture',encoding='utf-8')
            (module/'package.json').write_text(json.dumps({'name':'better-sqlite3','version':'13.0.3'}),encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, 'Missing/implausibly small'):
                snapshot_sqlite_module(base/'source',base/'snapshot')

    def test_v13_prebuild_selected_even_if_legacy_exists(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'better-sqlite3'
            native=self.fixture(root)
            legacy=root/'build/Release/better_sqlite3.node'
            legacy.parent.mkdir(parents=True)
            legacy.write_bytes(b'wrong legacy binary')
            self.assertEqual(native_addon_path(root),native)
            self.assertEqual(sqlite_native_layout(root),('prebuilds/win32-x64.node','13.0.3'))

    def test_v12_legacy_layout_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'better-sqlite3'
            binary=self.fixture(root,version='12.11.2')
            self.assertEqual(binary,native_addon_path(root))
            self.assertEqual(sqlite_native_layout(root)[0],'build/Release/better_sqlite3.node')

    def test_verified_snapshot_repairs_missing_packaged_native(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            root=base/'source/node_modules/better-sqlite3'
            binary=self.fixture(root)
            snap=snapshot_sqlite_module(base/'source',base/'snapshot')
            # Mimic packaging having discarded source module. Must rely on snapshot.
            import shutil
            shutil.rmtree(root)
            packaged=base/'packaged'
            dest=ensure_packaged_sqlite(snap,packaged)
            self.assertEqual(dest.read_bytes(),binary.read_bytes() if binary.exists() else (snap/'prebuilds/win32-x64.node').read_bytes())
            self.assertEqual(dest.relative_to(packaged).as_posix(),
                             'resources/app/node_modules/better-sqlite3/prebuilds/win32-x64.node')
            dest.write_bytes(b'corruption'+b'0'*10240)
            with self.assertRaisesRegex(RuntimeError, 'not a Windows PE'):
                ensure_packaged_sqlite(snap,packaged)

    def test_valid_but_different_native_addon_refused(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            root=base/'source/node_modules/better-sqlite3'
            self.fixture(root)
            snap=snapshot_sqlite_module(base/'source',base/'snapshot')
            packed=base/'packaged'
            ensure_packaged_sqlite(snap,packed)
            native=packed/'resources/app/node_modules/better-sqlite3/prebuilds/win32-x64.node'
            b=bytearray(native.read_bytes()); b[500]=1
            native.write_bytes(b)
            with self.assertRaisesRegex(RuntimeError, 'differs from verified'):
                ensure_packaged_sqlite(snap,packed)

    def test_anchor_drift_is_fatal(self):
        with self.assertRaises(RuntimeError):patch('const fs = require(\'fs\');\n')

if __name__ == '__main__':unittest.main()
