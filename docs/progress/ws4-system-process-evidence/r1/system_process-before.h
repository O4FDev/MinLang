/* Included by system.c. All process APIs have one serialized owner. Native
 * argument copies, registry slots and child state are prepared before launch. */
#ifndef _WIN32
#include <spawn.h>
#include <sys/wait.h>
#include <pthread.h>
#include <grp.h>
#ifdef __APPLE__
#include <dlfcn.h>
#endif
#ifdef __linux__
#include <sys/mman.h>
#include <sys/syscall.h>
#endif
#endif

enum { SYSTEM_VECTOR_LIMIT = 16 * 1024 * 1024, SYSTEM_VECTOR_COUNT = 65536 };
typedef struct SystemVector { char **values; char *storage; size_t count; } SystemVector;
static uint64_t system_u64(const unsigned char *bytes) {
    uint64_t result = 0;
    for (unsigned i = 0; i < 8; i++) result |= (uint64_t)bytes[i] << (i * 8);
    return result;
}
static void system_put64(unsigned char *bytes, uint64_t value) {
    for (unsigned i = 0; i < 8; i++) bytes[i] = (unsigned char)(value >> (i * 8));
}
static void system_vector_clear(SystemVector *vector) {
    free(vector->values); free(vector->storage);
}
/* Count and byte lengths are little-endian u64. Length prefixes preserve empty
 * arguments and make embedded NUL an error rather than an argument separator. */
static bool system_vector(const MinyarBytes *bytes, SystemVector *vector, bool environment) {
    if (!system_valid_buffer(bytes) || bytes->byte_length < 8) { system_error = EINVAL; return false; }
    if (bytes->byte_length > SYSTEM_VECTOR_LIMIT) { system_error = E2BIG; return false; }
    uint64_t count = system_u64(bytes->bytes);
    if (count > SYSTEM_VECTOR_COUNT || count > ((uint64_t)bytes->byte_length - 8) / 8) {
        system_error = EINVAL; return false;
    }
    vector->values = calloc((size_t)count + 1, sizeof(*vector->values));
    vector->storage = malloc((size_t)bytes->byte_length + (size_t)count);
    if (!vector->values || !vector->storage) { system_error = ENOMEM; return false; }
    vector->count = (size_t)count;
    size_t at = 8; char *out = vector->storage;
    for (size_t i = 0; i < vector->count; i++) {
        if ((size_t)bytes->byte_length - at < 8) { system_error = EINVAL; return false; }
        uint64_t length = system_u64(bytes->bytes + at); at += 8;
        if (length > (size_t)bytes->byte_length - at || (length && memchr(bytes->bytes + at, 0, (size_t)length))) {
            system_error = EINVAL; return false;
        }
        vector->values[i] = out;
        if (length) memcpy(out, bytes->bytes + at, (size_t)length);
        out[length] = 0;
        if (environment) {
            char *equals = strchr(out, '=');
#ifdef _WIN32
            /* Windows includes hidden drive-directory entries such as =C:=C:\\ . */
            if (equals == out) equals = strchr(out + 1, '=');
#endif
            if (!equals || equals == out) { system_error = EINVAL; return false; }
        }
        out += (size_t)length + 1; at += (size_t)length;
    }
    if (at != (size_t)bytes->byte_length || (!environment && !count)) { system_error = EINVAL; return false; }
    return true;
}
typedef struct SystemProcess {
    struct SystemProcess *next;
    long long handle;
#ifdef _WIN32
    HANDLE process;
    DWORD pid;
#else
    pid_t pid;
#endif
} SystemProcess;
static SystemProcess *system_processes;
static long long system_process_serial;
static bool system_process_cleanup_installed;
static void system_process_cleanup(void) {
    while (system_processes) {
        SystemProcess *next = system_processes->next;
#ifdef _WIN32
        CloseHandle(system_processes->process);
#endif
        free(system_processes); system_processes = next;
    }
}
static SystemProcess **system_process_slot(long long handle) {
    SystemProcess **slot = &system_processes;
    while (*slot && (*slot)->handle != handle) slot = &(*slot)->next;
    return slot;
}
long long minyar_system_childProcessId(long long handle) {
    system_error = 0;
    SystemProcess *process = *system_process_slot(handle);
    return process ? process->pid : system_failure(ECHILD);
}
static MinyarBytes *system_wait_result(long long error, unsigned state, long long code, long long signal) {
    MinyarBytes *result = minyar_bytes_new(32);
    unsigned char *bytes = (unsigned char *)result->bytes;
    system_put64(bytes, (uint64_t)error); system_put64(bytes + 8, state);
    system_put64(bytes + 16, (uint64_t)code); system_put64(bytes + 24, (uint64_t)signal);
    system_error = error < 0 ? (int)-error : 0;
    return result;
}
MinyarBytes *minyar_system_waitNative(long long handle, bool poll) {
    SystemProcess **slot = system_process_slot(handle), *process = *slot;
    if (!process) return system_wait_result(-ECHILD, 3, 0, 0);
    unsigned state = 0; long long code = 0, signal = 0; int error = 0;
#ifdef _WIN32
    DWORD wait = WaitForSingleObject(process->process, poll ? 0 : INFINITE);
    if (wait == WAIT_TIMEOUT) return system_wait_result(0, 0, 0, 0);
    if (wait != WAIT_OBJECT_0) error = system_windows_error(GetLastError());
    else {
        DWORD exit_code;
        if (!GetExitCodeProcess(process->process, &exit_code)) error = system_windows_error(GetLastError());
        else { state = 1; code = exit_code; }
    }
#else
    int status; pid_t waited;
    do { waited = waitpid(process->pid, &status, poll ? WNOHANG : 0); } while (waited < 0 && errno == EINTR);
    if (!waited) return system_wait_result(0, 0, 0, 0);
    if (waited < 0) error = errno;
    else if (WIFEXITED(status)) { state = 1; code = WEXITSTATUS(status); }
    else if (WIFSIGNALED(status)) { state = 2; signal = WTERMSIG(status); }
    else return system_wait_result(0, 0, 0, 0);
#endif
    if (!error || error == ECHILD) {
        *slot = process->next;
#ifdef _WIN32
        CloseHandle(process->process);
#endif
        free(process);
    }
    return system_wait_result(-error, error ? 3 : state, code, signal);
}

