// QBZ Downloader PortableApps Launcher b1r1. MIT. Transparent, non-elevated compiled PE.
// No registry edits, shortcut modifications, broad host cleanup, or subprocess injection.
#include <windows.h>
#include <stdexcept>
#include <shellapi.h>
#include <filesystem>
#include <string>
#include <sstream>
#include <iomanip>
#include <cwctype>
#include <vector>

static void fail(const std::wstring& msg) { MessageBoxW(nullptr, msg.c_str(), L"QBZ Downloader Portable", MB_ICONERROR | MB_OK); }

static std::wstring quote(const std::wstring& s) {
  std::wstring out=L"\"";
  size_t slashes=0;
  for(wchar_t c:s) {
    if(c==L'\\') { ++slashes; continue; }
    if(c==L'"') { out.append(slashes*2+1,L'\\');out+=L'"';slashes=0;continue; }
    out.append(slashes,L'\\');slashes=0;out+=c;
  }
  out.append(slashes*2,L'\\');return out+L"\"";
}
static std::wstring exePath() {
  std::wstring result(32768,L'\0');
  DWORD n=GetModuleFileNameW(nullptr,result.data(),static_cast<DWORD>(result.size()));
  if(!n || n>=result.size()) throw std::runtime_error("Cannot resolve launcher path");
  result.resize(n); return result;
}
static std::wstring mutexName(const std::wstring& p) {
  unsigned long long hash=14695981039346656037ull;
  for(wchar_t c:p) { hash^=static_cast<unsigned long long>(std::towlower(c));hash*=1099511628211ull; }
  std::wstringstream ss;ss<<L"Local\\QBZDownloaderPortable-"<<std::hex<<hash;return ss.str();
}
int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int) {
  try {
    namespace fs=std::filesystem;
    const fs::path root=fs::path(exePath()).parent_path();
    const fs::path appExe=root/L"App"/L"QBZDownloader"/L"QBZ Downloader.exe";
    if(!fs::is_regular_file(appExe)) {fail(L"Missing unpacked application:\n"+appExe.wstring());return 2;}
    const fs::path data=root/L"Data";
    if(fs::exists(data)) {
      const DWORD attr=GetFileAttributesW(data.c_str());
      if(attr==INVALID_FILE_ATTRIBUTES || (attr & FILE_ATTRIBUTE_REPARSE_POINT)) {
        fail(L"Data is a reparse point or inaccessible. Refusing unsafe data redirection.");return 3;
      }
    }
    for(const wchar_t* folder:{L"Electron",L"Electron/Session",L"Backend",L"Downloads",L"Logs"}) fs::create_directories(data/folder);
    auto name=mutexName(root.wstring());
    HANDLE mutex=CreateMutexW(nullptr,TRUE,name.c_str());
    if(!mutex){fail(L"Could not create portable-instance lock.");return 4;}
    if(GetLastError()==ERROR_ALREADY_EXISTS){CloseHandle(mutex);fail(L"This portable folder is already running. Close it before starting again.");return 5;}
    if(!SetEnvironmentVariableW(L"QBZ_PORTABLE_DATA_ROOT",data.c_str())) {ReleaseMutex(mutex);CloseHandle(mutex);fail(L"Cannot initialise portable Data environment.");return 6;}
    SetEnvironmentVariableW(L"QBZ_PORTABLE_INSTANCE",L"1");
    int argc=0;LPWSTR* argv=CommandLineToArgvW(GetCommandLineW(),&argc);
    std::wstring command=quote(appExe.wstring());
    if(argv) {for(int i=1;i<argc;++i){command+=L" "+quote(argv[i]);}LocalFree(argv);}
    std::vector<wchar_t> mutableCommand(command.begin(),command.end());mutableCommand.push_back(L'\0');
    STARTUPINFOW si{};si.cb=sizeof(si);PROCESS_INFORMATION pi{};
    std::wstring work=(root/L"App"/L"QBZDownloader").wstring();
    BOOL ok=CreateProcessW(appExe.c_str(),mutableCommand.data(),nullptr,nullptr,FALSE,0,nullptr,work.c_str(),&si,&pi);
    if(!ok) { auto err=GetLastError();ReleaseMutex(mutex);CloseHandle(mutex);fail(L"Electron failed to start. Windows error: "+std::to_wstring(err));return 7; }
    CloseHandle(pi.hThread);
    WaitForSingleObject(pi.hProcess,INFINITE);
    DWORD code=0;GetExitCodeProcess(pi.hProcess,&code);CloseHandle(pi.hProcess);
    ReleaseMutex(mutex);CloseHandle(mutex);
    return static_cast<int>(code);
  } catch(const std::exception& e) {
    // Exception strings are controlled program errors, not user filenames.
    fail(L"Launcher initialization failed. Check that the portable folder is writable.");return 8;
  }
}
