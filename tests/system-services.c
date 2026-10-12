#define _GNU_SOURCE 1
#include "system-test-values.h"
#include "../runtime/native/system.c"
#ifndef _WIN32
#include <sys/wait.h>
#endif

static void expect_text(MinyarText *value, const char *expected) {
    assert(value->byte_length == (long long)strlen(expected));
    assert(!memcmp(value->bytes, expected, strlen(expected)));
    test_release(value);
}
static void environment(void) {
    MinyarText name = test_text("MINYAR_SYSTEM_TEST"), missing = test_text("MINYAR_SYSTEM_MISSING"),
               empty = test_text("MINYAR_SYSTEM_EMPTY"), bad = test_text("BAD=KEY"), zero = test_text("");
    expect_text(minyar_system_getenv(&name), "snowman-☃");
    assert(minyar_system_lastError() == 0);
    expect_text(minyar_system_getenv(&empty), "");
    assert(minyar_system_lastError() == 0);
    expect_text(minyar_system_getenv(&missing), "");
    assert(minyar_system_lastError() == -ENOENT);
    expect_text(minyar_system_getenv(&bad), "");
    assert(minyar_system_lastError() == -EINVAL);
    expect_text(minyar_system_getenv(&zero), "");
    assert(minyar_system_lastError() == -EINVAL);
    MinyarText nul = {(const unsigned char *)"KEY\0tail", 8, 0, NULL, NULL};
    expect_text(minyar_system_getenv(&nul), "");
    assert(minyar_system_lastError() == -EINVAL);
    MinyarBytes *entries = minyar_system_environmentEntries();
    assert(minyar_system_lastError() == 0);
    int found = 0, found_empty = 0;
    size_t at = 0;
    while (at < (size_t)entries->byte_length) {
        const char *entry = (const char *)entries->bytes + at;
        const char *end = memchr(entry, 0, (size_t)entries->byte_length - at);
        assert(end);
        found += !strcmp(entry, "MINYAR_SYSTEM_TEST=snowman-☃");
        found_empty += !strcmp(entry, "MINYAR_SYSTEM_EMPTY=");
        at += (size_t)(end - entry) + 1;
    }
    assert(found == 1 && found_empty == 1);
    test_release(entries);
}
static void limits(void) {
    assert(minyar_system_getSoftLimit(LLONG_MAX) == -EINVAL);
    assert(minyar_system_getHardLimit(-1) == -EINVAL);
    assert(minyar_system_setResourceLimit(0, -1, 1) == -EINVAL);
    assert(minyar_system_setResourceLimit(0, 2, 1) == -EINVAL);
#ifdef _WIN32
    for (int resource = 0; resource < 6; resource++) {
        assert(minyar_system_getSoftLimit(resource) == -ENOTSUP);
        assert(minyar_system_getHardLimit(resource) == -ENOTSUP);
        assert(minyar_system_setResourceLimit(resource, 1, 1) == -ENOTSUP);
    }
    assert(minyar_system_raiseOpenFileLimit() == -ENOTSUP);
#else
    long long soft = minyar_system_getSoftLimit(0), hard = minyar_system_getHardLimit(0);
    assert(soft > 32 && hard >= soft);
    assert(minyar_system_setResourceLimit(0, 32, hard) == 0);
    assert(minyar_system_getSoftLimit(0) == 32 && minyar_system_getHardLimit(0) == hard);
    assert(minyar_system_setResourceLimit(0, soft, hard) == 0);
    /* Lower both limits in a sacrificial process; restoring a hard limit may require root. */
    pid_t child = fork(); assert(child >= 0);
    if (!child) {
        assert(minyar_system_setResourceLimit(0, 24, 24) == 0);
        assert(minyar_system_getSoftLimit(0) == 24 && minyar_system_getHardLimit(0) == 24);
        _exit(0);
    }
    int status; assert(waitpid(child, &status, 0) == child && WIFEXITED(status) && !WEXITSTATUS(status));
    long long core_soft = minyar_system_getSoftLimit(1), core_hard = minyar_system_getHardLimit(1);
    assert(core_soft >= 0 && core_hard >= core_soft);
    assert(minyar_system_setResourceLimit(1, core_soft, core_hard) == 0);
#endif
}
static void signals(void) {
#ifdef _WIN32
    assert(minyar_system_ignoreBrokenPipes() == -ENOTSUP);
    assert(minyar_system_shutdownSignalSocket() == -ENOTSUP);
    assert(minyar_system_drainShutdownSignals() == -ENOTSUP);
    assert(minyar_system_sendSignal(minyar_system_processId(), 15) == -ENOTSUP);
    assert(minyar_system_sendSignal(LLONG_MAX, 0) == -EINVAL);
    assert(minyar_system_sendSignal(minyar_system_processId(), 0) == 0);
#else
    assert(minyar_system_ignoreBrokenPipes() == 0);
    long long fd = minyar_system_shutdownSignalSocket(); assert(fd >= 0);
    assert(fcntl((int)fd, F_GETFD) & FD_CLOEXEC);
    assert(minyar_system_sendSignal(minyar_system_processId(), SIGTERM) == 0);
    assert(minyar_system_drainShutdownSignals() == SIGTERM);
#endif
    assert(minyar_system_wallClockMicroseconds() > 1700000000000000LL);
    assert(minyar_system_monotonicNanoseconds() > 0);
    assert(minyar_system_residentBytes() > 0);
}
int main(int argc, char **argv) {
    assert(argc == 2);
    if (!strcmp(argv[1], "environment")) environment();
    else if (!strcmp(argv[1], "limits")) limits();
    else if (!strcmp(argv[1], "signals")) signals();
    else if (!strcmp(argv[1], "stderr")) {
        MinyarText value = {(const unsigned char *)"diagnostic\0λ\n", 14, 0, NULL, NULL};
        assert(minyar_system_writeStandardError(&value) == 14);
    } else assert(!"unknown case");
    return 0;
}
