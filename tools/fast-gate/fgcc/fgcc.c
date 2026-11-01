// fgcc: a content-addressed cache in front of Clang for fast-gate shards.
//
// Installed in the shard image as /opt/fgcc/bin/clang (never in place of the toolchain's own clang, which checks
// inspect) and used as the gate's fixture Clang (TEST_CLANG) when a run asks for it, it execs the real compiler
// unless the invocation is one it can prove it may replay: a compile or link whose every input is
// a regular file and whose only output is the -o file. The key covers this program's version, the real compiler and
// both linkers, the system packages (dpkg status: crt objects, libc), argv with the -o path replaced by its extension,
// the working directory, the environment variables Clang and the linkers read, the bytes of every input file and
// library, and for C-family sources the preprocessed translation unit. A hit writes the stored output atomically
// (as Clang does), replays stdout, stderr and the exit status and nothing else. Only successful compiles are stored.
// It is plain C so it runs under the gate's 768 MiB address-space limit exactly like Clang.
//
// /home/agent/fgcc/config holds KEY=VALUE lines: mode=off|log|cache|verify, dir=<cache directory>, log=<jsonl file>.
// Without it every invocation is a plain exec of clang-23. verify recompiles every hit into a temporary file and
// records whether the output, stdout, stderr and status are identical; a mismatching entry is never used.
#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define VERSION "fgcc-c1"
#define REAL "/opt/llvm-23.1.3/bin/clang-23"
#define CONFIG "/home/agent/fgcc/config"

// ---- SHA-256 (FIPS 180-4) ----
typedef struct { uint32_t h[8]; uint64_t n; uint8_t b[64]; size_t used; } sha256;
static const uint32_t K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01,
    0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
    0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
    0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08,
    0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};
