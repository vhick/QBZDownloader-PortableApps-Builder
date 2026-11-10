# QBZ Downloader b1r2 — source and portability findings

**Audit date:** 2026-11-10. **Resolved architecture:** PORTABLEAPPS (on-demand Electron downloader with local web dashboard/backend, Windows x64). **Selected deliverable:** ZIP + independently generated community NSIS installer. NATIVE not requested and not built.

## Evidenced upstream facts

- Repository: `https://github.com/ifauzeee/QBZ-Downloader` (MIT at observed `main`). On inspection, `package.json` on `main` reported **5.6.3**, Electron **^44.5.1**, Node **>=22**, TypeScript backend, React/Vite client, `better-sqlite3` and `electron-builder` dependencies. `package-lock.json` and `client/package-lock.json` are both present. Package scripts include `build:full`, `desktop:rebuild`, and `bundle-binaries`.
- `electron/main.cjs` is the actual Electron main process. It uses an Electron `BrowserWindow`, starts the backend via a dynamic import of `dist/index.js`, uses `app.requestSingleInstanceLock()`, calls `app.setAppUserModelId('com.ifauze.qbzdownloader')`, and forwards backend notifications to Electron `Notification`.
- The same file's `resolveRuntimeDir()` normally uses `app.getPath('userData')` for packaged apps. Its existing electron-builder portable mode uses `PORTABLE_EXECUTABLE_DIR/QBZ-Data`. It has optional `QBZ_MIGRATE_FROM`; the local runtime contains a `data/qbz.db` SQLite database, the important `data/.secret.key` encryption key and other state. Default downloads are resolved by `QBZ_DEFAULT_DOWNLOADS_PATH`; users can save custom download paths.
- The source build helper `scripts/rebuild-electron-native.cjs` forces Electron ABI rebuild of `better-sqlite3`. `scripts/bundle-binaries.cjs` copies FFmpeg from npm and fetches pinned-hash `fpcalc` from official Chromaprint release. It labels helper download failures nonfatal; **this builder tightens that** and fails packaging if either helper is missing because quality analysis/format conversion should not be silently removed.
- The GitHub Releases page was inspected and displayed **no published releases**. The tag API could not be directly read in this environment, and candidate `v5.6.3` source ref returned 404. **Do not assert a stable v5.6.3 tag exists.** The builder queries live GitHub tags and Releases, refuses unverified `main`, and offers an explicitly opted-in immutable snapshot fallback (with a prominently marked non-stable provenance).
- No actual Windows GUI sessions, ProcMon traces, notification activation tests or installation tests were conducted in the authoring environment. Source inspection is not proof of no host traces.

## Mode-specific source findings

