/* SOURCE ONLY, uncompiled/unexecuted. Linux payload fixture, NOT a supervisor.
 * Never changes cgroups, limits or niceness. See accompanying fixture-plan.md. */
#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <linux/magic.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/statfs.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#if !defined(SYS_pidfd_open) || !defined(SYS_pidfd_send_signal) || !defined(RLIM_NLIMITS)
#error "Linux pidfd syscall and complete rlimit headers required"
#endif
#define MIB UINT64_C(1048576)
#define MAX_TOUCH (256 * MIB)
#define FIXTURE_MAX_INPUT 65536
#define MAX_TEXT 4096
struct owned { pid_t pid; int fd, direct; };
static struct owned owned[4];
static int owned_count;
static volatile sig_atomic_t term_seen;
static int term_pipe[2] = {-1, -1};
static long long millis(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t)) return -1;
    return (long long)t.tv_sec * 1000 + t.tv_nsec / 1000000;
}
static int wait_ready(int fd, short events, long long until) {
    for (;;) {
        long long now = millis();
        if (now < 0) return -1;
        if (now >= until) { errno = ETIMEDOUT; return -1; }
        struct pollfd p = {.fd = fd, .events = events};
        int n = poll(&p, 1, (int)(until - now));
        if (n < 0 && errno == EINTR) continue;
        if (n < 0) return -1;
        if (!n) { errno = ETIMEDOUT; return -1; }
        if (p.revents & events) return 0;
        errno = EIO; return -1;
    }
}
static int send_bytes(int fd, const void *data, size_t size) {
    const unsigned char *p = data;
    long long until = millis() + 5000;
    while (size) {
        if (wait_ready(fd, POLLOUT, until)) return -1;
        ssize_t n = write(fd, p, size);
        if (n < 0 && (errno == EINTR || errno == EAGAIN)) continue;
        if (n <= 0) { if (!n) errno = EIO; return -1; }
        p += n; size -= (size_t)n;
    }
    return 0;
}
static int receive(int fd, void *data, size_t size, long long until) {
    unsigned char *p = data;
    while (size) {
        if (wait_ready(fd, POLLIN | POLLHUP, until)) return -1;
        ssize_t n = read(fd, p, size);
        if (n < 0 && (errno == EINTR || errno == EAGAIN)) continue;
        if (n <= 0) { if (!n) errno = EPIPE; return -1; }
        p += n; size -= (size_t)n;
    }
    return 0;
}
static void cleanup(void) {
    for (int i = 0; i < owned_count; ++i) {
        if (owned[i].pid <= 0) continue;
        if (owned[i].fd >= 0) {
            (void)syscall(SYS_pidfd_send_signal, owned[i].fd, SIGKILL, NULL, 0);
            (void)wait_ready(owned[i].fd, POLLIN, millis() + 3000);
        } else if (owned[i].direct) {
            /* Only unreaped direct children enter this branch; no PID recycling. */
            (void)kill(owned[i].pid, SIGKILL);
        }
        if (owned[i].direct) (void)waitpid(owned[i].pid, NULL, WNOHANG);
        if (owned[i].fd >= 0) close(owned[i].fd);
    }
}
static void fail(const char *stage) {
    int saved = errno;
    char text[256];
    int n = snprintf(text, sizeof text, "{\"event\":\"fixture_error\",\"stage\":\"%s\",\"errno\":%d}\n", stage, saved);
    if (n > 0 && (size_t)n < sizeof text) (void)send_bytes(2, text, (size_t)n);
    exit(saved == ETIMEDOUT ? 75 : 70);
}
static void check(int value, const char *stage) { if (value < 0) fail(stage); }
static void require(int value, const char *stage) { if (!value) { errno = EPROTO; fail(stage); } }
static uint64_t decimal(const char *s, uint64_t low, uint64_t high) {
    uint64_t n = 0;
    if (!*s) { errno = EINVAL; fail("decimal"); }
    for (; *s; ++s) {
        if (*s < '0' || *s > '9' || n > (high - (unsigned)(*s - '0')) / 10) {
            errno = EINVAL; fail("decimal_range");
        }
        n = n * 10 + (unsigned)(*s - '0');
    }
    if (n < low || n > high) { errno = EINVAL; fail("decimal_range"); }
    return n;
}
static void read_text(int dir, const char *name, char *out, size_t size) {
    int fd = openat(dir, name, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    check(fd, name);
    ssize_t n = read(fd, out, size - 1);
    if (n < 0) { int saved = errno; close(fd); errno = saved; fail(name); }
    require((size_t)n < size - 1, "text_bound");
    out[n] = 0;
    while (n && out[n - 1] == '\n') out[--n] = 0;
    check(close(fd), "close_read");
}
static void hex(FILE *f, const void *data, size_t size) {
    const unsigned char *p = data;
    fputc('"', f);
    for (size_t i = 0; i < size; ++i) fprintf(f, "%02x", (unsigned)p[i]);
    fputc('"', f);
}
static FILE *event(char **data, size_t *size) {
    FILE *f = open_memstream(data, size);
    if (!f) fail("event_buffer");
    return f;
}
static void publish(FILE *f, char **data, size_t *size) {
    /* Use the final pointer published by fclose, including any final allocation. */
    check(fclose(f), "event_close");
    require(*size <= 2 * MIB, "event_size");
    check(send_bytes(1, *data, *size), "stdout");
    free(*data);
}
struct group {
    int fd;
    char path[MAX_TEXT], maximum[64], swap[64], oom[64], current[64], peak[64];
    char events[1024], population[256];
};
static void group_read(struct group *g) {
    char membership[MAX_TEXT], copy[MAX_TEXT], *save;
    read_text(AT_FDCWD, "/proc/self/cgroup", membership, sizeof membership);
    require(!strncmp(membership, "0::/", 4) && !strchr(membership, '\n'), "unified_membership");
    strcpy(g->path, membership + 3); strcpy(copy, g->path + 1);
    int fd = open("/sys/fs/cgroup", O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
    check(fd, "cgroup_mount");
    for (char *part = strtok_r(copy, "/", &save); part; part = strtok_r(NULL, "/", &save)) {
        require(strcmp(part, ".") && strcmp(part, ".."), "cgroup_component");
        int next = openat(fd, part, O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
        int saved = errno; close(fd); errno = saved; check(next, "cgroup_directory"); fd = next;
    }
    struct statfs fs;
    check(fstatfs(fd, &fs), "cgroup_filesystem");
    require(fs.f_type == CGROUP2_SUPER_MAGIC, "cgroup2_filesystem"); g->fd = fd;
    read_text(fd, "memory.max", g->maximum, sizeof g->maximum);
    read_text(fd, "memory.swap.max", g->swap, sizeof g->swap);
    read_text(fd, "memory.oom.group", g->oom, sizeof g->oom);
    read_text(fd, "memory.current", g->current, sizeof g->current);
    read_text(fd, "memory.peak", g->peak, sizeof g->peak);
    read_text(fd, "memory.events", g->events, sizeof g->events);
    read_text(fd, "cgroup.events", g->population, sizeof g->population);
}
static uint64_t starttime(void) {
    char text[MAX_TEXT], *save;
    read_text(AT_FDCWD, "/proc/self/stat", text, sizeof text);
    char *p = strrchr(text, ')'); require(p && p[1] == ' ', "proc_stat_comm");
    p += 2;
    for (int field = 3; field <= 22; ++field) {
        char *word = strtok_r(field == 3 ? p : NULL, " ", &save);
        require(word != NULL, "proc_stat_fields");
        if (field == 22) return decimal(word, 1, UINT64_MAX);
    }
    errno = EPROTO; fail("proc_stat_starttime"); return 0;
}
static void identity(FILE *f, const struct group *g) {
    fprintf(f, "\"pid\":%ld,\"ppid\":%ld,\"pgrp\":%ld,\"sid\":%ld,\"starttime_ticks\":%" PRIu64 ",\"cgroup_hex\":",
            (long)getpid(), (long)getppid(), (long)getpgrp(), (long)getsid(0), starttime());
    hex(f, g->path, strlen(g->path));
}
static void announce(const char *name, uint64_t bytes) {
    struct group g; group_read(&g);
    char *data = NULL; size_t size = 0; FILE *f = event(&data, &size);
    fprintf(f, "{\"event\":\"%s\",\"bytes\":%" PRIu64 ",", name, bytes); identity(f, &g);
    fprintf(f, ",\"memory_max\":\"%s\",\"swap_max\":\"%s\",\"oom_group\":\"%s\"}\n", g.maximum, g.swap, g.oom);
    check(fflush(f), "announcement_flush");
    require(size <= PIPE_BUF, "atomic_announcement_size");
    publish(f, &data, &size); close(g.fd);
}
static int track(pid_t pid, int direct) {
    require(owned_count < 4, "owned_capacity");
    int i = owned_count++; owned[i] = (struct owned){pid, -1, direct};
    owned[i].fd = (int)syscall(SYS_pidfd_open, pid, 0); check(owned[i].fd, "pidfd_open");
    return i;
}
static void child_reset(void) {
    for (int i = 0; i < owned_count; ++i) if (owned[i].fd >= 0) close(owned[i].fd);
    owned_count = 0;
}
static int reap(int index, long long until) {
    check(wait_ready(owned[index].fd, POLLIN, until), "child_deadline");
    int status; pid_t got;
    do { got = waitpid(owned[index].pid, &status, 0); } while (got < 0 && errno == EINTR);
    check((int)got, "waitpid"); require(got == owned[index].pid, "waitpid_identity");
    owned[index].pid = -1; check(close(owned[index].fd), "pidfd_close"); owned[index].fd = -1;
    return status;
}
static void term_handler(int sig) {
    (void)sig; int saved = errno; term_seen = 1;
    if (term_pipe[1] >= 0) (void)write(term_pipe[1], "T", 1);
    errno = saved;
}
static int hold(unsigned ms, int handled) {
    long long until = millis() + ms;
    while (!handled || !term_seen) {
        long long now = millis(); check(now < 0 ? -1 : 0, "clock");
        if (now >= until) return 0;
        struct pollfd p = {.fd = handled ? term_pipe[0] : -1, .events = POLLIN};
        int n = poll(handled ? &p : NULL, handled ? 1 : 0, (int)(until - now));
        if (n < 0 && errno == EINTR) continue;
        check(n, "hold_poll");
        if (n && (p.revents & (POLLERR | POLLHUP | POLLNVAL))) { errno = EIO; fail("signal_pipe"); }
    }
    return 1;
}
static uint64_t small_budget(void) {
    struct group g; group_read(&g);
    require(!strcmp(g.swap, "0") && !strcmp(g.oom, "1"), "expected_memory_policy");
    char score[64]; read_text(AT_FDCWD, "/proc/self/oom_score_adj", score, sizeof score);
    require(strcmp(score, "-1000"), "oom_immune_fixture");
    uint64_t n = decimal(g.maximum, 8 * MIB, 256 * MIB); close(g.fd); return n;
}
static unsigned char *map_touch(size_t bytes) {
    void *p = mmap(NULL, bytes, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (p == MAP_FAILED) fail("touch_mmap");
    check(madvise(p, bytes, MADV_NOHUGEPAGE), "no_transparent_hugepage_hint");
    return p;
}
static void touch(unsigned char *p, size_t bytes) {
    long page = sysconf(_SC_PAGESIZE); require(page > 0 && page <= 1048576, "page_size");
    volatile unsigned char *v = p;
    for (size_t i = 0; i < bytes; i += (size_t)page) v[i] = 0xa5;
    v[bytes - 1] = 0x5a;
}
static void inspect_fds(FILE *f, int closed_group_fd) {
    DIR *directory = opendir("/proc/self/fd");
    if (!directory) fail("fd_enumeration");
    int enumeration_fd = dirfd(directory); check(enumeration_fd, "enumeration_fd");
    int enumeration_flags = fcntl(enumeration_fd, F_GETFD); check(enumeration_flags, "enumeration_flags");
    int count = 0;
    fputs(",\"open_fds\":[", f);
    for (;;) {
        errno = 0; struct dirent *entry = readdir(directory);
        if (!entry) { if (errno) fail("fd_readdir"); break; }
        if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..")) continue;
        int fd = (int)decimal(entry->d_name, 0, INT_MAX);
        if (fd == enumeration_fd) continue; /* Only live descriptor excluded. */
        require(count < 256, "fd_observation_bound");
        int flags = fcntl(fd, F_GETFD); check(flags, "fd_flags");
        int status_flags = fcntl(fd, F_GETFL); check(status_flags, "fd_status_flags");
        char target[MAX_TEXT]; ssize_t n = readlinkat(enumeration_fd, entry->d_name, target, sizeof target);
        if (n < 0) fail("fd_readlink");
        require((size_t)n < sizeof target, "fd_target_bound");
        if (count++) fputc(',', f);
        fprintf(f, "{\"fd\":%d,\"fd_flags\":%d,\"close_on_exec\":%s,\"status_flags\":%d,\"target_hex\":",
                fd, flags, flags & FD_CLOEXEC ? "true" : "false", status_flags);
        hex(f, target, (size_t)n); fputc('}', f);
    }
    check(closedir(directory), "fd_enumeration_close");
    fprintf(f, "],\"fd_snapshot\":{\"excluded\":[{\"fd\":%d,\"fd_flags\":%d,\"reason\":\"fixture opendir enumeration\",\"closed\":true}],\"cgroup_inspection_fd_closed_before_snapshot\":%d,\"other_proc_inspection_fds_closed\":true}",
            enumeration_fd, enumeration_flags, closed_group_fd);
}
static void inspect(int argc, char **argv) {
    const char *keys[16]; int count = 0, index = 2;
    while (index < argc && !strcmp(argv[index], "--env")) {
        require(index + 1 < argc && count < 16, "env_arguments");
        const char *key = argv[index + 1]; size_t n = strlen(key);
        require(n && n <= 128 && !strchr(key, '='), "env_name");
        for (int i = 0; i < count; ++i) require(strcmp(keys[i], key), "duplicate_env_name");
        keys[count++] = key; index += 2;
    }
    require(index < argc && !strcmp(argv[index], "--") && argc - index - 1 <= 32, "literal_argv_separator");
    unsigned char input[FIXTURE_MAX_INPUT + 1]; size_t used = 0;
    long long until = millis() + 5000;
    for (;;) {
        check(wait_ready(0, POLLIN | POLLHUP, until), "stdin_deadline");
        ssize_t n = read(0, input + used, sizeof input - used);
        if (n < 0 && (errno == EINTR || errno == EAGAIN)) continue;
        check((int)n, "stdin"); if (!n) break;
        used += (size_t)n; require(used <= FIXTURE_MAX_INPUT, "stdin_bound");
    }
    char cwd[MAX_TEXT]; if (!getcwd(cwd, sizeof cwd)) fail("cwd");
    struct group g; group_read(&g);
    int closed_group_fd = g.fd; check(close(g.fd), "inspect_group_close"); g.fd = -1;
    char score[64]; read_text(AT_FDCWD, "/proc/self/oom_score_adj", score, sizeof score);
    errno = 0; int nice = getpriority(PRIO_PROCESS, 0); if (errno) fail("nice");
    /* Single-threaded inspect: restore immediately, before any file creation. */
    mode_t mask = umask(0); mode_t temporary_mask = umask(mask);
    require(temporary_mask == 0, "umask_restore");
    char *data = NULL; size_t size = 0; FILE *f = event(&data, &size);
    fprintf(f, "{\"event\":\"inspect\","); identity(f, &g);
    fprintf(f, ",\"nice\":%d,\"oom_score_adj\":\"%s\",\"umask_octal\":\"%04o\",\"umask_restored\":true,\"cwd_hex\":",
            nice, score, (unsigned)mask); hex(f, cwd, strlen(cwd));
    fputs(",\"argv_hex\":[", f);
    for (int i = 0; i < argc; ++i) { if (i) fputc(',', f); hex(f, argv[i], strlen(argv[i])); }
    fputs("],\"environment\":[", f);
    for (int i = 0; i < count; ++i) {
        const char *value = getenv(keys[i]); if (i) fputc(',', f);
        fputs("{\"name_hex\":", f); hex(f, keys[i], strlen(keys[i])); fputs(",\"value_hex\":", f);
        if (value) { require(strlen(value) <= MAX_TEXT, "env_value_bound"); hex(f, value, strlen(value)); }
        else fputs("null", f);
        fputc('}', f);
    }
    fputs("],\"stdin_hex\":", f); hex(f, input, used); fputs(",\"rlimits\":[", f);
    for (int i = 0; i < RLIM_NLIMITS; ++i) {
        struct rlimit r; check(getrlimit(i, &r), "getrlimit");
        if (i) fputc(',', f); fprintf(f, "{\"resource\":%d,\"soft\":", i);
        if (r.rlim_cur == RLIM_INFINITY) fputs("\"infinity\"", f); else fprintf(f, "%" PRIuMAX, (uintmax_t)r.rlim_cur);
        fputs(",\"hard\":", f);
        if (r.rlim_max == RLIM_INFINITY) fputs("\"infinity\"", f); else fprintf(f, "%" PRIuMAX, (uintmax_t)r.rlim_max);
        fputc('}', f);
    }
    fprintf(f, "],\"memory_max\":\"%s\",\"swap_max\":\"%s\",\"oom_group\":\"%s\",\"memory_current\":\"%s\",\"memory_peak\":\"%s\",\"memory_events_hex\":",
            g.maximum, g.swap, g.oom, g.current, g.peak);
    hex(f, g.events, strlen(g.events)); fputs(",\"cgroup_events_hex\":", f); hex(f, g.population, strlen(g.population));
    inspect_fds(f, closed_group_fd);
    fputs("}\n", f); publish(f, &data, &size);
    static const unsigned char out[] = {'o','u','t',0,255,'\n'}, err[] = {'e','r','r',0,255,'\n'};
    check(send_bytes(1, out, sizeof out), "stdout_sentinel"); check(send_bytes(2, err, sizeof err), "stderr_sentinel");
}
static void aggregate(size_t bytes, unsigned ms) {
    uint64_t budget = small_budget(); require(bytes < budget && (uint64_t)bytes * 2 > budget, "aggregate_shape");
    int ready_pipe[2], go[2]; check(pipe2(ready_pipe, O_NONBLOCK | O_CLOEXEC), "ready_pipe"); check(pipe2(go, O_NONBLOCK | O_CLOEXEC), "go_pipe");
    int children[2];
    for (int i = 0; i < 2; ++i) {
        pid_t pid = fork(); check((int)pid, "aggregate_fork");
        if (!pid) {
            child_reset(); close(ready_pipe[0]); close(go[1]);
            unsigned char *p = map_touch(bytes); announce("aggregate-child-ready", bytes);
            check(send_bytes(ready_pipe[1], "R", 1), "child_ready"); close(ready_pipe[1]);
            char value; check(receive(go[0], &value, 1, millis() + 5000), "child_barrier"); require(value == 'G', "go_value"); close(go[0]);
            touch(p, bytes); announce("aggregate-child-touched", bytes); (void)hold(ms, 0);
            check(munmap(p, bytes), "child_unmap"); exit(0);
        }
        children[i] = track(pid, 1);
    }
    close(ready_pipe[1]); close(go[0]); char both[2];
    check(receive(ready_pipe[0], both, 2, millis() + 5000), "both_children_ready");
    require(both[0] == 'R' && both[1] == 'R', "ready_values"); close(ready_pipe[0]);
    announce("aggregate-release", (uint64_t)bytes * 2); check(send_bytes(go[1], "GG", 2), "release_children"); close(go[1]);
    long long until = millis() + ms + 5000;
    for (int i = 0; i < 2; ++i) {
        int status = reap(children[i], until);
        require(WIFEXITED(status) && WEXITSTATUS(status) == 0, "aggregate_child_status");
    }
    announce("aggregate-completed-without-oom-claim", (uint64_t)bytes * 2);
}
struct receipt { pid_t pid; uint64_t ticks; };
static void orphan(const char *path, unsigned ms, unsigned release_ms) {
    require(path[0] == '/' && strlen(path) < MAX_TEXT, "absolute_evidence_path");
    int notice[2]; check(pipe2(notice, O_NONBLOCK | O_CLOEXEC), "orphan_pipe");
    pid_t middle = fork(); check((int)middle, "orphan_fork");
    if (!middle) {
        child_reset(); close(notice[0]); pid_t grandchild = fork(); check((int)grandchild, "grandchild_fork");
        if (grandchild) _exit(0);
        check((int)setsid(), "grandchild_setsid");
        struct group g; group_read(&g);
        int fd = open(path, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK, 0600);
        check(fd, "fresh_evidence_file");
        struct stat st; check(fstat(fd, &st), "evidence_stat"); require(S_ISREG(st.st_mode) && st.st_uid == geteuid() && st.st_nlink == 1 && !(st.st_mode & 0077), "private_regular_evidence");
        char *data = NULL; size_t size = 0; FILE *f = event(&data, &size);
        fputs("{\"event\":\"detached-grandchild\",", f); identity(f, &g); fputs("}\n", f);
        check(fflush(f), "orphan_event_flush"); check(fclose(f), "orphan_event_close");
        check(send_bytes(fd, data, size), "evidence_write"); free(data); check(close(fd), "evidence_close"); close(g.fd);
        struct receipt r; memset(&r, 0, sizeof r); r.pid = getpid(); r.ticks = starttime();
        close(0); close(1); close(2); /* Drain EOF cannot stand in for descendant cleanup. */
        if (send_bytes(notice[1], &r, sizeof r)) _exit(70);
        close(notice[1]); (void)hold(ms, 0); _exit(76);
    }
    int direct = track(middle, 1); close(notice[1]); struct receipt r;
    check(receive(notice[0], &r, sizeof r, millis() + 5000), "grandchild_receipt"); close(notice[0]);
    require(r.pid > 0 && r.ticks, "grandchild_identity"); int detached = track(r.pid, 0);
    int status = reap(direct, millis() + 5000); require(WIFEXITED(status) && WEXITSTATUS(status) == 0, "middle_status");
    char *data = NULL; size_t size = 0; FILE *f = event(&data, &size);
    fprintf(f, "{\"event\":\"orphan-awaiting-stdin-G\",\"leader_pid\":%ld,\"grandchild_pid\":%ld,\"starttime_ticks\":%" PRIu64 ",\"evidence_path_hex\":",
            (long)getpid(), (long)r.pid, r.ticks);
    hex(f, path, strlen(path)); fputs("}\n", f); publish(f, &data, &size);
    char go; check(receive(0, &go, 1, millis() + release_ms), "orphan_external_release"); require(go == 'G', "orphan_release_value");
    /* Success intentionally leaves this bounded-lived descendant for supervisor cleanup. */
    owned[detached].pid = -1; check(close(owned[detached].fd), "orphan_pidfd_close"); owned[detached].fd = -1;
}
int main(int argc, char **argv) {
    if (argc < 2 || argc > 96) return 64;
    for (int i = 0; i < argc; ++i) if (strlen(argv[i]) > MAX_TEXT) return 64;
    struct sigaction sa = {.sa_handler = SIG_DFL}; sigemptyset(&sa.sa_mask);
    check(sigaction(SIGCHLD, &sa, NULL), "sigchld_default"); sa.sa_handler = SIG_IGN;
    check(sigaction(SIGPIPE, &sa, NULL), "sigpipe_ignore");
    for (int fd = 1; fd <= 2; ++fd) { int flags = fcntl(fd, F_GETFL); check(flags, "stdio_flags"); check(fcntl(fd, F_SETFL, flags | O_NONBLOCK), "stdio_nonblocking"); }
    require(atexit(cleanup) == 0, "cleanup_registration");
    const char *mode = argv[1];
    if (!strcmp(mode, "inspect")) { inspect(argc, argv); return 0; }
    if (!strcmp(mode, "sparse") && argc == 3 && !strcmp(argv[2], "2147483648")) {
        require(sizeof(void *) == 8 && SIZE_MAX >= UINT64_C(2147483648), "64_bit_sparse"); announce("sparse-start", UINT64_C(2147483648));
        void *p = mmap(NULL, (size_t)UINT64_C(2147483648), PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        if (p == MAP_FAILED) fail("sparse_mmap"); check(munmap(p, (size_t)UINT64_C(2147483648)), "sparse_unmap");
        announce("sparse-unmapped", UINT64_C(2147483648)); return 0;
    }
    if ((!strcmp(mode, "touch") || !strcmp(mode, "aggregate")) && argc == 4) {
        size_t bytes = (size_t)decimal(argv[2], 4096, MAX_TOUCH); unsigned ms = (unsigned)decimal(argv[3], 1, 10000);
        if (!strcmp(mode, "aggregate")) { aggregate(bytes, ms); return 0; }
        (void)small_budget(); announce("touch-start", bytes); unsigned char *p = map_touch(bytes);
        touch(p, bytes); announce("touch-completed", bytes); (void)hold(ms, 0); check(munmap(p, bytes), "touch_unmap"); return 0;
    }
    if (!strcmp(mode, "exit37") && argc == 2) { announce("exit37", 0); return 37; }
    if (!strcmp(mode, "abrt") && argc == 2) {
        sa.sa_handler = SIG_DFL; check(sigaction(SIGABRT, &sa, NULL), "abrt_default");
        sigset_t set; sigemptyset(&set); sigaddset(&set, SIGABRT); check(sigprocmask(SIG_UNBLOCK, &set, NULL), "abrt_unblock");
        announce("abrt-ready", 0); check(raise(SIGABRT), "raise_abrt"); return 72;
    }
    if (!strcmp(mode, "term") && argc == 4 && (!strcmp(argv[2], "handled") || !strcmp(argv[2], "ignore"))) {
        unsigned ms = (unsigned)decimal(argv[3], 1, 15000); int handled = !strcmp(argv[2], "handled");
        if (handled) { check(pipe2(term_pipe, O_NONBLOCK | O_CLOEXEC), "term_pipe"); sa.sa_handler = term_handler; }
        else sa.sa_handler = SIG_IGN;
        check(sigaction(SIGTERM, &sa, NULL), "term_action");
        sigset_t set; sigemptyset(&set); sigaddset(&set, SIGTERM); check(sigprocmask(SIG_UNBLOCK, &set, NULL), "term_unblock");
        announce(handled ? "term-handled-ready" : "term-ignore-ready", 0);
        if (hold(ms, handled)) { announce("term-handled", 0); return 0; }
        announce("term-local-deadline", 0); return 75;
    }
    if ((!strcmp(mode, "orphan") || !strcmp(mode, "orphan-hold")) && argc == 4) {
        orphan(argv[2], (unsigned)decimal(argv[3], 10000, 60000), !strcmp(mode, "orphan-hold") ? 60000 : 5000);
        return 0;
    }
    return 64;
}