#if defined(__linux__) && (defined(__x86_64__) || defined(__aarch64__))
#define SYSTEM_CHILD __attribute__((no_sanitize("address", "undefined", "thread", "coverage"), no_stack_protector, no_instrument_function, no_profile_instrument_function))
/* Direct kernel results: never libc syscall() or errno/TLS in the shared-VM child. */
static SYSTEM_CHILD __attribute__((always_inline)) inline long system_raw(long number, long a, long b, long c, long d) {
#if defined(__x86_64__)
    long result; register long fourth __asm__("r10") = d;
    __asm__ volatile("syscall" : "=a"(result) : "a"(number), "D"(a), "S"(b), "d"(c), "r"(fourth) : "rcx", "r11", "memory", "cc");
    return result;
#else
    register long x8 __asm__("x8") = number, x0 __asm__("x0") = a, x1 __asm__("x1") = b,
                  x2 __asm__("x2") = c, x3 __asm__("x3") = d;
    __asm__ volatile("svc 0" : "+r"(x0) : "r"(x8), "r"(x1), "r"(x2), "r"(x3) : "memory", "cc");
    return x0;
#endif
}
typedef struct SystemKernelAction {
    unsigned long handler, flags;
#ifdef __x86_64__
    unsigned long restorer;
#endif
    uint64_t mask;
} SystemKernelAction;
typedef struct SystemChild {
    const char *path, *cwd;
    char **argv, **envp;
    const gid_t *groups;
    size_t group_count;
    long long uid, gid;
    bool credentials;
    uint64_t mask;
    SystemKernelAction defaults;
    volatile int error;
} SystemChild;
/* Never returns to clone's libc trampoline or Minyar. No library calls,
 * allocation, RC, TLS writes, sanitizers, stack protector or managed handlers. */