| Finding | Source evidence / confidence | File/registry path | Responsible component | NATIVE remedy | PORTABLEAPPS remedy | Data safety | Functionality tradeoff | Test | Limitation |
|---|---|---|---|---|---|---|---|---|---|
| Packaged backend runtime | `electron/main.cjs:resolveRuntimeDir` **SOURCE-INSPECTED** | Normally Electron `userData`; portable legacy `QBZ-Data` | Application | Not in selected mode | Patch to `Data/Backend` from launcher env before backend boot | Includes `data/qbz.db`, `data/.secret.key`, settings/history | None expected | Restart, SQLite contents and settings | App migrations must be tested |
| Chromium/Electron profile | Electron documented `userData` and session profile **SOURCE-INSPECTED + inferred framework caches** | Usually `%APPDATA%` / profile `userData` | Electron/Chromium | Not in selected mode | `app.setPath('userData')` and `app.setPath('sessionData')` pre-ready into `Data/Electron` | Leaves installed profile untouched | Browser cache stays on USB | Profile/cache persistence; external scans | Some OS-managed caches not redirectable |
| Logs | Electron `app.setAppLogsPath` **inferred API**, pinned runtime version | Electron log directory | Electron | Not in selected mode | Direct `Data/Logs` path before ready | No log harvesting | None | Logger location on first/second run | Dependency-specific logs need observation |
| Downloads | `QBZ_DEFAULT_DOWNLOADS_PATH` / Settings **SOURCE-INSPECTED** | Normally Downloads/QBZ-Downloader; user custom location | Application/user choice | Not in selected mode | New profile defaults `Data/Downloads`; keep custom paths intact | No personal media moved or deleted | Existing custom path can remain external | New download; custom path; relocation | Cannot safely rewrite arbitrary saved library paths |
| SQLite and credentials | `data/qbz.db`, `.secret.key` in migration logic and README encryption **SOURCE-INSPECTED** | `Data/Backend/data/` | Application and `safeStorage` | Not in selected mode | Retain DB/WAL/SHM/key under Data, do not copy installed profile | Always backup database+key together | Different Windows account may need reauthentication | restart, rollback, account move | Electron/DPAPI protected secrets may be device/user-bound |
| Single-instance behavior | `app.requestSingleInstanceLock` **SOURCE-INSPECTED** | Profile instance lock; process handle | Electron | Not in selected mode | Compiled root launcher uses per-folder mutex, waits for Electron main process | Prevent concurrent launches from same root | Duplicate launch shows dialog | double launch; restart | Child shutdown requires real Windows observation |
| Notifications/AUMID | `app.setAppUserModelId` / `Notification` **SOURCE-INSPECTED** | AUMID `com.ifauze.qbzdownloader`; Windows notifications | Application+Windows | Not in selected mode | Distinct `.portable` AUMID; preserve native Notification calls; no registry/shortcut sweeping | No installed app CLSID/shortcuts touched | Toast clicks may require Windows shortcut identity | toast and click-to-open | Not guaranteed without per-user registration; not yet verified |
| Registry, Start Menu, services | No unconditional code path established from reviewed main process **source-limited inference** | Unconfirmed | Installer, Windows shell, dependencies | Not in selected mode | No broad TraceGuard/ShellGuard; manual before/after Windows observation | Avoid collateral loss and installed-app damage | Residual shell-managed entries may persist | compare snapshots with ProcMon/Regshot | Full source/dependency behavior not yet exhaustively proven |
| FFmpeg / fpcalc | `scripts/bundle-binaries.cjs` **SOURCE-INSPECTED** | Packaged `resources/bin/win32-x64` | Dependencies | Not in selected mode | Bundled with checksum validation by upstream fpcalc retrieval, fail build when absent | No host download prerequisite | Larger ZIP | PE and file presence; real conversion | Runtime function tests still required |
| Temporary files | Some tools/libraries may use `os.tmpdir` **inferred, not source-attributed individually** | `%TEMP%` | Dependencies | Not in selected mode | Do **not** redirect global TEMP or sweep it; require targeted observation | Host data never bulk-deleted | Standard transient temp files possible | ProcMon scoped to process and children | Persistent app-owned TEMP traces unknown |
| Self-updates/shell integration | No independently proven auto-update or COM registration path **NOT YET VERIFIED** | Unknown | Upstream/dependencies | Not in selected mode | No speculative modifications; installed-app coexistence manual test | Preserves unrelated entries | May leave Windows-managed state | interactive acceptance | Do not promise zero host activity |

## Source adapter: intentionally narrow

File: `scripts/patch_upstream.py`; target: `electron/main.cjs`. It asserts every expected upstream anchor occurs exactly once and **fails the build on drift** rather than silently patching the wrong revision.

1. Insert a pre-start guarded block immediately after `require('fs')`. When `QBZ_PORTABLE_DATA_ROOT` is set by the compiled launcher, create `Data` subfolders and call `app.setPath('userData', ...)`, `app.setPath('sessionData', ...)`, and `app.setAppLogsPath(...)` before `whenReady()`, single-instance lock or backend load.
2. Use `Data/Backend` at the start of `resolveRuntimeDir()`.
3. Use `Data/Downloads` for the default desktop path; do **not** overwrite existing explicit download settings.
4. For a portable process, suppress an inherited `QBZ_MIGRATE_FROM` and `DOWNLOADS_PATH` environment override, and bypass the installed-profile migration routine. This prevents unintended import from an existing installed QBZ application.
5. Change the AUMID to `com.ifauze.qbzdownloader.portable` **only** for the portable build.

Launcher source: `launcher/main.cpp` and `launcher/CMakeLists.txt`. Windows PE compiles from C++17, resolves its own executable folder, creates Data, checks packaged app presence, acquires path-specific mutex, provides a per-process environment override, starts `App/QBZDownloader/QBZ Downloader.exe` without shell elevation, forwards Unicode-quoted CLI args, waits for the primary process to exit, and does not modify registry/shortcuts. An application EXE launched directly is **not** promised to be portable.

**Why no TraceGuard/ShellGuard?** The reviewed application gives us supported direct profile redirection and a source patch. A source-evidenced residual path requiring harvesting has not been established. Fabricating an allowlist or blindly sweeping AppData/registry is both dangerous and noncompliant. If real Windows process traces show an attributable persistent path, add a narrow, transactional adapter only after independent proof; never move an installed user's data on name similarity alone. Empty-directory recovery tests become applicable only for a newly evidenced allowlisted TraceGuard path.

## Build and dependency provenance

