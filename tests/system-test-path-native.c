#define _GNU_SOURCE 1
#define _XOPEN_SOURCE 700
#include "../runtime/minyar_native.h"
#include <errno.h>
#include <limits.h>
#include <stdint.h>
#ifdef _WIN32
#include <windows.h>
#endif

static _Thread_local long long systemtestpath_error;
long long minyar_systemtestpath_lastError(void) { return systemtestpath_error; }
MinyarBytes *minyar_systemtestpath_realpath(const MinyarText *path) {
    systemtestpath_error = 0;
    if (!path || path->byte_length < 1 || (unsigned long long)path->byte_length >= SIZE_MAX ||
        memchr(path->bytes, 0, (size_t)path->byte_length)) {
        systemtestpath_error = EINVAL;
        return minyar_bytes_new(0);
    }
    char *name = malloc((size_t)path->byte_length + 1);
    if (!name) { systemtestpath_error = ENOMEM; return minyar_bytes_new(0); }
    memcpy(name, path->bytes, (size_t)path->byte_length);
    name[path->byte_length] = 0;
#ifdef _WIN32
    if (path->byte_length > INT_MAX) { free(name); systemtestpath_error = ENAMETOOLONG; return minyar_bytes_new(0); }
    int wide_count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, name, -1, NULL, 0);
    wchar_t *wide = wide_count > 0 ? malloc((size_t)wide_count * sizeof(*wide)) : NULL;
    if (!wide || !MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, name, -1, wide, wide_count)) {
        free(name); free(wide); systemtestpath_error = EINVAL; return minyar_bytes_new(0);
    }
    free(name);
    HANDLE file = CreateFileW(wide, 0, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        NULL, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, NULL);
    free(wide);
    if (file == INVALID_HANDLE_VALUE) { systemtestpath_error = ENOENT; return minyar_bytes_new(0); }
    DWORD capacity = GetFinalPathNameByHandleW(file, NULL, 0, FILE_NAME_NORMALIZED);
    wide = capacity && capacity < UINT_MAX ? malloc(((size_t)capacity + 1) * sizeof(*wide)) : NULL;
    DWORD count = wide ? GetFinalPathNameByHandleW(file, wide, capacity + 1, FILE_NAME_NORMALIZED) : 0;
    CloseHandle(file);
    if (!count || count > capacity || count > INT_MAX) { free(wide); systemtestpath_error = EIO; return minyar_bytes_new(0); }
    int length = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, wide, (int)count, NULL, 0, NULL, NULL);
    if (length < 1) { free(wide); systemtestpath_error = EINVAL; return minyar_bytes_new(0); }
    MinyarBytes *result = minyar_bytes_new(length);
    if (WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, wide, (int)count, (char *)result->bytes, length, NULL, NULL) != length) abort();
    free(wide);
    return result;
#else
    char *resolved = realpath(name, NULL);
    int error = errno;
    free(name);
    if (!resolved) { systemtestpath_error = error; return minyar_bytes_new(0); }
    size_t length = strlen(resolved);
    if (length > LLONG_MAX) { free(resolved); systemtestpath_error = ENAMETOOLONG; return minyar_bytes_new(0); }
    MinyarBytes *result = minyar_bytes_new((long long)length);
    memcpy((void *)result->bytes, resolved, length);
    free(resolved);
    return result;
#endif
}
