# QBZ PortableApps builder b1r1 troubleshooting

**NO STABLE UPSTREAM TAGS FOUND** — This is an intentional source-provenance stop. Upstream GitHub currently appears to have no published Releases. Check whether stable Git tags exist. If none, explicitly select the build workflow's **allow_unreleased_snapshot=true** to pin the currently published GitHub HEAD commit, or supply a full 40-character reviewed upstream commit SHA with its exact package version. The HEAD option is an *unreleased snapshot*, not an official stable release.

**GitHub API 403 / rate limit / 401** — Do not fall back to random `main`. Run again with the normal GitHub Actions token after the permission/rate issue is resolved. `contents: write` is required for own-repository publication, never another repository.

**Upstream source pattern changed** — `patch_upstream.py` intentionally fails. Compare actual `electron/main.cjs` changes and adapt the source patch only after inspecting modified APIs. Never replace an anchor with a broad regex or patch a different unknown file.

**better-sqlite3 crashes or `.node` ABI error** — Verify `npm run desktop:rebuild` succeeded for exact Electron version and x64. The upstream script rebuilds `better-sqlite3` before electron-builder. Do not omit it.

**FFmpeg/fpcalc missing** — The kit halts instead of producing a functionally reduced ZIP. Review upstream `scripts/bundle-binaries.cjs`; it uses npm-installed ffmpeg-static and pinned-hash official Chromaprint 1.5.1 Windows assets. Fix network/download failures rather than silently omitting the helper.

**MSVC/CMake launcher build fails** — The kit tries Visual Studio 2022, then 2026 hosted runner generators. Review the CMake log for missing Visual C++ components. The root EXE is intentionally compiled from C++ rather than substituting CMD/PowerShell.

**Package builder: `running-exe must be relative Windows .exe`** — This pinned action's validator requires backslashes, not forward slashes. The included workflow uses `App\QBZDownloader\QBZ Downloader.exe` as the relative path. Keep that exact syntax.

**Installer fails while ZIP works** — The main workflow preserves a **ZIP-only** release with its own suffix and fails the job visibly. Fix the installer dependency issue, then run **Package Installer from Validated Release ZIP** with the prior publisher-owned tag. The second workflow verifies the publisher SHA256SUMS before using the shared action. It does not rebuild upstream source.

**`Qbz Downloader.exe` or resources missing** — Do not manually rename any EXE. Verify the source build produced `portable-unpacked/win-unpacked/QBZ Downloader.exe`, resources/app.asar and bundled helpers. If electron-builder changes output names, update `scripts/build_application.py`, `prepare_stage.py`, and launcher after source inspection.

**App starts when opened via App but host AppData is modified** — Direct launching the internal Electron binary bypasses the compiled root launcher. Use `QBZDownloaderPortable.exe` at package root. If traces remain from normal root launch, record exact process/path/ownership, then inspect them before proposing cleanup.

**Credential or library errors after moving PC** — Keep `Data/Backend/data/.secret.key` together with its SQLite files. Windows safeStorage/DPAPI encryption may still be user/machine-bound; reauthenticate using your legitimate account if required. Do not copy installed-app secrets over existing portable settings without an explicit verified migration.

**Duplicate launcher says already running** — Close the original root launcher and Electron process fully before starting again; the mutex is scoped to one portable folder. A hung Electron descendant is a manual runtime issue, not justification for force-deleting profile files.

**Toast notifications do not activate** — Electron's portable AUMID is distinct from the installed one. Windows may need a registered Start Menu identity for click-to-open, which this version does not create by default because no safe source-evidenced registration lifecycle was verified. Document the result; do not delete a user or installed application shortcut to paper over it.

**Win installer missing legacy files** — Verify real installer install/reinstall in disposable folders. Metadata and PE signature alone cannot prove removal of old App binary files. Never test `Data` preservation with your only database copy.
