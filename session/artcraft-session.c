/* artcraft-session.exe: what the ArtCraft desktop does once it is up.
 *
 * The edition's library entry (games/artcraft/game.json) starts the Mihawk desktop session in the artcraft prefix
 * with this program as its argument: Explorer, the session's root, runs it with CreateProcess once the desktop is
 * drawn (Wine's manage_desktop; Mihawk patch 0996). It does five things, then exits:
 *
 *   1. imports trust.reg (regedit /S) at every start: the code-signing root and the WinTrust policy the launcher's
 *      self-update needs (artcraft_ps5/regfile.py says what each value does);
 *   2. imports defaults.reg (wallpaper, Start pins) once per version of those defaults (defaults_id, remembered in
 *      HKCU\Software\ArtCraft\Session), so what the user changes afterwards stays, and applies the wallpaper then
 *      (SPI_SETDESKWALLPAPER), as Explorer has already painted Mihawk's on a new prefix;
 *   3. keeps one desktop shortcut per installed program in [shortcuts] (a program the launcher installs later gets
 *      one at the next session; a shortcut it made whose program is gone is removed; any other file is the user's);
 *   4. sets [environment] (WGPU_BACKEND=...) so the launcher and every app it starts inherit it;
 *   5. starts ArtCraft Launcher. It is a single-instance app: a second start, when Explorer comes back after a
 *      full-screen program and runs this again, only shows its window.
 *
 * Everything it does is logged (session.log beside session.ini), as there is no console to read.
 *
 *   artcraft-session.exe [--config FILE]                  the session start
 *   artcraft-session.exe --check-signature FILE           WinVerifyTrust exactly as the launcher's self-update calls
 *                                                         it (verifysign 1.0.1 defaults); exit 0 when trusted
 *
 * SPDX-License-Identifier: GPL-3.0-or-later */
#define COBJMACROS
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#include <shlobj.h>
#include <shlwapi.h>
#include <softpub.h>
#include <stdarg.h>
#include <stdio.h>
#include <wintrust.h>

#ifndef WTD_DISABLE_MD2_MD4
#define WTD_DISABLE_MD2_MD4 0x00002000
#endif

#define SESSION_MARK L"ArtCraft for PS5"   /* the description of every shortcut this program owns */
#define SESSION_KEY L"Software\\ArtCraft\\Session"
#define LOG_LIMIT (512 * 1024)
#define SECTION_MAX 32768

static WCHAR config_path[MAX_PATH], log_path[MAX_PATH];

static void say(const char *format, ...)
{
    char line[2048];
    SYSTEMTIME now;
    va_list args;
    int n;
    GetLocalTime(&now);
    n = snprintf(line, sizeof(line), "%04u-%02u-%02u %02u:%02u:%02u ", now.wYear, now.wMonth, now.wDay, now.wHour,
                 now.wMinute, now.wSecond);
    va_start(args, format);
    vsnprintf(line + n, sizeof(line) - n - 2, format, args);
    va_end(args);
    lstrcatA(line, "\r\n");
    fputs(line, stdout);
    fflush(stdout);
    if (!log_path[0]) return;
    HANDLE file = CreateFileW(log_path, FILE_APPEND_DATA, FILE_SHARE_READ, NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) return;
    DWORD written;
    WriteFile(file, line, lstrlenA(line), &written, NULL);
    CloseHandle(file);
}

/* UTF-8 of a wide string, for the log. */
static const char *u8(const WCHAR *text)
{
    static char buffers[4][MAX_PATH * 3];
    static int next;
    char *out = buffers[next++ % 4];
    if (!WideCharToMultiByte(CP_UTF8, 0, text ? text : L"", -1, out, MAX_PATH * 3, NULL, NULL)) lstrcpyA(out, "?");
    return out;
}

static BOOL exists(const WCHAR *path)
{
    return GetFileAttributesW(path) != INVALID_FILE_ATTRIBUTES;
}

static void ini(const WCHAR *key, const WCHAR *fallback, WCHAR *out, DWORD size)
{
    GetPrivateProfileStringW(L"session", key, fallback, out, size, config_path);
}