static SYSTEM_CHILD int system_clone_child(void *pointer) {
    SystemChild *child = pointer;
    long result = 0;
    SystemKernelAction action;
    for (int signal = 1; signal <= 64; signal++) {
        if (signal == SIGKILL || signal == SIGSTOP) continue;
        result = system_raw(SYS_rt_sigaction, signal, 0, (long)&action, 8);
        if (result < 0) goto failed;
        if (signal == SIGPIPE || action.handler > 1) {
            result = system_raw(SYS_rt_sigaction, signal, (long)&child->defaults, 0, 8);
            if (result < 0) goto failed;
        }
    }
    if (*child->cwd) {
        result = system_raw(SYS_chdir, (long)child->cwd, 0, 0, 0);
        if (result < 0) goto failed;
    }
    if (child->credentials) {
        result = system_raw(SYS_setgroups, (long)child->group_count, (long)child->groups, 0, 0);
        if (result < 0) goto failed;
        if (child->gid != -1) {
            result = system_raw(SYS_setresgid, (long)child->gid, (long)child->gid, (long)child->gid, 0);
            if (result < 0) goto failed;
        }
        if (child->uid != -1) {
            result = system_raw(SYS_setresuid, (long)child->uid, (long)child->uid, (long)child->uid, 0);
            if (result < 0) goto failed;
        }
    }
    result = system_raw(SYS_rt_sigprocmask, SIG_SETMASK, (long)&child->mask, 0, 8);
    if (result < 0) goto failed;
    result = system_raw(SYS_execve, (long)child->path, (long)child->argv, (long)child->envp, 0);
failed:
    child->error = result < 0 ? (int)-result : EIO;
    for (;;) system_raw(SYS_exit, 127, 0, 0, 0);
}
static int system_clone_spawn(SystemProcess *process, const char *path, char **argv, char **envp,
                              const char *cwd, long long uid, long long gid, gid_t *groups, size_t count, bool credentials) {
    long page = sysconf(_SC_PAGESIZE);
    if (page <= 0) return EIO;
    size_t size = 128 * 1024 + (size_t)page;
    void *stack = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (stack == MAP_FAILED) return errno;
    if (mprotect(stack, (size_t)page, PROT_NONE)) { int error = errno; munmap(stack, size); return error; }
    SystemChild child = {.path=path, .cwd=cwd, .argv=argv, .envp=envp, .groups=groups,
        .group_count=count, .uid=uid, .gid=gid, .credentials=credentials};
    uint64_t all = UINT64_MAX, original;
    /* Include NPTL's reserved signals: pthread_sigmask deliberately leaves them
     * unblocked. The child shares VM/TLS, never dispositions, fds or cwd. */
    long masked = system_raw(SYS_rt_sigprocmask, SIG_SETMASK, (long)&all, (long)&original, 8);
    if (masked < 0) { munmap(stack, size); return (int)-masked; }
    child.mask = original & ~(UINT64_C(1) << (SIGPIPE - 1));
    pid_t pid = clone(system_clone_child, (unsigned char *)stack + size, CLONE_VM | CLONE_VFORK | SIGCHLD, &child);
    int error = pid < 0 ? errno : child.error;
    long restored = system_raw(SYS_rt_sigprocmask, SIG_SETMASK, (long)&original, 0, 8);
    if (restored < 0 && !error) error = (int)-restored;
    munmap(stack, size);
    if (error && pid > 0) {
        if (!child.error) kill(pid, SIGKILL);
        while (waitpid(pid, NULL, 0) < 0 && errno == EINTR) {}
    }
    if (!error) process->pid = pid;
    return error;
}
#endif

#ifndef _WIN32
#ifdef __APPLE__
/* Exact SPI prototypes from Apple's libsyscall/wrappers/spawn/spawn_private.h.
 * Lookup remains parent-only; missing SPI is an explicit unsupported result. */
