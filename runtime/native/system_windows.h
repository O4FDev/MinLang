/* Included only by system.c. UTF-8 at the package boundary, UTF-16 at Win32. */
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0601
#endif
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <psapi.h>
#include <wchar.h>

static int system_windows_error(DWORD code) {
    switch (code) {
    case ERROR_FILE_NOT_FOUND: case ERROR_PATH_NOT_FOUND: case ERROR_ENVVAR_NOT_FOUND: return ENOENT;
    case ERROR_ACCESS_DENIED: case ERROR_PRIVILEGE_NOT_HELD: return EACCES;
    case ERROR_NOT_ENOUGH_MEMORY: case ERROR_OUTOFMEMORY: return ENOMEM;
    case ERROR_INVALID_PARAMETER: case ERROR_INVALID_NAME: return EINVAL;
    case ERROR_DIRECTORY: return ENOTDIR;
    case ERROR_BAD_EXE_FORMAT: return ENOEXEC;
    case ERROR_INVALID_HANDLE: return EBADF;
    case ERROR_BROKEN_PIPE: return EPIPE;
    case ERROR_NO_UNICODE_TRANSLATION: return EILSEQ;
    case ERROR_FILENAME_EXCED_RANGE: return ENAMETOOLONG;
    default: return EIO;
    }
}
static wchar_t *system_wide(const char *value) {
    int length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value, -1, NULL, 0);
    if (!length) { system_error = system_windows_error(GetLastError()); return NULL; }
    wchar_t *result = malloc((size_t)length * sizeof(*result));
    if (!result) { system_error = ENOMEM; return NULL; }
    if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value, -1, result, length)) {
        system_error = system_windows_error(GetLastError()); free(result); return NULL;
    }
    return result;
}
long long minyar_system_wallClockMicroseconds(void) {
    FILETIME time; GetSystemTimeAsFileTime(&time);
    ULARGE_INTEGER value; value.LowPart = time.dwLowDateTime; value.HighPart = time.dwHighDateTime;
    return (long long)(value.QuadPart / 10) - 11644473600000000LL;
}
long long minyar_system_monotonicNanoseconds(void) {
    LARGE_INTEGER count, frequency;
    if (!QueryPerformanceCounter(&count) || !QueryPerformanceFrequency(&frequency) || frequency.QuadPart <= 0)
        return -EIO;
    return count.QuadPart / frequency.QuadPart * 1000000000LL +
           (long long)((long double)(count.QuadPart % frequency.QuadPart) * 1000000000.0L / frequency.QuadPart);
}
long long minyar_system_processId(void) { return GetCurrentProcessId(); }
long long minyar_system_residentBytes(void) {
    PROCESS_MEMORY_COUNTERS memory;
    if (!GetProcessMemoryInfo(GetCurrentProcess(), &memory, sizeof(memory)))
        return -system_windows_error(GetLastError());
    if (memory.WorkingSetSize > LLONG_MAX) return -EOVERFLOW;
    return (long long)memory.WorkingSetSize;
}
long long minyar_system_ignoreBrokenPipes(void) { return -ENOTSUP; }
long long minyar_system_shutdownSignalSocket(void) { return -ENOTSUP; }
long long minyar_system_drainShutdownSignals(void) { return -ENOTSUP; }
long long minyar_system_sendSignal(long long pid, long long signal) {
    if (pid <= 0 || (uint64_t)pid > UINT32_MAX || signal < 0 || signal > INT_MAX) return -EINVAL;
    if (signal) return -ENOTSUP;
    HANDLE process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, (DWORD)pid);
    if (!process) return GetLastError() == ERROR_INVALID_PARAMETER ? -ESRCH : -system_windows_error(GetLastError());
    DWORD code; BOOL success = GetExitCodeProcess(process, &code); CloseHandle(process);
    return success ? (code == STILL_ACTIVE ? 0 : -ESRCH) : -EIO;
}
long long minyar_system_writeStandardError(const MinyarText *text) {
    if (!system_valid_buffer(text)) return -EINVAL;
    HANDLE output = GetStdHandle(STD_ERROR_HANDLE);
    long long done = 0;
    while (done < text->byte_length) {
        DWORD count = (DWORD)((text->byte_length - done) > INT_MAX ? INT_MAX : text->byte_length - done), written;
        if (!WriteFile(output, text->bytes + done, count, &written, NULL)) return -system_windows_error(GetLastError());
        if (!written) return -EIO;
        done += written;
    }
    return done;
}
MinyarText *minyar_system_getenv(const MinyarText *name) {
    system_error = 0;
    char *key = system_cstring(name);
    wchar_t *wide = NULL, *value = NULL;
    MinyarText *result = NULL;
    if (key && (!*key || strchr(key, '='))) system_error = EINVAL;
    else if (key) wide = system_wide(key);
    if (wide) {
        DWORD capacity = 0;
        for (;;) {
            SetLastError(ERROR_SUCCESS);
            DWORD count = GetEnvironmentVariableW(wide, value, capacity);
            if (!count) { system_error = GetLastError() == ERROR_ENVVAR_NOT_FOUND ? ENOENT :
                                      (GetLastError() ? system_windows_error(GetLastError()) : 0); break; }
            if (count < capacity) {
                int bytes = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, value, (int)count, NULL, 0, NULL, NULL);
                if (!bytes) { system_error = EILSEQ; break; }
                char *utf8 = malloc((size_t)bytes);
                if (!utf8) { system_error = ENOMEM; break; }
                WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, value, (int)count,
                                    utf8, bytes, NULL, NULL);
                result = minyar_native_copy_text((const unsigned char *)utf8, bytes);
                free(utf8);
                break;
            }
            wchar_t *grown = realloc(value, (size_t)count * sizeof(*value));
            if (!grown) { system_error = ENOMEM; break; }
            value = grown; capacity = count;
        }
    }
    free(key); free(wide); free(value);
    return result ? result : minyar_native_copy_text((const unsigned char *)"", 0);
}
MinyarBytes *minyar_system_environmentEntries(void) {
    system_error = 0;
    wchar_t *block = GetEnvironmentStringsW();
    if (!block) { system_error = system_windows_error(GetLastError()); return minyar_bytes_new(0); }
    size_t length = 0;
    for (wchar_t *at = block; *at; at += wcslen(at) + 1) {
        int count = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, at, -1, NULL, 0, NULL, NULL);
        if (!count || (size_t)count > (size_t)LLONG_MAX - length) {
            system_error = count ? EOVERFLOW : EILSEQ; FreeEnvironmentStringsW(block); return minyar_bytes_new(0);
        }
        length += (size_t)count;
    }
    MinyarBytes *result = minyar_bytes_new((long long)length);
    char *out = (char *)result->bytes;
    for (wchar_t *at = block; *at; at += wcslen(at) + 1) {
        int count = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, at, -1, NULL, 0, NULL, NULL);
        WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, at, -1, out, count, NULL, NULL); out += count;
    }
    FreeEnvironmentStringsW(block); return result;
}
long long minyar_system_getSoftLimit(long long resource) { return system_failure(resource >= 0 && resource < 6 ? ENOTSUP : EINVAL); }
long long minyar_system_getHardLimit(long long resource) { return minyar_system_getSoftLimit(resource); }
long long minyar_system_setResourceLimit(long long resource, long long soft, long long hard) {
    return system_failure(resource < 0 || resource >= 6 || soft < 0 || hard < 0 || soft > hard ? EINVAL : ENOTSUP);
}
long long minyar_system_raiseOpenFileLimit(void) { return -ENOTSUP; }