static void open_log(void)
{
    WCHAR folder[MAX_PATH], old[MAX_PATH], fallback[MAX_PATH];
    WIN32_FILE_ATTRIBUTE_DATA data;
    lstrcpyW(folder, config_path);
    PathRemoveFileSpecW(folder);
    PathCombineW(fallback, folder, L"logs\\session.log");
    ini(L"log", fallback, log_path, MAX_PATH);
    lstrcpyW(folder, log_path);
    PathRemoveFileSpecW(folder);
    SHCreateDirectoryExW(NULL, folder, NULL);
    if (GetFileAttributesExW(log_path, GetFileExInfoStandard, &data) && data.nFileSizeLow > LOG_LIMIT)
    {
        lstrcpyW(old, log_path);
        lstrcatW(old, L".1");
        MoveFileExW(log_path, old, MOVEFILE_REPLACE_EXISTING);
    }
}

/* Runs a command line and waits for it; its exit code, or -1. */
static long run_and_wait(WCHAR *command, DWORD timeout_ms)
{
    STARTUPINFOW startup;
    PROCESS_INFORMATION process;
    DWORD code = (DWORD)-1;
    ZeroMemory(&startup, sizeof(startup));
    startup.cb = sizeof(startup);
    if (!CreateProcessW(NULL, command, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, NULL, &startup, &process))
        return -1;
    if (WaitForSingleObject(process.hProcess, timeout_ms) == WAIT_OBJECT_0) GetExitCodeProcess(process.hProcess, &code);
    else say("  still running after %lu ms; not waiting longer", timeout_ms);
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return (long)code;
}

static long import_reg(const WCHAR *file)
{
    WCHAR command[MAX_PATH * 2 + 64], windows[MAX_PATH];
    GetWindowsDirectoryW(windows, MAX_PATH);
    wsprintfW(command, L"\"%s\\regedit.exe\" /S \"%s\"", windows, file);
    return run_and_wait(command, 30000);
}

static void import_trust(void)
{
    WCHAR file[MAX_PATH];
    ini(L"trust", L"", file, MAX_PATH);
    if (!file[0] || !exists(file)) { say("trust: no file (%s)", u8(file)); return; }
    say("trust: regedit /S %s: exit %ld", u8(file), import_reg(file));
}

/* TRUE when the defaults went in at this start. */
static BOOL import_defaults(void)
{
    WCHAR file[MAX_PATH], id[128], applied[128] = {0};
    DWORD size = sizeof(applied);
    long code;
    ini(L"defaults", L"", file, MAX_PATH);
    ini(L"defaults_id", L"", id, ARRAYSIZE(id));
    if (!file[0] || !id[0] || !exists(file)) { say("defaults: none (%s)", u8(file)); return FALSE; }
    RegGetValueW(HKEY_CURRENT_USER, SESSION_KEY, L"DefaultsApplied", RRF_RT_REG_SZ, NULL, applied, &size);
    if (!lstrcmpW(applied, id)) { say("defaults: %s already applied; the user's choices stay", u8(id)); return FALSE; }
    code = import_reg(file);
    say("defaults: regedit /S %s: exit %ld", u8(file), code);
    if (code != 0) return FALSE;
    RegSetKeyValueW(HKEY_CURRENT_USER, SESSION_KEY, L"DefaultsApplied", REG_SZ, id, (lstrlenW(id) + 1) * sizeof(WCHAR));
    return TRUE;
}

static void apply_wallpaper(void)
{
    WCHAR wanted[MAX_PATH], current[MAX_PATH] = {0};
    ini(L"wallpaper", L"", wanted, MAX_PATH);
    if (!wanted[0]) return;
    if (!exists(wanted)) { say("wallpaper: %s is missing; leaving the desktop as it is", u8(wanted)); return; }
    SystemParametersInfoW(SPI_GETDESKWALLPAPER, MAX_PATH, current, 0);
    if (!lstrcmpiW(current, wanted)) { say("wallpaper: already %s", u8(wanted)); return; }
    BOOL ok = SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, wanted, SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE);
    say("wallpaper: %s -> %s: %s", u8(current), u8(wanted), ok ? "set" : "failed");
}

