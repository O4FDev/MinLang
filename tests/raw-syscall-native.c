/* Link against the actual shared runtime, not a libc syscall wrapper. */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#if defined(__linux__) && defined(__LP64__) && (defined(__x86_64__) || defined(__aarch64__))
#include <sys/syscall.h>
#include <unistd.h>
#endif
long long minyar_machine_syscall(long long, long long, long long, long long,
                               long long, long long, long long);
int main(void) {
    errno = EDOM;
#if defined(__linux__) && defined(__LP64__) && (defined(__x86_64__) || defined(__aarch64__))
    assert(minyar_machine_syscall(SYS_getpid, 0, 0, 0, 0, 0, 0) == getpid());
    assert(errno == EDOM);
    assert(minyar_machine_syscall(2147483647, 0, 0, 0, 0, 0, 0) == -ENOSYS);
    assert(errno == EDOM);
    assert(minyar_machine_syscall(SYS_close, -1, 0, 0, 0, 0, 0) == -EBADF);
    assert(errno == EDOM);
    assert(minyar_machine_syscall(SYS_openat, -100, 1, 0, 0, 0, 0) == -EFAULT);
    assert(errno == EDOM);
#else
    assert(minyar_machine_syscall(39, 1, 2, 3, 4, 5, 6) == -38);
    assert(errno == EDOM);
#endif
    puts("raw syscall preserves libc errno");
    return 0;
}
