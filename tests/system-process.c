#define _GNU_SOURCE 1
#include "system-test-values.h"
#include "../runtime/native/system.c"
#ifndef _WIN32
#include <sys/stat.h>
#include <sys/wait.h>
#include <grp.h>
#else
#include <io.h>
#endif
static void test_cwd(char *out, size_t capacity) {
#ifdef _WIN32
    wchar_t wide[4096];
    assert(GetCurrentDirectoryW(4096, wide));
    assert(WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, wide, -1, out, (int)capacity, NULL, NULL));
    for (char *at = out; *at; at++) if (*at == '\\') *at = '/';
#else
    assert(getcwd(out, capacity));
#endif
}

static void put64(unsigned char *out, uint64_t value) {
    for (unsigned i = 0; i < 8; i++) out[i] = (unsigned char)(value >> (8*i));
}
static long long get64(const MinyarBytes *bytes, unsigned at) {
    uint64_t value = 0;
    for (unsigned i = 0; i < 8; i++) value |= (uint64_t)bytes->bytes[at+i] << (8*i);
    return (long long)value;
}
static MinyarBytes *pack(const char **strings, size_t count) {
    size_t length = 8;
    for (size_t i = 0; i < count; i++) length += 8 + strlen(strings[i]);
    MinyarBytes *result = minyar_bytes_new((long long)length);
    unsigned char *out = (unsigned char *)result->bytes; put64(out, count); out += 8;
    for (size_t i = 0; i < count; i++) {
        size_t n = strlen(strings[i]); put64(out, n); out += 8; memcpy(out, strings[i], n); out += n;
    }
    return result;
}
static long long launch(const char *path, const char **args, size_t argc, const char **env, size_t envc,
                        const char *cwd, long long uid, long long gid, const MinyarBytes *groups, bool credentials) {
    MinyarText p = test_text(path), working = test_text(cwd);
    MinyarBytes *a = pack(args, argc), *e = pack(env, envc);
    long long handle = minyar_system_spawnNative(&p, a, e, &working, uid, gid, groups, credentials);
    test_release(a); test_release(e); return handle;
}
static void exited(long long handle, long long exit_code) {
    assert(handle > 0 && minyar_system_childProcessId(handle) > 0);
    MinyarBytes *status = minyar_system_waitNative(handle, false);
    assert(status->byte_length == 32 && get64(status, 0) == 0 && get64(status, 8) == 1);
    assert(get64(status, 16) == exit_code && get64(status, 24) == 0); test_release(status);
    status = minyar_system_waitNative(handle, true);
    assert(get64(status, 0) == -ECHILD); test_release(status);
    assert(minyar_system_childProcessId(handle) == -ECHILD);
}
static int child(int argc, char **argv) {
    if (argc < 2 || strncmp(argv[1], "child-", 6)) return -1;
    if (!strcmp(argv[1], "child-arguments")) {
        assert(argc == 8 && !strcmp(argv[0], "custom name"));
        const char *expected[] = {"", "with space", "quote\"slash\\", "trail\\", "λ☃", ";$HOME*"};
        for (int i = 0; i < 6; i++) assert(!strcmp(argv[i+2], expected[i]));
#ifdef _WIN32
        wchar_t value[32]; assert(GetEnvironmentVariableW(L"EXPLICIT", value, 32) && !wcscmp(value, L"λ=☃"));
        SetLastError(ERROR_SUCCESS); assert(!GetEnvironmentVariableW(L"EMPTY", value, 32) && !GetLastError());
        assert(!GetEnvironmentVariableW(L"MINYAR_PARENT_ONLY", value, 32) && GetLastError() == ERROR_ENVVAR_NOT_FOUND);
#else
        assert(getenv("EXPLICIT") && !strcmp(getenv("EXPLICIT"), "λ=☃"));
        assert(getenv("EMPTY") && !*getenv("EMPTY")); assert(!getenv("MINYAR_PARENT_ONLY"));
#endif
    } else if (!strcmp(argv[1], "child-empty")) {
#ifdef _WIN32
        wchar_t *env = GetEnvironmentStringsW(); assert(env && !*env); FreeEnvironmentStringsW(env);
#else
#ifdef __APPLE__
        char **environ = *_NSGetEnviron();
#endif
        assert(!environ || !environ[0]);
#endif
    } else if (!strcmp(argv[1], "child-cwd")) {
        char cwd[4096];
        test_cwd(cwd, sizeof(cwd)); assert(!strcmp(cwd, argv[2]));
    } else if (!strcmp(argv[1], "child-pipe")) {
#ifndef _WIN32
        struct sigaction action; sigset_t mask;
        assert(!sigaction(SIGPIPE, NULL, &action) && action.sa_handler == SIG_DFL);
        assert(!sigprocmask(SIG_SETMASK, NULL, &mask) && !sigismember(&mask, SIGPIPE));
        assert(sigismember(&mask, SIGUSR1));
        raise(SIGPIPE); assert(!"SIGPIPE must terminate");
#endif
    } else if (!strcmp(argv[1], "child-fds")) {
#ifdef _WIN32
        DWORD flags; HANDLE handle = (HANDLE)(uintptr_t)strtoull(argv[2], NULL, 10);
        assert(!GetHandleInformation(handle, &flags));
#else
        assert(fcntl(atoi(argv[2]), F_GETFD) == -1 && errno == EBADF);
        assert(fcntl(atoi(argv[3]), F_GETFD) >= 0);
#endif
    } else if (!strcmp(argv[1], "child-sleep")) {
#ifdef _WIN32
        Sleep(1000);
#else
        sleep(1);
#endif
        return 37;
    } else if (!strcmp(argv[1], "child-credentials")) {
#ifndef _WIN32
        assert(getuid() == 65534 && geteuid() == 65534 && getgid() == 65534 && getegid() == 65534);
        gid_t groups[16]; int n = getgroups(16, groups); assert(n >= 0);
        int extras = 0;
        for (int i = 0; i < n; i++) { assert(groups[i] == 777 || groups[i] == 888 || groups[i] == 65534); if (groups[i] != 65534) extras++; }
        assert(extras == 2);
#endif
    } else if (!strcmp(argv[1], "child-exit")) return 127;
    else assert(!"unknown child mode");
    return 0;
}
static int process_main(int argc, char **argv) {
    int result = child(argc, argv); if (result >= 0) return result;
    assert(argc == 3);
    MinyarBytes *groups = minyar_bytes_new(0);
    const char *args[] = {"custom name", "child-arguments", "", "with space", "quote\"slash\\", "trail\\", "λ☃", ";$HOME*"};
    const char *env[] = {"EXPLICIT=λ=☃", "EMPTY="};
    exited(launch(argv[0], args, 8, env, 2, "", -1, -1, groups, false), 0);
    const char *simple[] = {"custom name", "child-empty"};
    exited(launch(argv[0], simple, 2, NULL, 0, "", -1, -1, groups, false), 0);
    char previous[4096];
    test_cwd(previous, sizeof(previous));
    const char *cwd[] = {"custom name", "child-cwd", argv[2]};
    exited(launch(argv[0], cwd, 3, NULL, 0, argv[2], -1, -1, groups, false), 0);
    char after[4096];
    test_cwd(after, sizeof(after));
    assert(!strcmp(previous, after));
    simple[1] = "child-exit"; exited(launch(argv[0], simple, 2, NULL, 0, "", -1, -1, groups, false), 127);
    assert(launch("/minyar/no-such-executable", simple, 2, NULL, 0, "", -1, -1, groups, false) == -ENOENT);
    assert(launch(argv[0], simple, 2, NULL, 0, "/minyar/no-such-directory", -1, -1, groups, false) == -ENOENT);
    assert(launch(argv[0], NULL, 0, NULL, 0, "", -1, -1, groups, false) == -EINVAL);
    const char *bad_env[] = {"NOT_AN_ASSIGNMENT"};
    assert(launch(argv[0], simple, 2, bad_env, 1, "", -1, -1, groups, false) == -EINVAL);
    assert(launch(argv[0], simple, 2, NULL, 0, "", -2, -1, groups, true) == -EINVAL);
    assert(launch(argv[0], simple, 2, NULL, 0, "", 4294967295LL, -1, groups, true) == -EINVAL);
    assert(launch(argv[0], simple, 2, NULL, 0, "", -1, LLONG_MAX, groups, true) == -EINVAL);
    MinyarText path = test_text(argv[0]), working = test_text("");
    MinyarBytes *packed = pack(simple, 2), *empty = pack(NULL, 0);
    /* A NUL cannot be reinterpreted as another argv element. */
    ((unsigned char *)packed->bytes)[16] = 0;
    assert(minyar_system_spawnNative(&path, packed, empty, &working, -1, -1, groups, false) == -EINVAL);
    test_release(packed);
    packed = pack(simple, 2); packed->byte_length--;
    assert(minyar_system_spawnNative(&path, packed, empty, &working, -1, -1, groups, false) == -EINVAL);
    test_release(packed);
    packed = pack(simple, 2);
    MinyarText nul = {(const unsigned char *)"/bad\0tail", 9, 0, NULL, NULL};
    assert(minyar_system_spawnNative(&nul, packed, empty, &working, -1, -1, groups, false) == -EINVAL);
    MinyarBytes *bad_groups = minyar_bytes_new(8); put64((unsigned char *)bad_groups->bytes, UINT32_MAX);
    assert(minyar_system_spawnNative(&path, packed, empty, &working, -1, -1, bad_groups, true) == -EINVAL);
    test_release(packed); test_release(empty); test_release(bad_groups);

    simple[1] = "child-sleep";
    long long handle = launch(argv[0], simple, 2, NULL, 0, "", -1, -1, groups, false);
    assert(handle > 0);
    MinyarBytes *pending = minyar_system_waitNative(handle, true);
    assert(get64(pending, 0) == 0 && get64(pending, 8) == 0); test_release(pending); exited(handle, 37);
    const char *fd_args[] = {"custom name", "child-fds", "", ""};
    char first[32], second[32];
#ifdef _WIN32
    HANDLE fd = CreateEventW(NULL, TRUE, FALSE, NULL); assert(fd);
    assert(SetHandleInformation(fd, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT));
    snprintf(first, sizeof(first), "%llu", (unsigned long long)(uintptr_t)fd);
    fd_args[2] = first;
    exited(launch(argv[0], fd_args, 3, NULL, 0, "", -1, -1, groups, false), 0); CloseHandle(fd);
    simple[1] = "child-exit";
    assert(launch(argv[0], simple, 2, NULL, 0, "", -1, -1, groups, true) == -ENOTSUP);
    (void)second;
#else
    uid_t parent_uid = getuid(), parent_euid = geteuid();
    gid_t parent_gid = getgid(), parent_egid = getegid(), parent_groups[SYSTEM_VECTOR_COUNT], after_groups[SYSTEM_VECTOR_COUNT];
    int parent_count = getgroups(SYSTEM_VECTOR_COUNT, parent_groups); assert(parent_count >= 0);
    int excluded = open("/dev/null", O_RDONLY | O_CLOEXEC), inherited = open("/dev/null", O_RDONLY);
    assert(excluded >= 0 && inherited >= 0);
    snprintf(first, sizeof(first), "%d", excluded); snprintf(second, sizeof(second), "%d", inherited);
    fd_args[2] = first; fd_args[3] = second;
    exited(launch(argv[0], fd_args, 4, NULL, 0, "", -1, -1, groups, false), 0);
    close(excluded); close(inherited);
    struct sigaction saved, ignored; sigset_t mask, saved_mask, current;
    memset(&ignored, 0, sizeof(ignored)); ignored.sa_handler = SIG_IGN;
    assert(!sigaction(SIGPIPE, &ignored, &saved));
    sigemptyset(&mask); sigaddset(&mask, SIGPIPE); sigaddset(&mask, SIGUSR1);
    assert(!sigprocmask(SIG_BLOCK, &mask, &saved_mask));
    simple[1] = "child-pipe";
    handle = launch(argv[0], simple, 2, NULL, 0, "", -1, -1, groups, false); assert(handle > 0);
    MinyarBytes *status = minyar_system_waitNative(handle, false);
    assert(get64(status, 0) == 0 && get64(status, 8) == 2 && get64(status, 24) == SIGPIPE); test_release(status);
    assert(!sigaction(SIGPIPE, NULL, &ignored) && ignored.sa_handler == SIG_IGN);
    assert(!sigprocmask(SIG_SETMASK, NULL, &current) && sigismember(&current, SIGPIPE) && sigismember(&current, SIGUSR1));
    simple[1] = "child-exit";
    long long credential = launch(argv[0], simple, 2, NULL, 0, "", -1, -1, groups, true);
    if (geteuid()) assert(credential == -EPERM);
    else {
        exited(credential, 127);
        MinyarBytes *extras = minyar_bytes_new(16); put64((unsigned char *)extras->bytes, 777); put64((unsigned char *)extras->bytes + 8, 888);
        simple[1] = "child-credentials";
        exited(launch(argv[0], simple, 2, NULL, 0, "", 65534, 65534, extras, true), 0); test_release(extras);
        simple[1] = "child-pipe";
        handle = launch(argv[0], simple, 2, NULL, 0, "", -1, -1, groups, true); assert(handle > 0);
        status = minyar_system_waitNative(handle, false);
        assert(get64(status, 0) == 0 && get64(status, 8) == 2 && get64(status, 24) == SIGPIPE); test_release(status);
        assert(launch("/minyar/no-such-executable", simple, 2, NULL, 0, "", -1, -1, groups, true) == -ENOENT);
    }
    assert(!sigaction(SIGPIPE, NULL, &ignored) && ignored.sa_handler == SIG_IGN);
    assert(!sigprocmask(SIG_SETMASK, NULL, &current) && sigismember(&current, SIGPIPE));
    assert(!sigaction(SIGPIPE, &saved, NULL)); assert(!sigprocmask(SIG_SETMASK, &saved_mask, NULL));
    assert(getuid() == parent_uid && geteuid() == parent_euid && getgid() == parent_gid && getegid() == parent_egid);
    int after_count = getgroups(SYSTEM_VECTOR_COUNT, after_groups);
    assert(after_count == parent_count && !memcmp(parent_groups, after_groups, (size_t)parent_count * sizeof(gid_t)));
#endif
    test_release(groups); puts("system process: passed"); return 0;
}
#ifdef _WIN32
int wmain(int argc, wchar_t **wide) {
    char **argv = calloc((size_t)argc + 1, sizeof(*argv)); assert(argv);
    for (int i = 0; i < argc; i++) {
        int length = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, wide[i], -1, NULL, 0, NULL, NULL); assert(length);
        argv[i] = malloc((size_t)length); assert(argv[i]);
        assert(WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, wide[i], -1, argv[i], length, NULL, NULL));
    }
    int result = process_main(argc, argv);
    for (int i = 0; i < argc; i++) free(argv[i]); free(argv); return result;
}
#else
int main(int argc, char **argv) { return process_main(argc, argv); }
#endif