/* Whether the shortcut at `link` is one of ours, and where it points. */
static BOOL read_link(const WCHAR *link, WCHAR *target, WCHAR *description)
{
    IShellLinkW *shell_link;
    IPersistFile *file;
    BOOL ok = FALSE;
    target[0] = description[0] = 0;
    if (FAILED(CoCreateInstance(&CLSID_ShellLink, NULL, CLSCTX_INPROC_SERVER, &IID_IShellLinkW, (void **)&shell_link)))
        return FALSE;
    if (SUCCEEDED(IShellLinkW_QueryInterface(shell_link, &IID_IPersistFile, (void **)&file)))
    {
        if (SUCCEEDED(IPersistFile_Load(file, link, STGM_READ)))
        {
            IShellLinkW_GetPath(shell_link, target, MAX_PATH, NULL, 0);
            IShellLinkW_GetDescription(shell_link, description, MAX_PATH);
            ok = TRUE;
        }
        IPersistFile_Release(file);
    }
    IShellLinkW_Release(shell_link);
    return ok;
}

static BOOL write_link(const WCHAR *link, const WCHAR *target)
{
    IShellLinkW *shell_link;
    IPersistFile *file;
    WCHAR folder[MAX_PATH];
    HRESULT hr;
    lstrcpyW(folder, target);
    PathRemoveFileSpecW(folder);
    if (FAILED(CoCreateInstance(&CLSID_ShellLink, NULL, CLSCTX_INPROC_SERVER, &IID_IShellLinkW, (void **)&shell_link)))
        return FALSE;
    IShellLinkW_SetPath(shell_link, target);
    IShellLinkW_SetWorkingDirectory(shell_link, folder);
    IShellLinkW_SetIconLocation(shell_link, target, 0);
    IShellLinkW_SetDescription(shell_link, SESSION_MARK);
    hr = IShellLinkW_QueryInterface(shell_link, &IID_IPersistFile, (void **)&file);
    if (SUCCEEDED(hr))
    {
        hr = IPersistFile_Save(file, link, TRUE);
        IPersistFile_Release(file);
    }
    IShellLinkW_Release(shell_link);
    return SUCCEEDED(hr);
}

static void sync_shortcuts(void)
{
    static WCHAR section[SECTION_MAX];
    WCHAR folder[MAX_PATH], link[MAX_PATH], target[MAX_PATH], description[MAX_PATH];
    unsigned made = 0, kept = 0, removed = 0, absent = 0;
    ini(L"desktop", L"", folder, MAX_PATH);
    if (!folder[0]) return;
    SHCreateDirectoryExW(NULL, folder, NULL);
    GetPrivateProfileSectionW(L"shortcuts", section, SECTION_MAX, config_path);
    for (WCHAR *entry = section; *entry; entry += lstrlenW(entry) + 1)
    {
        WCHAR *equals = StrChrW(entry, L'=');
        if (!equals || equals == entry) continue;
        *equals = 0;
        const WCHAR *name = entry, *program = equals + 1;
        if (!PathCombineW(link, folder, name) || lstrlenW(link) + 4 >= MAX_PATH) continue;
        lstrcatW(link, L".lnk");
        BOOL ours = read_link(link, target, description) && !lstrcmpW(description, SESSION_MARK);
        if (!exists(program))
        {
            if (ours && DeleteFileW(link)) ++removed;
            else ++absent;
        }
        else if (ours && !lstrcmpiW(target, program)) ++kept;
        else if (exists(link) && !ours) say("shortcuts: %s is the user's own; left alone", u8(link));
        else if (write_link(link, program)) ++made;
        else say("shortcuts: could not write %s", u8(link));
        *equals = L'=';
    }
    say("shortcuts: %u written, %u current, %u removed, %u programs not installed", made, kept, removed, absent);
}

static void set_environment(void)
{
    static WCHAR section[SECTION_MAX];
    GetPrivateProfileSectionW(L"environment", section, SECTION_MAX, config_path);
    for (WCHAR *entry = section; *entry; entry += lstrlenW(entry) + 1)
    {
        WCHAR *equals = StrChrW(entry, L'=');
        if (!equals || equals == entry) continue;
        *equals = 0;
        SetEnvironmentVariableW(entry, equals + 1);
        say("environment: %s=%s", u8(entry), u8(equals + 1));
        *equals = L'=';
    }
}