#define ROR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))
static void sha_block(sha256 *s, const uint8_t *p) {
    uint32_t w[64], a, b, c, d, e, f, g, h;
    for (int i = 0; i < 16; i++) w[i] = (uint32_t)p[4 * i] << 24 | (uint32_t)p[4 * i + 1] << 16 | (uint32_t)p[4 * i + 2] << 8 | p[4 * i + 3];
    for (int i = 16; i < 64; i++) {
        uint32_t s0 = ROR(w[i - 15], 7) ^ ROR(w[i - 15], 18) ^ (w[i - 15] >> 3), s1 = ROR(w[i - 2], 17) ^ ROR(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    a = s->h[0], b = s->h[1], c = s->h[2], d = s->h[3], e = s->h[4], f = s->h[5], g = s->h[6], h = s->h[7];
    for (int i = 0; i < 64; i++) {
        uint32_t t1 = h + (ROR(e, 6) ^ ROR(e, 11) ^ ROR(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i];
        uint32_t t2 = (ROR(a, 2) ^ ROR(a, 13) ^ ROR(a, 22)) + ((a & b) ^ (a & c) ^ (b & c));
        h = g, g = f, f = e, e = d + t1, d = c, c = b, b = a, a = t1 + t2;
    }
    s->h[0] += a, s->h[1] += b, s->h[2] += c, s->h[3] += d, s->h[4] += e, s->h[5] += f, s->h[6] += g, s->h[7] += h;
}
static void sha_init(sha256 *s) {
    static const uint32_t iv[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
    memcpy(s->h, iv, sizeof iv), s->n = 0, s->used = 0;
}
static void sha_add(sha256 *s, const void *data, size_t len) {
    const uint8_t *p = data;
    s->n += len;
    if (s->used) {
        size_t take = 64 - s->used < len ? 64 - s->used : len;
        memcpy(s->b + s->used, p, take), s->used += take, p += take, len -= take;
        if (s->used == 64) sha_block(s, s->b), s->used = 0;
    }
    for (; len >= 64; p += 64, len -= 64) sha_block(s, p);
    if (len) memcpy(s->b, p, len), s->used = len;
}
static void sha_hex(sha256 *s, char out[65]) {
    uint64_t bits = s->n * 8;
    uint8_t pad = 0x80, zero = 0, len[8];
    sha_add(s, &pad, 1);
    while (s->used != 56) sha_add(s, &zero, 1);
    for (int i = 0; i < 8; i++) len[i] = (uint8_t)(bits >> (56 - 8 * i));
    sha_add(s, len, 8);
    for (int i = 0; i < 8; i++) sprintf(out + 8 * i, "%08x", s->h[i]);
}
static void sha_str(sha256 *s, const char *tag, const char *value) {
    sha_add(s, tag, strlen(tag)), sha_add(s, "=", 1), sha_add(s, value, strlen(value)), sha_add(s, "\0", 1);
}

// ---- small helpers ----
static char mode[16] = "off", dir[4096], logpath[4096];
static int has_prefix(const char *s, const char *p) { return strncmp(s, p, strlen(p)) == 0; }
static const char *ext(const char *path) {
    const char *slash = strrchr(path, '/'), *dot = strrchr(path, '.');
    return dot && (!slash || dot > slash) ? dot : "";
}
static double now(void) { struct timespec t; clock_gettime(CLOCK_REALTIME, &t); return t.tv_sec + t.tv_nsec / 1e9; }
static int hash_file(const char *path, char out[65]) {
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) return -1;
    struct stat st;
    if (fstat(fd, &st) != 0 || !S_ISREG(st.st_mode)) { close(fd); return -1; }
    sha256 s; sha_init(&s);
    static char buf[1 << 16];
    ssize_t n;
    while ((n = read(fd, buf, sizeof buf)) > 0) sha_add(&s, buf, (size_t)n);
    close(fd);
    if (n < 0) return -1;
    sha_hex(&s, out);
    return 0;
}
// A tool's identity: resolved path + content hash, memoised per box under dir/identity (keyed by size and mtime).
static void identity(sha256 *key, const char *path) {
    char resolved[4096], memo[8192], digest[65];
    struct stat st;
    if (!realpath(path, resolved) || stat(resolved, &st) != 0) { sha_str(key, "tool-missing", path); return; }
    snprintf(memo, sizeof memo, "%s/identity/", dir);
    mkdir(memo, 0755);
    size_t at = strlen(memo);
    for (const char *p = resolved; *p && at < sizeof memo - 64; p++) memo[at++] = *p == '/' ? '_' : *p;
    snprintf(memo + at, sizeof memo - at, "-%lld-%lld", (long long)st.st_size, (long long)st.st_mtim.tv_sec);
    FILE *f = fopen(memo, "r");
    if (f && fscanf(f, "%64s", digest) == 1 && strlen(digest) == 64) { fclose(f); }
    else {
        if (f) fclose(f);
        if (hash_file(resolved, digest) != 0) { sha_str(key, "tool-unreadable", resolved); return; }
        char tmp[8300]; snprintf(tmp, sizeof tmp, "%s.%d", memo, getpid());
        if ((f = fopen(tmp, "w"))) { fprintf(f, "%s\n", digest); fclose(f); rename(tmp, memo); }
    }
    sha_str(key, "tool", resolved), sha_str(key, "tool-hash", digest);
}
static void read_config(void) {
    FILE *f = fopen(CONFIG, "r");
    if (!f) return;
    char line[8192];
    while (fgets(line, sizeof line, f)) {
        line[strcspn(line, "\r\n")] = 0;
        char *eq = strchr(line, '=');
        if (!eq) continue;
        *eq = 0;
        if (!strcmp(line, "mode")) snprintf(mode, sizeof mode, "%s", eq + 1);
        else if (!strcmp(line, "dir")) snprintf(dir, sizeof dir, "%s", eq + 1);
        else if (!strcmp(line, "log")) snprintf(logpath, sizeof logpath, "%s", eq + 1);
    }
    fclose(f);
}
static void passthrough(char **argv) {
    execv(REAL, argv);
    fprintf(stderr, "fgcc: exec %s: %s\n", REAL, strerror(errno));
    _exit(127);
}

// ---- running the real driver ----
typedef struct { char *data; size_t len, cap; } buffer;
static void buf_add(buffer *b, const char *p, size_t n) {
    if (b->len + n + 1 > b->cap) { b->cap = (b->len + n + 1) * 2; b->data = realloc(b->data, b->cap); }
    memcpy(b->data + b->len, p, n), b->len += n, b->data[b->len] = 0;
}
static void write_all(int fd, const char *p, size_t n) {
    while (n) { ssize_t w = write(fd, p, n); if (w < 0) { if (errno == EINTR) continue; return; } p += w, n -= (size_t)w; }
}
// Runs REAL with argv (argv[0] kept). stdout/stderr are captured into out/err and, when tee is set, also forwarded.
// When hash is set, stdout is hashed instead of buffered. Returns the wait status.
static int run_real(char **argv, buffer *out, buffer *err, int tee, sha256 *hash) {
    int po[2], pe[2];
    if (pipe2(po, O_CLOEXEC) || pipe2(pe, O_CLOEXEC)) return -1;
    pid_t pid = fork();
    if (pid < 0) return -1;
    if (pid == 0) {
        dup2(po[1], 1), dup2(pe[1], 2);
        execv(REAL, argv);
        _exit(127);
    }
    close(po[1]), close(pe[1]);
    struct pollfd fds[2] = {{po[0], POLLIN, 0}, {pe[0], POLLIN, 0}};
    int open_fds = 2;
    static char chunk[1 << 16];
    while (open_fds) {
        if (poll(fds, 2, -1) < 0) { if (errno == EINTR) continue; break; }
        for (int i = 0; i < 2; i++) {
            if (fds[i].fd < 0 || !(fds[i].revents & (POLLIN | POLLHUP | POLLERR))) continue;
            ssize_t n = read(fds[i].fd, chunk, sizeof chunk);
            if (n <= 0) { close(fds[i].fd), fds[i].fd = -1, open_fds--; continue; }
            if (i == 0 && hash) sha_add(hash, chunk, (size_t)n);
            else buf_add(i == 0 ? out : err, chunk, (size_t)n);
            if (tee) write_all(i == 0 ? 1 : 2, chunk, (size_t)n);
        }
    }
    int status = 0;
    while (waitpid(pid, &status, 0) < 0 && errno == EINTR) {}
    return status;
}
// Leave the way the real driver left: same exit code, or the same signal.
static void exit_like(int status) {
    if (WIFSIGNALED(status)) { signal(WTERMSIG(status), SIG_DFL); raise(WTERMSIG(status)); }
    exit(WIFEXITED(status) ? WEXITSTATUS(status) : 127);
}

// ---- analysis ----
static const char *separate[] = {"-o", "-I", "-L", "-D", "-U", "-isystem", "-idirafter", "-iquote", "-isysroot", "-MT", "-MQ",
    "-arch", "-target", "-Xlinker", "-Xassembler", "-Xpreprocessor", "-mllvm", "-z", "-T", "-u", "-e", "--param", "-framework",
    "-rpath", "--sysroot", "-resource-dir", "-l", NULL};
static const char *refuse_exact[] = {"-E", "-M", "-MM", "-MD", "-MMD", "-MF", "-MT", "-MQ", "-###", "-v", "--version", "-dumpversion",
    "-dumpmachine", "-fsyntax-only", "-save-temps", "-gsplit-dwarf", "-ftime-trace", "-working-directory", "-", "-fmodules",
    "-Xclang", "-x", "-include", "-imacros", "-pipe", NULL};
static const char *refuse_prefix[] = {"@", "-print", "--print", "-fprofile", "-Wl,@", "-MF", "-fsanitize-ignorelist", "-fsanitize-blacklist",
    "-fmodule", "-fcrash", "-fdebug-prefix-map", "-ffile-prefix-map", "-fmacro-prefix-map", "-save-temps", "-ftime-trace", "-o", NULL};
static int in_list(const char *s, const char **list) { for (; *list; list++) if (!strcmp(s, *list)) return 1; return 0; }
static int prefix_list(const char *s, const char **list) { for (; *list; list++) if (has_prefix(s, *list)) return 1; return 0; }
static int is_c(const char *e) { return !strcmp(e, ".c") || !strcmp(e, ".cc") || !strcmp(e, ".cpp") || !strcmp(e, ".cxx") || !strcmp(e, ".m") || !strcmp(e, ".mm") || !strcmp(e, ".S") || !strcmp(e, ".s"); }
static int is_bin(const char *e) { return !strcmp(e, ".ll") || !strcmp(e, ".bc") || !strcmp(e, ".o") || !strcmp(e, ".a") || !strcmp(e, ".so"); }

typedef struct { int cacheable; char reason[512]; const char *output; char key[65]; int output_index; } analysis;

static int find_library(const char *name, char **dirs, int ndirs, char *found, size_t size) {
    static const char *system_dirs[] = {"/usr/lib/x86_64-linux-gnu", "/lib/x86_64-linux-gnu", "/usr/lib", "/lib", "/usr/local/lib", NULL};
    for (int pass = 0; pass < 2; pass++) {
        for (int i = 0; pass == 0 ? i < ndirs : system_dirs[i] != NULL; i++) {
            const char *d = pass == 0 ? dirs[i] : system_dirs[i];
            for (int kind = 0; kind < 2; kind++) {
                snprintf(found, size, "%s/lib%s.%s", d, name, kind == 0 ? "so" : "a");
                struct stat st;
                if (stat(found, &st) == 0 && S_ISREG(st.st_mode)) return 0;
            }
        }
    }
    return -1;
}

static analysis analyse(int argc, char **argv, const char *cwd) {
    analysis a = {0};
    a.output_index = -1;
    int compile_only = 0, sources = 0, ninputs = 0, nlibs = 0, nlibdirs = 0;
    char **inputs = calloc((size_t)argc, sizeof *inputs), **libs = calloc((size_t)argc, sizeof *libs), **libdirs = calloc((size_t)argc, sizeof *libdirs);
    int *input_is_c = calloc((size_t)argc, sizeof *input_is_c);
    for (int i = 1; i < argc; i++) {
        const char *arg = argv[i];
        if (in_list(arg, refuse_exact) || (prefix_list(arg, refuse_prefix) && strcmp(arg, "-o")) || strstr(arg, "thinlto-cache")) {
            snprintf(a.reason, sizeof a.reason, "option %s", arg);
            return a;
        }
        if (!strcmp(arg, "-c") || !strcmp(arg, "-S")) compile_only = 1;
        if (!strcmp(arg, "-o")) {
            if (i + 1 >= argc || a.output) { snprintf(a.reason, sizeof a.reason, "output"); return a; }
            a.output = argv[i + 1], a.output_index = i + 1, i++;
            continue;
        }
        if (!strcmp(arg, "-L") && i + 1 < argc) libdirs[nlibdirs++] = argv[i + 1];
        else if (has_prefix(arg, "-L")) libdirs[nlibdirs++] = (char *)arg + 2;
        if (has_prefix(arg, "-l") && strlen(arg) > 2) libs[nlibs++] = (char *)arg + 2;
        if (has_prefix(arg, "-Wl,") || (!strcmp(arg, "-Xlinker") && i + 1 < argc)) {
            // Linker options naming files (version scripts, linker scripts): their bytes are inputs too.
            char copy[4096];
            snprintf(copy, sizeof copy, "%s", has_prefix(arg, "-Wl,") ? arg + 4 : argv[i + 1]);
            for (char *part = strtok(copy, ","); part; part = strtok(NULL, ",")) {
                char *value = strchr(part, '=') ? strchr(part, '=') + 1 : part;
                struct stat st;
                char path[8192];
                if (*value && *value != '-') {
                    snprintf(path, sizeof path, "%s%s%s", value[0] == '/' ? "" : cwd, value[0] == '/' ? "" : "/", value);
                    if (stat(path, &st) == 0 && S_ISREG(st.st_mode)) inputs[ninputs++] = strdup(value);
                }
            }
        }
        if (in_list(arg, separate) && i + 1 < argc) { i++; continue; }
        if (arg[0] != '-') {
            const char *e = ext(arg);
            if (!is_c(e) && !is_bin(e)) { snprintf(a.reason, sizeof a.reason, "input %s", arg); return a; }
            if (is_c(e)) sources++, input_is_c[ninputs] = 1;
            inputs[ninputs++] = (char *)arg;
        }
    }
    if (!a.output) { snprintf(a.reason, sizeof a.reason, "no -o"); return a; }
    if (!ninputs) { snprintf(a.reason, sizeof a.reason, "no inputs"); return a; }
    if (sources > 1) { snprintf(a.reason, sizeof a.reason, "several sources"); return a; }

    sha256 key;
    sha_init(&key);
    sha_str(&key, "version", VERSION);
    identity(&key, REAL), identity(&key, "/opt/llvm-23.1.3/bin/ld.lld"), identity(&key, "/usr/bin/ld"), identity(&key, "/var/lib/dpkg/status");
    sha_str(&key, "argv0", strrchr(argv[0], '/') ? strrchr(argv[0], '/') + 1 : argv[0]);
    sha_str(&key, "cwd", cwd);
    for (int i = 1; i < argc; i++) sha_str(&key, "arg", i == a.output_index ? ext(argv[i]) : argv[i]);
    extern char **environ;
    static const char *env_exact[] = {"CPATH", "LIBRARY_PATH", "COMPILER_PATH", "SOURCE_DATE_EPOCH", "LD_RUN_PATH", "LD_LIBRARY_PATH",
        "SDKROOT", "MACOSX_DEPLOYMENT_TARGET", "ZERO_AR_DATE", "LLVM_PROFILE_FILE", "RC_DEBUG_OPTIONS", "PATH", "LANG", "LC_ALL",
        "LC_CTYPE", NULL};
    static const char *env_prefix[] = {"C_INCLUDE", "CPLUS_INCLUDE", "OBJC_INCLUDE", "CCC_", "CLANG_", "LLVM_", "ASAN_", "UBSAN_", "LSAN_", NULL};
    for (char **e = environ; *e; e++) {
        char name[256];
        size_t n = strcspn(*e, "=");
        if (n >= sizeof name) continue;
        memcpy(name, *e, n), name[n] = 0;
        if (in_list(name, env_exact) || prefix_list(name, env_prefix)) sha_str(&key, "env", *e);
    }
    for (int i = 0; i < ninputs; i++) {
        char path[8192], digest[65];
        snprintf(path, sizeof path, "%s%s%s", inputs[i][0] == '/' ? "" : cwd, inputs[i][0] == '/' ? "" : "/", inputs[i]);
        if (hash_file(path, digest) != 0) { snprintf(a.reason, sizeof a.reason, "input %s", inputs[i]); return a; }
        sha_str(&key, "input", inputs[i]), sha_str(&key, "input-hash", digest);
    }
    if (!compile_only) {
        for (int i = 0; i < nlibs; i++) {
            char found[8192], digest[65];
            if (find_library(libs[i], libdirs, nlibdirs, found, sizeof found) != 0 || hash_file(found, digest) != 0) {
                snprintf(a.reason, sizeof a.reason, "library %s", libs[i]);
                return a;
            }
            sha_str(&key, "lib", found), sha_str(&key, "lib-hash", digest);
        }
    }
    if (sources == 1) {
        // The preprocessed unit covers every header and macro; the real driver produces it with the same flags.
        char **pre = calloc((size_t)argc + 4, sizeof *pre);
        int n = 0;
        pre[n++] = argv[0];
        for (int i = 1; i < argc; i++) {
            if (!strcmp(argv[i], "-o")) { i++; continue; }
            if (!strcmp(argv[i], "-c") || !strcmp(argv[i], "-S") || has_prefix(argv[i], "-l") || has_prefix(argv[i], "-Wl,") ||
                has_prefix(argv[i], "-fuse-ld") || !strcmp(argv[i], "-pthread") || !strcmp(argv[i], "-shared") || !strcmp(argv[i], "-static")) continue;
            if (!strcmp(argv[i], "-Xlinker") || !strcmp(argv[i], "-L") || !strcmp(argv[i], "-z") || !strcmp(argv[i], "-T") || !strcmp(argv[i], "-rpath")) { i++; continue; }
            if (has_prefix(argv[i], "-L")) continue;
            if (argv[i][0] != '-' && is_bin(ext(argv[i]))) continue;
            pre[n++] = argv[i];
        }
        pre[n++] = "-E", pre[n++] = "-o", pre[n++] = "-";
        pre[n] = NULL;
        sha256 unit;
        sha_init(&unit);
        buffer out = {0}, err = {0};
        int status = run_real(pre, &out, &err, 0, &unit);
        if (!WIFEXITED(status) || WEXITSTATUS(status) != 0 || err.len) { snprintf(a.reason, sizeof a.reason, "preprocess"); return a; }
        char digest[65];
        sha_hex(&unit, digest);
        sha_str(&key, "preprocessed", digest);
    }
    sha_hex(&key, a.key);
    a.cacheable = 1;
    return a;
}

// ---- cache entries: DIR/kk/KEY/{output,stdout,stderr,meta} ----
static int copy_file(const char *from, const char *to, mode_t perm) {
    int in = open(from, O_RDONLY | O_CLOEXEC);
    if (in < 0) return -1;
    int out = open(to, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, perm);
    if (out < 0) { close(in); return -1; }
    static char buf[1 << 16];
    ssize_t n;
    int rc = 0;
    while ((n = read(in, buf, sizeof buf)) > 0) { if (write(out, buf, (size_t)n) != n) { rc = -1; break; } }
    if (n < 0) rc = -1;
    close(in);
    if (close(out) != 0) rc = -1;
    return rc;
}
static int same_file(const char *a, const char *b) {
    int x = open(a, O_RDONLY | O_CLOEXEC), y = open(b, O_RDONLY | O_CLOEXEC);
    int same = x >= 0 && y >= 0;
    static char p[1 << 16], q[1 << 16];
    while (same) {
        ssize_t m = read(x, p, sizeof p), n = m > 0 ? read(y, q, (size_t)m) : read(y, q, 1);
        if (m < 0 || n != (m > 0 ? m : 0)) { same = 0; break; }
        if (m == 0) break;
        if (memcmp(p, q, (size_t)m)) same = 0;
    }
    if (x >= 0) close(x);
    if (y >= 0) close(y);
    return same;
}
static int read_small(const char *path, buffer *b) {
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) return -1;
    char chunk[8192];
    ssize_t n;
    while ((n = read(fd, chunk, sizeof chunk)) > 0) buf_add(b, chunk, (size_t)n);
    close(fd);
    if (!b->data) buf_add(b, "", 0);
    return n < 0 ? -1 : 0;
}
static void write_small(const char *path, const buffer *b) {
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
    if (fd >= 0) { write_all(fd, b->data ? b->data : "", b->len); close(fd); }
}
static int same_buffer(const buffer *a, const buffer *b) { return a->len == b->len && (!a->len || !memcmp(a->data, b->data, a->len)); }

static void json_string(FILE *f, const char *s) {
    fputc('"', f);
    for (; *s; s++) {
        unsigned char c = (unsigned char)*s;
        if (c == '"' || c == '\\') fprintf(f, "\\%c", c);
        else if (c < 0x20) fprintf(f, "\\u%04x", c);
        else fputc(c, f);
    }
    fputc('"', f);
}
static void log_record(int argc, char **argv, const char *cwd, const analysis *a, const char *result, int status, double start, double analysis_s) {
    if (!*logpath) return;
    FILE *f = fopen(logpath, "a");
    if (!f) return;
    fprintf(f, "{\"t\": %.3f, \"d\": %.4f, \"ad\": %.4f, \"ok\": %s, \"res\": \"%s\", \"st\": %d, \"cwd\": ", start, now() - start, analysis_s,
        a->cacheable ? "true" : "false", result, status);
    json_string(f, cwd);
    fprintf(f, ", \"why\": "), json_string(f, a->reason);
    fprintf(f, ", \"key\": "), json_string(f, a->cacheable ? a->key : "");
    const char *label = getenv("MINYAR_CHECK_LABEL");
    fprintf(f, ", \"label\": "), json_string(f, label ? label : "");
    fprintf(f, ", \"args\": [");
    for (int i = 1; i < argc; i++) { if (i > 1) fputs(", ", f); json_string(f, argv[i]); }
    fputs("]}\n", f);
    fclose(f);
}

int main(int argc, char **argv) {
    read_config();
    if (!strcmp(mode, "off") || !*dir) passthrough(argv);
    // As tools/clang-cache.min: checks that measure budgets, performance or timing always compile for real.
    const char *label = getenv("MINYAR_CHECK_LABEL"), *disable = getenv("MINYAR_DISABLE_COMPILER_CACHE");
    if ((disable && !strcmp(disable, "1")) || (label && (strstr(label, "budget") || strstr(label, "performance") ||
        strstr(label, "timing") || strstr(label, "measurement")))) passthrough(argv);
    double start = now();
    char cwd[4096];
    if (!getcwd(cwd, sizeof cwd)) passthrough(argv);
    analysis a = analyse(argc, argv, cwd);
    double analysis_s = now() - start;
    buffer out = {0}, err = {0};
    if (!a.cacheable || !strcmp(mode, "log")) {
        int status = run_real(argv, &out, &err, 1, NULL);
        log_record(argc, argv, cwd, &a, "run", WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status), start, analysis_s);
        exit_like(status);
    }
    char output[8192], entry[8192], path[8400];
    snprintf(output, sizeof output, "%s%s%s", a.output[0] == '/' ? "" : cwd, a.output[0] == '/' ? "" : "/", a.output);
    snprintf(entry, sizeof entry, "%s/%.2s/%s", dir, a.key, a.key);
    buffer meta = {0}, cached_out = {0}, cached_err = {0};
    snprintf(path, sizeof path, "%s/meta", entry);
    int cached_status = -1;
    unsigned perm = 0644;
    if (read_small(path, &meta) == 0 && sscanf(meta.data, "status %d mode %o", &cached_status, &perm) == 2) {
        snprintf(path, sizeof path, "%s/stdout", entry), read_small(path, &cached_out);
        snprintf(path, sizeof path, "%s/stderr", entry), read_small(path, &cached_err);
        const char *result = "hit";
        if (!strcmp(mode, "verify")) {
            // Recompile into a temporary file next to the output and compare everything the caller could observe.
            char fresh[8400];
            snprintf(fresh, sizeof fresh, "%s.fgcc-verify-%d", output, getpid());
            char **vargv = calloc((size_t)argc + 1, sizeof *vargv);
            for (int i = 0; i < argc; i++) vargv[i] = i == a.output_index ? fresh : argv[i];
            int status = run_real(vargv, &out, &err, 0, NULL);
            snprintf(path, sizeof path, "%s/output", entry);
            int same = WIFEXITED(status) && WEXITSTATUS(status) == cached_status && same_file(fresh, path) &&
                same_buffer(&out, &cached_out) && same_buffer(&err, &cached_err);
            unlink(fresh);
            result = same ? "verified" : "MISMATCH";
            if (!same) {
                out.len = err.len = 0;
                status = run_real(argv, &out, &err, 1, NULL);
                log_record(argc, argv, cwd, &a, result, WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status), start, analysis_s);
                exit_like(status);
            }
        }
        char temporary[8400];
        snprintf(temporary, sizeof temporary, "%s.fgcc-%d", output, getpid());
        snprintf(path, sizeof path, "%s/output", entry);
        mode_t mask = umask(0);
        umask(mask);
        if (copy_file(path, temporary, (mode_t)perm & ~mask) == 0 && chmod(temporary, (mode_t)perm & ~mask) == 0 && rename(temporary, output) == 0) {
            write_all(1, cached_out.data ? cached_out.data : "", cached_out.len);
            write_all(2, cached_err.data ? cached_err.data : "", cached_err.len);
            log_record(argc, argv, cwd, &a, result, cached_status, start, analysis_s);
            exit(cached_status);
        }
        unlink(temporary);
    }
    int status = run_real(argv, &out, &err, 1, NULL);
    if (WIFEXITED(status) && WEXITSTATUS(status) == 0) {
        struct stat st;
        char fill[8400];
        snprintf(fill, sizeof fill, "%s/.fill-%d-%ld", dir, getpid(), (long)(start * 1000));
        if (stat(output, &st) == 0 && S_ISREG(st.st_mode) && mkdir(fill, 0755) == 0) {
            snprintf(path, sizeof path, "%s/output", fill);
            int ok = copy_file(output, path, 0644) == 0;
            buffer m = {0};
            char line[64];
            snprintf(line, sizeof line, "status 0 mode %o\n", (unsigned)(st.st_mode & 07777));
            buf_add(&m, line, strlen(line));
            snprintf(path, sizeof path, "%s/stdout", fill), write_small(path, &out);
            snprintf(path, sizeof path, "%s/stderr", fill), write_small(path, &err);
            snprintf(path, sizeof path, "%s/meta", fill), write_small(path, &m);
            snprintf(path, sizeof path, "%s/%.2s", dir, a.key);
            mkdir(path, 0755);
            if (!ok || rename(fill, entry) != 0) {
                char rm[8600]; snprintf(rm, sizeof rm, "rm -rf '%s'", fill);
                if (system(rm)) {}
            }
        }
    }
    log_record(argc, argv, cwd, &a, "miss", WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status), start, analysis_s);
    exit_like(status);
}