typedef int (*SystemSpawnUid)(const posix_spawnattr_t *, uid_t);
typedef int (*SystemSpawnGid)(const posix_spawnattr_t *, gid_t);
typedef int (*SystemSpawnGroups)(const posix_spawnattr_t *, int, gid_t *, uid_t);
static int system_apple_credentials(posix_spawnattr_t *attributes, long long uid, long long gid,
                                    gid_t *groups, size_t count) {
    SystemSpawnUid set_uid = (SystemSpawnUid)dlsym(RTLD_DEFAULT, "posix_spawnattr_set_uid_np");
    SystemSpawnGid set_gid = (SystemSpawnGid)dlsym(RTLD_DEFAULT, "posix_spawnattr_set_gid_np");
    SystemSpawnGroups set_groups = (SystemSpawnGroups)dlsym(RTLD_DEFAULT, "posix_spawnattr_set_groups_np");
    if (!set_uid || !set_gid || !set_groups) return ENOTSUP;
    if (count >= NGROUPS_MAX) return EINVAL;
    /* Darwin's group list includes the effective GID as element zero. Passing
     * zero groups makes XNU install group 0; prepend the requested/inherited
     * primary group so an empty supplementary list really drops root groups. */
    gid_t native_groups[NGROUPS_MAX];
    native_groups[0] = gid == -1 ? getegid() : (gid_t)gid;
    for (size_t i = 0; i < count; i++) native_groups[i+1] = groups[i];
    int error = gid == -1 ? 0 : set_gid(attributes, (gid_t)gid);
    /* KAUTH_UID_NONE disables memberd expansion: the explicit list is complete. */
    if (!error) error = set_groups(attributes, (int)count + 1, native_groups, (uid_t)-1);
    if (!error && uid != -1) error = set_uid(attributes, (uid_t)uid);
    return error;
}
#endif
static int system_posix_spawn(SystemProcess *process, const char *path, char **argv, char **envp,
                              const char *cwd, long long uid, long long gid, gid_t *groups, size_t count, bool credentials) {
#if defined(__linux__) && (defined(__x86_64__) || defined(__aarch64__))
    if (credentials) return system_clone_spawn(process, path, argv, envp, cwd, uid, gid, groups, count, true);
#elif !defined(__APPLE__)
    if (credentials) return ENOTSUP;
#endif
    posix_spawnattr_t attributes; posix_spawn_file_actions_t actions;
    int error = posix_spawnattr_init(&attributes);
    if (error) return error;
    bool actions_ready = false;
    sigset_t mask, defaults;
    error = pthread_sigmask(SIG_SETMASK, NULL, &mask);
    sigemptyset(&defaults); sigaddset(&defaults, SIGPIPE);
    if (!error) sigdelset(&mask, SIGPIPE);
    if (!error) error = posix_spawnattr_setsigdefault(&attributes, &defaults);
    if (!error) error = posix_spawnattr_setsigmask(&attributes, &mask);
    if (!error) error = posix_spawnattr_setflags(&attributes, POSIX_SPAWN_SETSIGDEF | POSIX_SPAWN_SETSIGMASK);
#ifdef __APPLE__
    if (!error && credentials) error = system_apple_credentials(&attributes, uid, gid, groups, count);
#else
    (void)uid; (void)gid; (void)groups; (void)count;
#endif
    if (!error) { error = posix_spawn_file_actions_init(&actions); actions_ready = !error; }
    if (!error && *cwd) {
#ifdef __APPLE__
        typedef int (*SystemSpawnChdir)(posix_spawn_file_actions_t *, const char *);
        /* Prefer macOS 26's public name, falling back to the 10.15 SPI without
         * compiling a deprecated _np call against newer SDKs. */
        SystemSpawnChdir chdir_action = (SystemSpawnChdir)dlsym(RTLD_DEFAULT, "posix_spawn_file_actions_addchdir");
        if (!chdir_action) chdir_action = (SystemSpawnChdir)dlsym(RTLD_DEFAULT, "posix_spawn_file_actions_addchdir_np");
        error = chdir_action ? chdir_action(&actions, cwd) : ENOTSUP;
#elif defined(__GLIBC__) && defined(__GLIBC_PREREQ)
#if __GLIBC_PREREQ(2, 29)
        error = posix_spawn_file_actions_addchdir_np(&actions, cwd);
#else
        error = ENOTSUP;
#endif
#else
        error = ENOTSUP;
#endif
    }
    if (!error) error = posix_spawn(&process->pid, path, &actions, &attributes, argv, envp);
    if (actions_ready) posix_spawn_file_actions_destroy(&actions);
    posix_spawnattr_destroy(&attributes);
#if defined(__linux__) && (defined(__x86_64__) || defined(__aarch64__))
    if (error == ENOTSUP && *cwd) return system_clone_spawn(process, path, argv, envp, cwd, uid, gid, groups, count, false);
#endif
    return error;
}
#else
#include "system_process_windows.h"
#endif