static int start_launcher(void)
{
    WCHAR launcher[MAX_PATH], folder[MAX_PATH], command[MAX_PATH + 2];
    STARTUPINFOW startup;
    PROCESS_INFORMATION process;
    ini(L"launcher", L"", launcher, MAX_PATH);
    if (!launcher[0] || !exists(launcher)) { say("launcher: %s is missing", u8(launcher)); return 1; }
    lstrcpyW(folder, launcher);
    PathRemoveFileSpecW(folder);
    wsprintfW(command, L"\"%s\"", launcher);
    ZeroMemory(&startup, sizeof(startup));
    startup.cb = sizeof(startup);
    if (!CreateProcessW(launcher, command, NULL, NULL, FALSE, 0, NULL, folder, &startup, &process))
    {
        say("launcher: could not start %s (error %lu)", u8(launcher), GetLastError());
        return 1;
    }
    say("launcher: started %s (pid %lu)", u8(launcher), process.dwProcessId);
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return 0;
}

/* WinVerifyTrust as verifysign 1.0.1's default policy calls it for the launcher's self-update (craft-libs
 * crates/update self_update.rs signed_like): generic verify v2, no UI, no revocation, cached URLs only. */
static int check_signature(const WCHAR *path)
{
    GUID action = WINTRUST_ACTION_GENERIC_VERIFY_V2;
    WINTRUST_FILE_INFO file;
    WINTRUST_DATA data;
    LONG status;
    ZeroMemory(&file, sizeof(file));
    ZeroMemory(&data, sizeof(data));
    file.cbStruct = sizeof(file);
    data.cbStruct = sizeof(data);
    file.pcwszFilePath = path;
    data.dwUIChoice = WTD_UI_NONE;
    data.fdwRevocationChecks = WTD_REVOKE_NONE;
    data.dwUnionChoice = WTD_CHOICE_FILE;
    data.pFile = &file;
    data.dwStateAction = WTD_STATEACTION_VERIFY;
    data.dwProvFlags = WTD_DISABLE_MD2_MD4 | WTD_CACHE_ONLY_URL_RETRIEVAL | WTD_NO_IE4_CHAIN_FLAG;
    data.dwUIContext = WTD_UICONTEXT_EXECUTE;
    status = WinVerifyTrust(INVALID_HANDLE_VALUE, &action, &data);
    data.dwStateAction = WTD_STATEACTION_CLOSE;
    WinVerifyTrust(INVALID_HANDLE_VALUE, &action, &data);
    const char *meaning = status == 0 ? "trusted" :
        status == (LONG)TRUST_E_NOSIGNATURE ? "not signed" :
        status == (LONG)CERT_E_UNTRUSTEDROOT ? "untrusted root (the code-signing root is not in the Root store)" :
        status == (LONG)CERT_E_EXPIRED ? "expired (Wine reads no RFC 3161 timestamp; see the WinTrust State flags)" :
        status == (LONG)TRUST_E_BAD_DIGEST ? "the file does not match its signature" :
        status == (LONG)CERT_E_CHAINING ? "the chain does not build" : "see winerror.h";
    say("signature: %s: 0x%08lx %s", u8(path), (unsigned long)status, meaning);
    return status == 0 ? 0 : 1;
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR line, int show)
{
    int count, i, result = 0;
    WCHAR **argv = CommandLineToArgvW(GetCommandLineW(), &count);
    (void)instance; (void)previous; (void)line; (void)show;
    GetModuleFileNameW(NULL, config_path, MAX_PATH);
    PathRemoveFileSpecW(config_path);
    PathAppendW(config_path, L"session.ini");
    for (i = 1; argv && i + 1 < count; ++i)
        if (!lstrcmpW(argv[i], L"--config")) GetFullPathNameW(argv[++i], MAX_PATH, config_path, NULL);
    open_log();
    for (i = 1; argv && i < count; ++i)
        if (!lstrcmpW(argv[i], L"--check-signature"))
        {
            if (i + 1 >= count) { say("--check-signature needs a file"); return 2; }
            return check_signature(argv[i + 1]);
        }
    say("session: ArtCraft desktop up; config %s", u8(config_path));
    if (!exists(config_path)) { say("session: no config; nothing to do"); return 1; }
    CoInitializeEx(NULL, COINIT_APARTMENTTHREADED);
    import_trust();
    if (import_defaults()) apply_wallpaper();
    sync_shortcuts();
    set_environment();
    result = start_launcher();
    CoUninitialize();
    LocalFree(argv);
    return result;
}
