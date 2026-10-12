#define _DEFAULT_SOURCE
#include "../runtime/minyar_native.h"
#include <openssl/sha.h>
#include <stdint.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#endif

/* Single-test-process fixture; production has no global state. */
static unsigned char *mapping;
static size_t mapping_length;
long long minyar_sha256test_guarded(long long length, bool front) {
#ifdef _WIN32
    SYSTEM_INFO system;
    GetSystemInfo(&system);
    size_t page = system.dwPageSize;
#else
    size_t page = (size_t)sysconf(_SC_PAGESIZE);
#endif
    if (mapping || length < 1 || length > 8192) abort();
    size_t capacity = ((size_t)length + page - 1) / page * page;
    mapping_length = capacity + 2 * page;
#ifdef _WIN32
    mapping = VirtualAlloc(NULL, mapping_length, MEM_RESERVE | MEM_COMMIT, PAGE_NOACCESS);
    DWORD old;
    if (!mapping || !VirtualProtect(mapping + page, capacity, PAGE_READWRITE, &old)) abort();
#else
    mapping = mmap(NULL, mapping_length, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (mapping == MAP_FAILED || mprotect(mapping + page, capacity, PROT_READ | PROT_WRITE)) abort();
#endif
    unsigned char *data = mapping + page + (front ? 0 : capacity - (size_t)length);
    for (long long i = 0; i < length; ++i) data[i] = (unsigned char)(i * 31 + length);
    return (long long)(uintptr_t)data;
}
void minyar_sha256test_releaseGuard(void) {
#ifdef _WIN32
    if (!mapping || !VirtualFree(mapping, 0, MEM_RELEASE)) abort();
#else
    if (!mapping || munmap(mapping, mapping_length)) abort();
#endif
    mapping = NULL;
}
MinyarBytes *minyar_sha256test_oracle(long long address, long long length) {
    MinyarBytes *result = minyar_bytes_new(32);
    if (!SHA256((const unsigned char *)(uintptr_t)address, (size_t)length, (unsigned char *)result->bytes)) abort();
    return result;
}
long long minyar_sha256test_nanos(void) {
#ifdef _WIN32
    LARGE_INTEGER now, frequency;
    if (!QueryPerformanceCounter(&now) || !QueryPerformanceFrequency(&frequency)) abort();
    return now.QuadPart / frequency.QuadPart * 1000000000 +
        now.QuadPart % frequency.QuadPart * 1000000000 / frequency.QuadPart;
#else
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now)) abort();
    return (long long)now.tv_sec * 1000000000 + now.tv_nsec;
#endif
}
