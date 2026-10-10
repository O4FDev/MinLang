#!/usr/bin/env python3
"""Exercise the Windows CSPRNG boundary without a Windows host or bcrypt link flag.

The real Windows fragment is compiled against a fault-injectable OS shim. Like
CPython's random-source tests, unavailable sources and system failures must fail
closed; large requests must neither truncate nor bypass the secure generator.
Peer source: CPython v3.14.0 Lib/test/test_os.py URandomFDTests.test_urandom_failure
https://github.com/python/cpython/blob/v3.14.0/Lib/test/test_os.py#L2028
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLANG = os.environ.get("MINYAR_TEST_CLANG", "clang")

SHIM = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
#define WINAPI
#define CALLBACK
#define TRUE 1
#define FALSE 0
#define LOAD_LIBRARY_SEARCH_SYSTEM32 0x800
typedef int BOOL;
typedef void *PVOID;
typedef void *HMODULE;
typedef void (*FARPROC)(void);
typedef struct { int done; } INIT_ONCE, *PINIT_ONCE;
#define INIT_ONCE_STATIC_INIT {0}
static int mode, loads, symbols, calls, frees;
static uintptr_t last_pointer;
static uint64_t total;
#include <bcrypt.h>
static NTSTATUS WINAPI secure_random(BCRYPT_ALG_HANDLE handle, PUCHAR out,
                                    ULONG count, ULONG flags) {
    assert(handle == NULL && flags == BCRYPT_USE_SYSTEM_PREFERRED_RNG);
    if (calls) assert((uintptr_t)out == last_pointer);
    last_pointer = (uintptr_t)out + count;
    total += count;
    calls++;
    return mode == 3 ? -1 : 0;
}
static HMODULE LoadLibraryExW(const wchar_t *name, void *file, unsigned flags) {
    assert(!wcscmp(name, L"bcrypt.dll") && file == NULL);
    assert(flags == LOAD_LIBRARY_SEARCH_SYSTEM32);
    loads++;
    return mode == 1 ? NULL : (HMODULE)(uintptr_t)1;
}
static FARPROC GetProcAddress(HMODULE module, const char *name) {
    assert(module && !strcmp(name, "BCryptGenRandom"));
    symbols++;
    return mode == 2 ? NULL : (FARPROC)secure_random;
}
static BOOL FreeLibrary(HMODULE module) { assert(module); frees++; return TRUE; }
static BOOL InitOnceExecuteOnce(PINIT_ONCE once,
                               BOOL (CALLBACK *initialize)(PINIT_ONCE, PVOID, PVOID *),
                               PVOID parameter, PVOID *context) {
    if (!once->done) {
        if (!initialize(once, parameter, context)) return FALSE;
        once->done = 1;
    }
    return TRUE;
}
static _Noreturn void minyar_stop(const char *message) {
    fprintf(stderr, "%s\n", message);
    exit(19);
}
'''

MAIN = r'''
int main(int argc, char **argv) {
    assert(argc == 2);
    mode = atoi(argv[1]);
    if (mode == 4) {
        fill_random((unsigned char *)(uintptr_t)4096, (size_t)UINT32_MAX + 7);
        assert(calls == 2 && total == (uint64_t)UINT32_MAX + 7);
    } else {
        fill_random((unsigned char *)(uintptr_t)4096, 17);
        fill_random((unsigned char *)(uintptr_t)(4096 + 17), 29);
        assert(calls == 2 && total == 46);
    }
    assert(loads == 1 && symbols == 1 && frees == 0);
    puts("secure system random source used");
}
'''


class WindowsRandomSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="minyar-random-")
        cls.addClassCleanup(cls.temporary.cleanup)
        directory = Path(cls.temporary.name)
        (directory / "bcrypt.h").write_text('''typedef int32_t NTSTATUS;
typedef uint32_t ULONG;
typedef void *BCRYPT_ALG_HANDLE;
typedef unsigned char *PUCHAR;
#define BCRYPT_USE_SYSTEM_PREFERRED_RNG 2
NTSTATUS WINAPI BCryptGenRandom(BCRYPT_ALG_HANDLE, PUCHAR, ULONG, ULONG);
''')
        fragment = (ROOT / "runtime/minyar_bytes.h").read_text().split(
            "#elif defined(_WIN32)\n", 1)[1].split("\n#else\n", 1)[0]
        source = directory / "random.c"
        source.write_text(SHIM + fragment + MAIN)
        cls.executable = directory / ("random.exe" if os.name == "nt" else "random")
        linked = subprocess.run([CLANG, "-std=c11", "-Wall", "-Wextra", "-Werror",
                                 "-Wno-unused-function", "-I", str(directory),
                                 str(source), "-o", str(cls.executable)],
                                capture_output=True, text=True, timeout=30)
        if linked.returncode:
            raise AssertionError("Windows random source must link without bcrypt flags:\n" + linked.stderr)

    def test_secure_source_is_initialized_once(self):
        self.check(0, 0, "secure system random source used\n", "")

    def test_large_requests_are_split_at_the_windows_length_boundary(self):
        self.check(4, 0, "secure system random source used\n", "")

    def test_unavailable_library_symbol_and_system_failure_fail_closed(self):
        for failure in (1, 2, 3):
            with self.subTest(failure=failure):
                self.check(failure, 19, "", "the system could not provide random bytes.\n")

    def check(self, mode, status, stdout, stderr):
        result = subprocess.run([str(self.executable), str(mode)], capture_output=True,
                                text=True, timeout=10)
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (status, stdout, stderr))


if __name__ == "__main__":
    unittest.main(verbosity=2)
