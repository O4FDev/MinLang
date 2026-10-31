/* dev-check coverage: write the profile before abnormal exits that skip atexit handlers. */
#include <signal.h>
#include <string.h>
#include <unistd.h>
extern int __llvm_profile_write_file(void) __attribute__((weak));
extern void __real__exit(int) __attribute__((noreturn));
extern void __real__Exit(int) __attribute__((noreturn));
extern void __real_abort(void) __attribute__((noreturn));
static void flush(void) { if (__llvm_profile_write_file) __llvm_profile_write_file(); }
void __wrap__exit(int status) { flush(); __real__exit(status); }
void __wrap__Exit(int status) { flush(); __real__Exit(status); }
void __wrap_abort(void) { flush(); __real_abort(); }
static void on_signal(int number) { flush(); signal(number, SIG_DFL); raise(number); }
__attribute__((constructor)) static void install(void) {
    int numbers[] = { SIGSEGV, SIGBUS, SIGILL, SIGFPE, SIGTRAP, SIGABRT };
    for (unsigned i = 0; i < sizeof numbers / sizeof numbers[0]; i++) {
        struct sigaction old;
        if (sigaction(numbers[i], 0, &old) == 0 && old.sa_handler == SIG_DFL) signal(numbers[i], on_signal);
    }
}