long long minyar_system_spawnNative(const MinyarText *path, const MinyarBytes *arguments,
    const MinyarBytes *environment, const MinyarText *cwd, long long uid, long long gid,
    const MinyarBytes *group_bytes, bool credentials) {
    system_error = 0;
    if (uid < -1 || gid < -1 || uid >= UINT32_MAX || gid >= UINT32_MAX ||
        (!credentials && (uid != -1 || gid != -1)) || !system_valid_buffer(group_bytes) || group_bytes->byte_length % 8)
        return system_failure(EINVAL);
    size_t count = (size_t)group_bytes->byte_length / 8;
    if (count > SYSTEM_VECTOR_COUNT || (!credentials && count)) return system_failure(EINVAL);
    for (size_t i = 0; i < count; i++)
        if (system_u64(group_bytes->bytes + i*8) >= UINT32_MAX) return system_failure(EINVAL);
    SystemVector argv = {0}, envp = {0};
    char *executable = system_cstring(path), *working = NULL;
    SystemProcess *process = NULL;
#ifndef _WIN32
    gid_t *groups = NULL;
#endif
    if (!executable) goto failed;
    working = system_cstring(cwd); if (!working) goto failed;
    if (!*executable) { system_error = ENOENT; goto failed; }
    if (!system_vector(arguments, &argv, false) || !system_vector(environment, &envp, true)) goto failed;
    if (system_process_serial == LLONG_MAX) { system_error = EOVERFLOW; goto failed; }
    process = calloc(1, sizeof(*process)); if (!process) { system_error = ENOMEM; goto failed; }
    if (!system_process_cleanup_installed) {
        if (atexit(system_process_cleanup)) { system_error = ENOMEM; goto failed; }
        system_process_cleanup_installed = true;
    }
#ifdef _WIN32
    system_error = credentials ? ENOTSUP : system_windows_spawn(process, executable, &argv, &envp, working);
#else
    if (credentials) {
        long maximum = sysconf(_SC_NGROUPS_MAX);
        if (maximum >= 0 && count > (size_t)maximum) { system_error = EINVAL; goto failed; }
        groups = calloc(count ? count : 1, sizeof(*groups));
        if (!groups) { system_error = ENOMEM; goto failed; }
        for (size_t i = 0; i < count; i++) {
            uint64_t value = system_u64(group_bytes->bytes + i*8); groups[i] = (gid_t)value;
            if ((uint64_t)groups[i] != value) { system_error = EINVAL; goto failed; }
        }
        if ((uid != -1 && (long long)(uid_t)uid != uid) || (gid != -1 && (long long)(gid_t)gid != gid)) {
            system_error = EINVAL; goto failed;
        }
    }
    system_error = system_posix_spawn(process, executable, argv.values, envp.values, working, uid, gid, groups, count, credentials);
#endif
failed:
    free(executable); free(working); system_vector_clear(&argv); system_vector_clear(&envp);
#ifndef _WIN32
    free(groups);
#endif
    if (system_error) { free(process); return -system_error; }
    process->handle = ++system_process_serial; process->next = system_processes; system_processes = process;
    return process->handle;
}
