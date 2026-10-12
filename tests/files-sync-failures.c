/* Exercise the Darwin stable-storage branch with deterministic syscall
 * failures. Host headers are loaded first so Linux can run this control too;
 * it is a fault-injection test, not qualification of a Darwin filesystem. */
#define _GNU_SOURCE 1
#include "../runtime/minyar_native.h"
#include <assert.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <pthread.h>
#include <stdarg.h>
#include <stdatomic.h>
#include <stdint.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>
#ifndef __APPLE__
#define __APPLE__ 1
#endif
#ifndef F_FULLFSYNC
#define F_FULLFSYNC 0x7ffffffe
#endif

static int full_sync_calls, weak_sync_calls, interrupted_once, full_sync_error;
static int injected_fcntl(int fd, int command, ...) {
    (void)fd;
    assert(command == F_FULLFSYNC);
    full_sync_calls++;
    if (interrupted_once) {
        interrupted_once = 0;
        errno = EINTR;
        return -1;
    }
    errno = full_sync_error;
    return full_sync_error ? -1 : 0;
}
static int injected_fsync(int fd) {
    (void)fd;
    weak_sync_calls++;
    return 0;
}
#define fcntl injected_fcntl
#define fsync injected_fsync
#include "../runtime/native/files.c"
#undef fsync
#undef fcntl

/* No managed values are needed by these sync entry points. */
MinyarBytes *minyar_bytes_new(long long length) { (void)length; abort(); }
MinyarText *minyar_native_copy_text(const unsigned char *bytes, long long length) {
    (void)bytes; (void)length; abort();
}
unsigned char *minyar_bytes_extend(MinyarBytes *bytes, long long count) {
    (void)bytes; (void)count; abort();
}

int main(void) {
    full_sync_error = EIO;
    assert(minyar_files_syncData(3) == -EIO);
    assert(minyar_files_sync(3) == -EIO);
    assert(full_sync_calls == 2 && weak_sync_calls == 0);
    full_sync_error = 0;
    interrupted_once = 1;
    assert(minyar_files_syncData(3) == 0);
    assert(full_sync_calls == 4 && weak_sync_calls == 0);
    assert(minyar_files_sync(3) == 0);
    assert(full_sync_calls == 5 && weak_sync_calls == 0);
    puts("durable sync failure and interruption verified");
    return 0;
}