- Source resolution: GitHub Releases API (published stable only) and `git ls-remote --tags`, numeric semver ordering; checkout exact verified immutable tag commit, or explicit full SHA, or *explicitly opted-in* untagged HEAD snapshot. Snapshot is not mislabeled stable.
- Release API errors: non-success HTTP response is a hard error. No automatic fallback on 401/403/429/5xx; a valid empty releases array can still lead to verified stable tags.
- Two separate package-lock SHA-256 values are recorded in embedded `build-identity.json`; `npm ci` uses locks. Upstream `sync-version` may rewrite lockfile formatting as part of the upstream build; the identity records the checkout's source bytes.
- The real application is source-built on hosted `windows-latest`, Node 22; Electron `better-sqlite3` is rebuilt for exact Electron ABI before packaging.
- Electron-builder output is an unpacked Windows application (`win-unpacked`) configured to invoke `electron/main.cjs`; no electron-builder NSIS/portable EXE is substituted for the root launcher.
- `win32-x64/ffmpeg.exe` and `fpcalc.exe` must both be present. Chromaprint's archive SHA-256 pin is in reviewed upstream script. npm package integrity is enforced by lockfiles.
- Shared package builder `@v1.0.0` action definition **SOURCE-INSPECTED** including `scripts/build.ps1` and `scripts/common.ps1`. Its `running-exe` validator requires backslashes.
- Release publisher `@v1.1.1` action and `scripts/publish.py` **SOURCE-INSPECTED**. Requires `.zip` / `.paf.exe`, validates PE signatures and ZIP format, writes `SHA256SUMS.txt`, and checks managed release identity. It cannot assert GUI runtime portability.
- Shared-action immutable commit SHAs have **not** been verified in this environment; tags are used exactly as requested. For production hardening, replace tags with audited SHAs only after separate verification.

## Security and licensing limits

- Upstream license: MIT at observed source checkout; the workflow carries original LICENSE and a source build record. npm/Electron/FFmpeg/Chromaprint dependencies have independent licenses and notices that a redistributor must review. The builder does not claim all dependency license obligations have been exhaustively audited.
- No upstream developer asset is repackaged from a third-party mirror. No credential collection or bundled credentials. Use only legitimate Qobuz service access and respect media rights.
- A bundled unsigned PE is not a signed PE. Neither publisher nor custom NSIS action provides official PortableApps certification or AV guarantees.
- Localhost backend port, firewall and notification activity must be tested with actual Windows processes. Do not misinterpret closed ports or absence of a shortcut as proof of desktop functionality.

## Evidence status at kit authoring

| Stage | Evidence/status | Meaning |
|---|---|---|
| Upstream core `electron/main.cjs` / npm build scripts | **SOURCE-INSPECTED** | Specific read paths/API calls verified on observed main |
| Pinned shared action definitions | **SOURCE-INSPECTED** | Inputs and implementation read; commit SHAs unverified |
| Builder scripts Python syntax/layout | **STATIC-VALIDATED** if `scripts/check_kit.py` passes | Syntax and structure, not Windows function |
| Source stable tag and exact commit | **NOT YET VERIFIED** | Determined at hosted-run time; none invented |
| Electron compilation and native `better-sqlite3` | **NOT YET VERIFIED** | Needs first hosted Windows run |
| Root native C++ PE compilation | **NOT YET VERIFIED** | Needs first hosted Windows run |
| PortableApps ZIP generation/static validation | **NOT YET VERIFIED** | Needs first hosted Windows run |
| Direct native mode | **NOT APPLICABLE** | NATIVE not selected |
| Portable Electron data containment | **NOT YET VERIFIED** | Requires profile and host before/after observation |
| TraceGuard empty dirs / registry recovery | **NOT APPLICABLE** | No evidenced allowlisted residual state; no harvesting |
| ShellGuard shortcut cleanup | **NOT APPLICABLE** | No attributable runtime entries established, so no destructive collector |
| Real Windows notifications and activation | **NOT YET VERIFIED** | AUMID modification needs real desktop acceptance |
| Installer construction/static checks | **NOT YET VERIFIED** | Hosted Windows run required |
| Actual installer install/reinstall/data preservation | **NOT YET VERIFIED** | Manual Windows test required |
| Publisher release creation | **NOT YET VERIFIED** | User must run GitHub workflow |
| User-reported Windows functionality | **NOT YET VERIFIED** | No user confirmation at this revision |

## b1r2 observed CI feedback and corrective design

- **WINDOWS-COMPILED (b1r1 log 115928022622):** Electron 44.10.0 app was created, upstream `desktop:rebuild` reported success for better-sqlite3, and the compiled C++ root launcher succeeded using Visual Studio 2026.
- **FAILED (b1r1):** staging validation required one `better_sqlite3.node` under `app.asar.unpacked`; it found a count other than one. The uploaded logs did not show the packaged directory contents, so it is not proven whether the native binary was missing or stored elsewhere.
- **b1r2 fix (static design, not yet Windows tested):** use source-built `asar: false` (supported by electron-builder v26), verify the rebuilt x64 native module and source version, restore this exact locked source module into `resources/app/node_modules/better-sqlite3` if omitted from the packaged tree, reject hash mismatches, and require a headless Electron SQLite query before staging. This is a packaging-only remedy and performs no host-data harvesting.
- **GUI/manual acceptance remains pending:** Native module smoke tests do not validate the dashboard, notification activation, Qobuz login, download queue, or installed-app coexistence.
