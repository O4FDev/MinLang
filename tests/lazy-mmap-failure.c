/* Inject each startup mapping failure; check rollback before process exit. */
#include <sys/mman.h>
#include <errno.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#define MINYAR_BOUNDED_HEAP 1
#define MINYAR_LAZY_HEAP 1
#ifndef FAIL_MAPPING
#define FAIL_MAPPING 1
#endif
static unsigned mappings, releases;
static void *first_mapping;
static size_t first_size;
static void verify_failure(void) {
    assert(mappings == FAIL_MAPPING);
    assert(releases == (FAIL_MAPPING == 2));
    fputs("injected mapping failure rolled back correctly\n", stderr);
}
static void *fixture_mmap(void *address, size_t size, int protection, int flags, int fd, off_t offset) {
    if (!mappings) assert(!atexit(verify_failure));
    mappings++;
    if (mappings == FAIL_MAPPING) { errno = ENOMEM; return MAP_FAILED; }
    void *result = mmap(address, size, protection, flags, fd, offset);
    assert(result != MAP_FAILED);
    first_mapping = result; first_size = size;
    return result;
}
static int fixture_munmap(void *address, size_t size) {
    assert(address == first_mapping && size == first_size);
    releases++;
    int result = munmap(address, size);
    assert(!result);
    return result;
}
#define mmap fixture_mmap
#define munmap fixture_munmap
#include "../runtime/minyar_runtime.c"
#undef mmap
#undef munmap
int main(void) { assert(!"mapping failure must stop before main"); }
