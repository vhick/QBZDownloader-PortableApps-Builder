"""Deterministic contract regression tests — these do NOT emulate Windows runtime."""
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from patch_upstream import patch,MARKER
from resolve_upstream import VERSION,FULL_SHA

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
    def test_anchor_drift_is_fatal(self):
        with self.assertRaises(RuntimeError):patch('const fs = require(\'fs\');\n')

if __name__ == '__main__':unittest.main()
