/* SOURCE DRAFT ONLY. No compilation/execution has qualified this backend.
 * Linux LP64/systemd255; cooperating same-UID repository tests, not a sandbox.
 * Companion launcher owns request creation and unit lifetime. No default use.
 * Wire: MYMEM001, little-endian u64 schema/budget/wall/setup/grace/cleanup,
 * client PID/startticks/nice(two's complement)/umask/UID/GID/16; sixteen
 * (infinity flags, finite soft, finite hard) triples; affinity byte count and
 * raw mask; supplementary-group count and u64 GIDs; six length-prefixed byte
 * strings nonce/unit/state/socket/cwd/executable; counted argv and env strings.
 * Strings forbid NUL. Only control paths are restricted to safe ASCII. */
#define _GNU_SOURCE
#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <linux/magic.h>
#include <linux/sched.h>
#include <poll.h>
#include <sched.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/statfs.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#if !defined(__linux__) || !defined(SYS_clone3) || !defined(SYS_pidfd_open) || !defined(CLONE_INTO_CGROUP) || !defined(CLONE_PIDFD)
#error "Linux headers with clone3, pidfd_open and native cgroup admission required"
#endif
_Static_assert(sizeof(void *) == 8 && sizeof(long) == 8 && sizeof(rlim_t) == 8 && RLIM_NLIMITS == 16, "v1 requires Linux LP64 and 16 rlimits");
_Static_assert(sizeof(uid_t)==4&&sizeof(gid_t)==4,"v1 requires Linux 32-bit credential IDs");
_Static_assert(RLIMIT_CPU == 0 && RLIMIT_AS == 9 && RLIMIT_RTTIME == 15, "unexpected resource ABI");
#define MAX_REQUEST (16U * 1024U * 1024U)
#define MAX_VECTOR 65536U
#define TEXT_CAP 4096
#define MAX_AFFINITY 8192U
#define CHILD_TAG UINT32_C(0x4d594d31)
static const char *const limit_names[16] = {"CPU","FSIZE","DATA","STACK","CORE","RSS","NPROC","NOFILE","MEMLOCK","AS","LOCKS","SIGPENDING","MSGQUEUE","NICE","RTPRIO","RTTIME"};
static volatile sig_atomic_t caught_signal;
static int wake_write = -1;
static int protocol_error(void) { errno = EPROTO; return -1; }
static long long now_ms(void) { struct timespec t; return clock_gettime(CLOCK_MONOTONIC, &t) ? -1 : (long long)t.tv_sec * 1000 + t.tv_nsec / 1000000; }
static void interrupted(int sig) { int saved = errno; if (sig != SIGCHLD && !caught_signal) caught_signal = sig; if (wake_write >= 0) { unsigned char b = (unsigned char)sig; (void)write(wake_write, &b, 1); } errno = saved; }
static int wait_fd(int fd, short events, long long deadline) {
    for (;;) {
        long long left = deadline - now_ms(); if (left <= 0) { errno = ETIMEDOUT; return -1; }
        struct pollfd p = {.fd=fd, .events=events}; int n = poll(&p, 1, left > INT_MAX ? INT_MAX : (int)left);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) { if (!n) errno = ETIMEDOUT; return -1; }
        if (p.revents & events) return 0;
        errno = EPIPE; return -1;
    }
}
static int write_all(int fd, const void *data, size_t size) {
    const unsigned char *p = data;
    while (size) { ssize_t n = write(fd, p, size); if (n < 0 && errno == EINTR) continue; if (n <= 0) return -1; p += n; size -= (size_t)n; }
    return 0;
}
static int socket_write(int fd, const void *data, size_t size, long long deadline) {
    const unsigned char *p = data;
    while (size) { ssize_t n = send(fd, p, size, MSG_NOSIGNAL); if (n < 0 && errno == EINTR) continue; if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) { if (wait_fd(fd, POLLOUT, deadline)) return -1; continue; } if (n <= 0) return -1; p += n; size -= (size_t)n; }
    return 0;
}
static int read_fd(int fd, char *s, size_t cap) {
    if (lseek(fd, 0, SEEK_SET) < 0) return -1;
    ssize_t n; do { n = read(fd, s, cap - 1); } while (n < 0 && errno == EINTR);
    if (n < 0) return -1; if ((size_t)n == cap - 1) { errno = EOVERFLOW; return -1; } s[n] = 0; return 0;
}
static int read_at(int dir, const char *name, char *s, size_t cap) {
    int fd = openat(dir, name, O_RDONLY|O_CLOEXEC|O_NOFOLLOW); if (fd < 0) return -1;
    int result = read_fd(fd, s, cap), saved = errno; close(fd); errno = saved; return result;
}
static int write_at(int dir, const char *name, const char *value) {
    int fd = openat(dir, name, O_WRONLY|O_CLOEXEC|O_NOFOLLOW); if (fd < 0) return -1;
    ssize_t n = write(fd, value, strlen(value)); int saved = errno; close(fd); errno = saved;
    if (n < 0) return -1; if ((size_t)n != strlen(value)) { errno = EIO; return -1; } return 0;
}
static bool token(const char *s, const char *word) {
    size_t n = strlen(word);
    for (const char *p = s; (p = strstr(p, word)); ++p) if ((p == s || isspace((unsigned char)p[-1])) && (!p[n] || isspace((unsigned char)p[n]))) return true;
    return false;
}
static int counter(const char *s, const char *key, unsigned long long *value) {
    size_t size = strlen(key);
    for (const char *p = s; *p;) {
        if (!strncmp(p, key, size) && p[size] == ' ') { char *end; errno = 0; unsigned long long v = strtoull(p + size + 1, &end, 10); if (errno || (*end && *end != '\n')) return protocol_error(); *value = v; return 0; }
        const char *next = strchr(p, '\n'); if (!next) break; p = next + 1;
    }
    errno = ENOENT; return -1;
}
static int start_ticks(pid_t pid, unsigned long long *result) {
    char name[64], text[4096]; snprintf(name, sizeof name, "/proc/%ld/stat", (long)pid);
    if (read_at(AT_FDCWD, name, text, sizeof text)) return -1;
    char *p = strrchr(text, ')'); if (!p) return protocol_error(); p++;
    for (int field = 3; field <= 22; field++) {
        while (*p == ' ') p++; if (!*p) return protocol_error();
        char *end = p; while (*end && *end != ' ' && *end != '\n') end++;
        if (field == 22) { char saved = *end; *end = 0; char *after; errno = 0; *result = strtoull(p, &after, 10); bool valid = !errno && after != p && !*after; *end = saved; return valid ? 0 : protocol_error(); } p = end;
    }
    return protocol_error();
}
static void json_string(FILE *f, const char *s) {
    if (!s) { fputs("null", f); return; } fputc('"', f);
    for (const unsigned char *p = (const unsigned char *)s; *p; p++) { if (*p == '"' || *p == '\\') fprintf(f, "\\%c", *p); else if (*p < 32 || *p >= 127) fprintf(f, "\\u%04x", (unsigned)*p); else fputc(*p, f); } fputc('"', f);
}
static void json_limit(FILE *f, rlim_t v) { if (v == RLIM_INFINITY) fputs("null", f); else fprintf(f, "\"%llu\"", (unsigned long long)v); }
static unsigned char *affinity_get(size_t *size) {
    for(size_t n=128;n<=MAX_AFFINITY;n*=2){unsigned char *mask=calloc(1,n);if(!mask)return NULL;if(!sched_getaffinity(0,n,(cpu_set_t *)mask)){*size=n;return mask;}int saved=errno;free(mask);if(saved!=EINVAL){errno=saved;return NULL;}}
    errno=EOVERFLOW;return NULL;
}
static void json_affinity(FILE *f,const unsigned char *mask,size_t size){fputc('[',f);bool first=true;for(size_t i=0;i<size*8;i++)if(mask[i/8]&(1U<<(i%8))){if(!first)fputc(',',f);fprintf(f,"%zu",i);first=false;}fputc(']',f);}
static int gid_compare(const void *a,const void *b){gid_t x=*(const gid_t *)a,y=*(const gid_t *)b;return (x>y)-(x<y);}
static gid_t *groups_get(size_t *size){
    int n=getgroups(0,NULL);if(n<0)return NULL;if(n>65536){errno=EOVERFLOW;return NULL;}
    gid_t *groups=malloc((n?(size_t)n:1)*sizeof *groups);if(!groups)return NULL;
    int count=getgroups(n,groups);if(count<0||count>n){int saved=errno?errno:EPROTO;free(groups);errno=saved;return NULL;}
    qsort(groups,(size_t)count,sizeof *groups,gid_compare);*size=0;for(int i=0;i<count;i++)if(!*size||groups[i]!=groups[*size-1])groups[(*size)++]=groups[i];return groups;
}
static void json_groups(FILE *f,const gid_t *groups,size_t size){fputc('[',f);for(size_t i=0;i<size;i++){if(i)fputc(',',f);fprintf(f,"%lu",(unsigned long)groups[i]);}fputc(']',f);}
static int groups_match(const gid_t *expected,size_t count){size_t observed_count;gid_t *observed=groups_get(&observed_count);if(!observed)return -1;bool same=count==observed_count&&(!count||!memcmp(expected,observed,count*sizeof *expected));free(observed);return same?0:protocol_error();}
static int capture(void) {
    struct rlimit limits[16]; for (int i = 0; i < 16; i++) if (getrlimit(i, &limits[i])) return 125;
    errno = 0; int nice_value = getpriority(PRIO_PROCESS, 0); if (errno) return 125;
    mode_t mask = umask(0); umask(mask); unsigned long long ticks; pid_t client = getppid();
    if (start_ticks(client, &ticks) || getppid() != client) return 125;
    printf("{\"schema\":1,\"client_pid\":%ld,\"client_start_ticks\":\"%llu\",\"uid\":%lu,\"gid\":%lu,\"nice\":%d,\"umask\":%u,\"rlimits\":[", (long)client, ticks, (unsigned long)getuid(), (unsigned long)getgid(), nice_value, (unsigned)mask);
    for (int i = 0; i < 16; i++) { if (i) putchar(','); printf("{\"id\":%d,\"name\":\"%s\",\"soft\":", i, limit_names[i]); json_limit(stdout, limits[i].rlim_cur); fputs(",\"hard\":", stdout); json_limit(stdout, limits[i].rlim_max); putchar('}'); }
    size_t affinity_size=0;unsigned char *affinity=affinity_get(&affinity_size);if(!affinity)return 125;
    size_t group_count=0;gid_t *groups=groups_get(&group_count);if(!groups){free(affinity);return 125;}
    printf("],\"affinity_mask_bytes\":%zu,\"affinity\":",affinity_size);json_affinity(stdout,affinity,affinity_size);fputs(",\"supplementary_groups\":",stdout);json_groups(stdout,groups,group_count);puts("}");free(groups);free(affinity);return ferror(stdout) ? 125 : 0;
}
struct Request {
    uint64_t memory, wall, setup, grace, cleanup, client, ticks; int nice_value; mode_t mask; uid_t uid; gid_t gid;
    struct rlimit limits[16];size_t affinity_size,group_count;gid_t *groups;unsigned char *affinity,*affinity_observed;char *nonce, *unit, *state, *socket, *cwd, *executable; char **argv, **environment;
};
struct Decode { unsigned char *data; size_t size, at; int error; };
static uint64_t number(struct Decode *d) {
    if (d->error || d->size - d->at < 8) { d->error = EPROTO; return 0; }
    uint64_t v = 0; for (unsigned i = 0; i < 8; i++) v |= (uint64_t)d->data[d->at++] << (8*i); return v;
}
static char *string(struct Decode *d) {
    uint64_t n = number(d); if (d->error || n > d->size - d->at || n > MAX_REQUEST || memchr(d->data + d->at, 0, (size_t)n)) { d->error = EPROTO; return NULL; }
    char *s = malloc((size_t)n + 1); if (!s) { d->error = ENOMEM; return NULL; } memcpy(s, d->data + d->at, (size_t)n); s[n] = 0; d->at += (size_t)n; return s;
}
static char **vector(struct Decode *d, bool environment) {
    uint64_t count = number(d); if (d->error || count > MAX_VECTOR || count > (d->size - d->at)/8) { d->error = EPROTO; return NULL; }
    char **v = calloc((size_t)count + 1, sizeof *v); if (!v) { d->error = ENOMEM; return NULL; }
    for (size_t i = 0; i < count && !d->error; i++) { v[i] = string(d); if (environment && v[i] && (!strchr(v[i], '=') || v[i][0] == '=')) d->error = EPROTO; } return v;
}
static bool safe_path(const char *s) { if (!s || s[0] != '/' || strlen(s) >= 1024) return false; for (; *s; s++) if (!((*s>='A'&&*s<='Z')||(*s>='a'&&*s<='z')||(*s>='0'&&*s<='9')||strchr("/._-",*s))) return false; return true; }
static int request_read(const char *name, struct Request *r) {
    int fd = open(name, O_RDONLY|O_CLOEXEC|O_NOFOLLOW); if (fd < 0) return -1; struct stat st;
    if (fstat(fd, &st) || !S_ISREG(st.st_mode) || st.st_uid != getuid() || (st.st_mode & 0777) != 0600 || st.st_size < 8 || st.st_size > MAX_REQUEST) { close(fd); return protocol_error(); }
    struct Decode d = {.data=malloc((size_t)st.st_size), .size=(size_t)st.st_size}; if (!d.data) { close(fd); return -1; }
    size_t got = 0; while (got < d.size) { ssize_t n = read(fd, d.data + got, d.size - got); if (n < 0 && errno == EINTR) continue; if (n <= 0) { close(fd); free(d.data); return protocol_error(); } got += (size_t)n; } close(fd);
    if (memcmp(d.data, "MYMEM001", 8)) { free(d.data); return protocol_error(); } d.at = 8;
    if (number(&d) != 1) d.error = EPROTO;
    r->memory = number(&d); r->wall = number(&d); r->setup = number(&d); r->grace = number(&d); r->cleanup = number(&d);
    r->client = number(&d); r->ticks = number(&d); uint64_t nice_raw=number(&d),mask_raw=number(&d),uid_raw=number(&d),gid_raw=number(&d);
    int64_t nice_signed;memcpy(&nice_signed,&nice_raw,sizeof nice_signed);
    if(nice_signed < -20||nice_signed>19||mask_raw>0777||uid_raw!=getuid()||gid_raw!=getgid())d.error=EPROTO;
    r->nice_value=(int)nice_signed;r->mask=(mode_t)mask_raw;r->uid=(uid_t)uid_raw;r->gid=(gid_t)gid_raw;
    if (number(&d) != 16) d.error = EPROTO;
    for (int i = 0; i < 16; i++) { uint64_t flags = number(&d), soft = number(&d), hard = number(&d); if (flags > 3 || (!(flags&1) && soft == UINT64_MAX) || (!(flags&2) && hard == UINT64_MAX)) d.error = EPROTO; r->limits[i].rlim_cur = flags&1 ? RLIM_INFINITY : soft; r->limits[i].rlim_max = flags&2 ? RLIM_INFINITY : hard; if (r->limits[i].rlim_cur > r->limits[i].rlim_max) d.error = EPROTO; }
    uint64_t affinity_size=number(&d);if(d.error||affinity_size==0||affinity_size>MAX_AFFINITY||affinity_size>d.size-d.at)d.error=EPROTO;
    if(!d.error){r->affinity_size=(size_t)affinity_size;r->affinity=malloc(r->affinity_size);r->affinity_observed=calloc(1,r->affinity_size);if(!r->affinity||!r->affinity_observed)d.error=ENOMEM;else{memcpy(r->affinity,d.data+d.at,r->affinity_size);d.at+=r->affinity_size;bool any=false;for(size_t i=0;i<r->affinity_size;i++)if(r->affinity[i])any=true;if(!any)d.error=EPROTO;}}
    uint64_t group_count=number(&d);if(group_count>65536||group_count>(d.size-d.at)/8)d.error=EPROTO;
    if(!d.error){r->group_count=(size_t)group_count;r->groups=malloc((r->group_count?r->group_count:1)*sizeof *r->groups);if(!r->groups)d.error=ENOMEM;else for(size_t i=0;i<r->group_count;i++){uint64_t gid=number(&d);if(gid>UINT32_MAX||(i&&gid<=r->groups[i-1]))d.error=EPROTO;r->groups[i]=(gid_t)gid;}}
    r->nonce = string(&d); r->unit = string(&d); r->state = string(&d); r->socket = string(&d); r->cwd = string(&d); r->executable = string(&d); r->argv = vector(&d, false); r->environment = vector(&d, true);
    int error = d.error; if (d.at != d.size) error = EPROTO; free(d.data); if (error) { errno = error; return -1; }
    if (!r->nonce || strlen(r->nonce) != 32) return protocol_error(); for (const char *p = r->nonce; *p; p++) if (!isxdigit((unsigned char)*p)) return protocol_error();
    char expected[80]; snprintf(expected, sizeof expected, "minyar-test-mem-%s.service", r->nonce);
    long page = sysconf(_SC_PAGESIZE);
    if (strcmp(expected, r->unit) || !safe_path(r->state) || !safe_path(r->socket) || !r->cwd[0] || r->cwd[0] != '/' || !r->executable[0] || r->executable[0] != '/' || !r->argv || !r->argv[0] || !r->argv[0][0] || r->memory == 0 || r->memory > INT64_MAX || page <= 0 || r->memory % (uint64_t)page || r->wall == 0 || r->wall > UINT64_C(604800000) || r->setup != 10000 || r->grace != 2000 || r->cleanup != 5000 || r->client == 0 || r->client > INT_MAX || r->nice_value < -20 || r->nice_value > 19 || r->mask > 0777 || r->uid != getuid() || r->uid != geteuid() || !r->uid || r->gid != getgid() || r->gid != getegid()) return protocol_error();
    size_t parent = strlen(r->state); if (strncmp(name, r->state, parent) || strcmp(name + parent, "/request.bin")) return protocol_error(); return 0;
}
static int state_open(const struct Request *r) { int fd = open(r->state, O_RDONLY|O_DIRECTORY|O_CLOEXEC|O_NOFOLLOW); if (fd < 0) return -1; struct stat st; if (fstat(fd, &st) || st.st_uid != getuid() || (st.st_mode&0777) != 0700) { close(fd); return protocol_error(); } return fd; }
struct Atomic { FILE *file; int dir; char temporary[96]; const char *name; };
static int atomic_open(struct Atomic *a, int dir, const char *name) {
    a->dir = dir; a->name = name; snprintf(a->temporary, sizeof a->temporary, ".%s.%ld.tmp", name, (long)getpid());
    int fd = openat(dir, a->temporary, O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW, 0600); if (fd < 0) return -1;
    if(fchmod(fd,0600)){int saved=errno;close(fd);unlinkat(dir,a->temporary,0);errno=saved;return -1;}
    a->file = fdopen(fd, "w"); if (!a->file) { int saved = errno; close(fd); unlinkat(dir, a->temporary, 0); errno = saved; return -1; } return 0;
}
static int atomic_finish(struct Atomic *a) {
    int result = 0, saved = 0; if (fflush(a->file) || ferror(a->file) || fsync(fileno(a->file))) { result = -1; saved = errno ? errno : EIO; }
    if (fclose(a->file) && !result) { result = -1; saved = errno; }
    if (!result && renameat(a->dir, a->temporary, a->dir, a->name)) { result = -1; saved = errno; }
    if (result) unlinkat(a->dir, a->temporary, 0); errno = saved; return result;
}
static int atomic_text(int dir, const char *name, const char *value) { struct Atomic a; if (atomic_open(&a, dir, name)) return -1; fputs(value, a.file); return atomic_finish(&a); }
static int membership(char *s, size_t cap) { char text[2048]; if (read_at(AT_FDCWD, "/proc/self/cgroup", text, sizeof text)) return -1; size_t n = strlen(text); if (n && text[n-1] == '\n') text[--n] = 0; if (strncmp(text, "0::/", 4) || strchr(text, '\n') || strlen(text+3) >= cap) return protocol_error(); strcpy(s, text+3); return 0; }
static int open_group(const char *name) {
    char copy[1024]; if(!name||name[0]!='/'||strlen(name)>=sizeof copy)return protocol_error();
    for(const char *p=name;*p;p++)if(!((*p>='A'&&*p<='Z')||(*p>='a'&&*p<='z')||(*p>='0'&&*p<='9')||strchr("/._-@",*p)))return protocol_error();
    strcpy(copy, name+1);
    int fd = open("/sys/fs/cgroup", O_RDONLY|O_DIRECTORY|O_CLOEXEC|O_NOFOLLOW); if (fd < 0) return -1;
    char *save = NULL; for (char *part = strtok_r(copy, "/", &save); part; part = strtok_r(NULL, "/", &save)) { if (!strcmp(part,".") || !strcmp(part,"..")) { close(fd); return protocol_error(); } int next = openat(fd, part, O_RDONLY|O_DIRECTORY|O_CLOEXEC|O_NOFOLLOW); int saved = errno; close(fd); errno = saved; if (next < 0) return -1; fd = next; } return fd;
}
static int own_unit(const struct Request *r, char *root, size_t cap, bool main_process) {
    char self[1024], anchor[128], suffix[128]; if (membership(self, sizeof self)) return -1;
    snprintf(anchor, sizeof anchor, "/user.slice/user-%lu.slice/user@%lu.service/", (unsigned long)getuid(), (unsigned long)getuid());
    snprintf(suffix, sizeof suffix, "/%s/", r->unit); if (strncmp(self, anchor, strlen(anchor))) return protocol_error(); char *end = strstr(self, suffix); if (!end) return protocol_error();
    char *leaf = end + strlen(suffix); if (strcmp(leaf, "control") && (main_process || strcmp(leaf, ".control"))) return protocol_error();
    size_t n = (size_t)(leaf - self - 1); if (n >= cap) return protocol_error(); memcpy(root, self, n); root[n] = 0;
    int fd = open_group(root); if (fd < 0) return -1; struct stat st; struct statfs sf;
    if (fstat(fd, &st) || fstatfs(fd, &sf) || st.st_uid != getuid() || sf.f_type != CGROUP2_SUPER_MAGIC) { close(fd); return protocol_error(); } return fd;
}
static int population(int fd, char *events, size_t cap) { if (read_fd(fd, events, cap)) return -1; if (token(events,"populated 0")) return 0; if (token(events,"populated 1")) return 1; return protocol_error(); }
static int empty_group(int fd, long long deadline) { char events[TEXT_CAP]; for (;;) { int n = population(fd, events, sizeof events); if (n <= 0) return n; if (wait_fd(fd, POLLPRI|POLLERR, deadline)) return -1; } }
static int remove_empty_tree(int parent, const char *name, unsigned depth) {
    if (depth > 32) { errno = EOVERFLOW; return -1; }
    int fd = openat(parent, name, O_RDONLY|O_DIRECTORY|O_CLOEXEC|O_NOFOLLOW); if (fd < 0) return errno == ENOENT ? 0 : -1;
    DIR *dir = fdopendir(dup(fd)); if (!dir) { close(fd); return -1; } struct dirent *entry; int result = 0;
    while ((entry = readdir(dir))) { if (!strcmp(entry->d_name,".") || !strcmp(entry->d_name,"..")) continue; struct stat st; if (fstatat(fd, entry->d_name, &st, AT_SYMLINK_NOFOLLOW)) { result = -1; break; } if (S_ISDIR(st.st_mode) && remove_empty_tree(fd, entry->d_name, depth+1)) { result = -1; break; } }
    int saved = errno; closedir(dir); close(fd); errno = saved; if (result) return -1; return unlinkat(parent, name, AT_REMOVEDIR);
}
static int connect_client(const struct Request *r, int *pidfd, int streams[3], long long deadline) {
    int fd = socket(AF_UNIX, SOCK_STREAM|SOCK_CLOEXEC|SOCK_NONBLOCK, 0); if (fd < 0) return -1;
    struct sockaddr_un address = {.sun_family=AF_UNIX}; if (strlen(r->socket) >= sizeof address.sun_path) { close(fd); return protocol_error(); } strcpy(address.sun_path, r->socket);
    if (connect(fd, (struct sockaddr *)&address, sizeof address) && errno != EINPROGRESS) goto failed;
    if (wait_fd(fd, POLLOUT, deadline)) goto failed; int error = 0; socklen_t size = sizeof error; if (getsockopt(fd, SOL_SOCKET, SO_ERROR, &error, &size) || error) { if (error) errno = error; goto failed; }
    struct ucred peer; size = sizeof peer; if (getsockopt(fd, SOL_SOCKET, SO_PEERCRED, &peer, &size) || size != sizeof peer || peer.uid != r->uid || peer.pid != (pid_t)r->client) { errno = EPROTO; goto failed; }
    unsigned long long ticks; if (start_ticks(peer.pid, &ticks) || ticks != r->ticks) { errno = EPROTO; goto failed; }
    *pidfd = (int)syscall(SYS_pidfd_open, peer.pid, 0); if (*pidfd < 0) goto failed;
    if (start_ticks(peer.pid, &ticks) || ticks != r->ticks) { errno = EPROTO; goto failed; }
    struct pollfd alive = {.fd=*pidfd,.events=POLLIN}; if (poll(&alive,1,0) != 0) { errno = ESRCH; goto failed; }
    unsigned char hello[56] = {0}; memcpy(hello,"MYHEL001",8); uint64_t pid = (uint64_t)getpid(); if (start_ticks(getpid(), &ticks)) goto failed;
    for (unsigned i=0;i<8;i++) { hello[8+i]=(unsigned char)(pid>>(8*i)); hello[16+i]=(unsigned char)(ticks>>(8*i)); } memcpy(hello+24,r->nonce,32);
    if (socket_write(fd,hello,sizeof hello,deadline)) goto failed;
    unsigned char data[40]; union { struct cmsghdr align; unsigned char bytes[CMSG_SPACE(3*sizeof(int))]; } control;
    struct iovec iov = {.iov_base=data,.iov_len=sizeof data}; struct msghdr msg = {.msg_iov=&iov,.msg_iovlen=1,.msg_control=control.bytes,.msg_controllen=sizeof control.bytes}; ssize_t n;
    for (;;) { n=recvmsg(fd,&msg,MSG_CMSG_CLOEXEC); if (n<0 && errno==EINTR) continue; if (n<0 && (errno==EAGAIN || errno==EWOULDBLOCK)) { if (wait_fd(fd,POLLIN,deadline)) goto failed; continue; } break; }
    if (n<=0) { errno=EPROTO; goto failed; } int count=0;
    for (struct cmsghdr *c=CMSG_FIRSTHDR(&msg);c;c=CMSG_NXTHDR(&msg,c)) {
        if (c->cmsg_level!=SOL_SOCKET || c->cmsg_type!=SCM_RIGHTS || c->cmsg_len<CMSG_LEN(0)) { errno=EPROTO; goto failed; }
        size_t bytes=c->cmsg_len-CMSG_LEN(0); if (bytes%sizeof(int)) { errno=EPROTO; goto failed; }
        size_t nf=bytes/sizeof(int); int *fds=(int *)CMSG_DATA(c); for(size_t i=0;i<nf;i++) { if(count<3) streams[count++]=fds[i]; else { close(fds[i]); errno=EPROTO; goto failed; } }
    }
    if ((msg.msg_flags&(MSG_CTRUNC|MSG_TRUNC)) || count!=3) { errno=EPROTO; goto failed; }
    size_t at=(size_t)n; while(at<sizeof data) { ssize_t z=recv(fd,data+at,sizeof data-at,0); if(z<0&&errno==EINTR)continue; if(z<0&&(errno==EAGAIN||errno==EWOULDBLOCK)){if(wait_fd(fd,POLLIN,deadline))goto failed;continue;} if(z<=0){errno=EPROTO;goto failed;}at+=(size_t)z; }
    if(memcmp(data,"MYFDS001",8)||memcmp(data+8,r->nonce,32)){errno=EPROTO;goto failed;}
    if(socket_write(fd,"R",1,deadline))goto failed; return fd;
failed: { int saved=errno; close(fd); errno=saved; return -1; }
}
struct ChildMsg { uint32_t tag, phase; int32_t error, nice_value; uint32_t mask, reserved; uint64_t soft[16], hard[16]; };
_Static_assert(sizeof(struct ChildMsg)<PIPE_BUF,"child report must be atomic");
static int *open_fds(size_t *count) {
    DIR *dir=opendir("/proc/self/fd"); if(!dir)return NULL; int *fds=NULL; size_t cap=0; *count=0; struct dirent *entry;
    while((entry=readdir(dir))) { char *end; long n=strtol(entry->d_name,&end,10); if(!*entry->d_name||*end||n<3||n>INT_MAX)continue; if(*count==cap){size_t next=cap?cap*2:32; int *p=realloc(fds,next*sizeof *p);if(!p){free(fds);closedir(dir);return NULL;}fds=p;cap=next;}fds[(*count)++]=(int)n; }
    closedir(dir); return fds;
}
static void child_exec(const struct Request *r, int report, const int streams[3], const int *fds, size_t count, const char *expected, pid_t owner) {
    struct ChildMsg m={.tag=CHILD_TAG,.phase=1}; char actual[1200];
#define CHILD_REQUIRE(expr, step) do { m.phase=(step); if((expr)<0){m.error=errno?errno:EIO;goto failed;} } while(0)
    CHILD_REQUIRE(prctl(PR_SET_PDEATHSIG,SIGKILL),1); if(getppid()!=owner){errno=ECHILD;CHILD_REQUIRE(-1,1);}
    CHILD_REQUIRE(membership(actual,sizeof actual),1); if(strcmp(actual,expected)){errno=EPROTO;CHILD_REQUIRE(-1,1);}
    CHILD_REQUIRE(setsid(),2); for(int i=0;i<3;i++)CHILD_REQUIRE(dup2(streams[i],i),3);
    for(size_t i=0;i<count;i++)if(fds[i]!=report)close(fds[i]);
    struct sigaction sa={.sa_handler=SIG_DFL}; sigemptyset(&sa.sa_mask); for(int sig=1;sig<NSIG;sig++)if(sig!=SIGKILL&&sig!=SIGSTOP){if(sigaction(sig,&sa,NULL)&&errno!=EINVAL){m.phase=4;m.error=errno;goto failed;}}
    sigset_t empty;sigemptyset(&empty);CHILD_REQUIRE(sigprocmask(SIG_SETMASK,&empty,NULL),4);
    CHILD_REQUIRE(chdir(r->cwd),5);umask(r->mask);
    if(getuid()!=r->uid||geteuid()!=r->uid||getgid()!=r->gid||getegid()!=r->gid){errno=EPROTO;CHILD_REQUIRE(-1,6);}CHILD_REQUIRE(groups_match(r->groups,r->group_count),6);m.reserved|=2;
    CHILD_REQUIRE(sched_setaffinity(0,r->affinity_size,(cpu_set_t *)r->affinity),6);CHILD_REQUIRE(sched_getaffinity(0,r->affinity_size,(cpu_set_t *)r->affinity_observed),6);if(memcmp(r->affinity,r->affinity_observed,r->affinity_size)){errno=EPROTO;CHILD_REQUIRE(-1,6);}m.reserved|=1;
    for(int i=0;i<16;i++)if(i!=RLIMIT_AS)CHILD_REQUIRE(setrlimit(i,&r->limits[i]),6);
    CHILD_REQUIRE(setpriority(PRIO_PROCESS,0,r->nice_value),7);
    struct rlimit as={.rlim_cur=r->limits[RLIMIT_AS].rlim_max,.rlim_max=r->limits[RLIMIT_AS].rlim_max};CHILD_REQUIRE(setrlimit(RLIMIT_AS,&as),8);
    for(int i=0;i<16;i++){struct rlimit got;CHILD_REQUIRE(getrlimit(i,&got),9);struct rlimit wanted=i==RLIMIT_AS?as:r->limits[i];if(got.rlim_cur!=wanted.rlim_cur||got.rlim_max!=wanted.rlim_max){errno=EPROTO;CHILD_REQUIRE(-1,9);}m.soft[i]=got.rlim_cur;m.hard[i]=got.rlim_max;}
    errno=0;m.nice_value=getpriority(PRIO_PROCESS,0);if(errno||m.nice_value!=r->nice_value){if(!errno)errno=EPROTO;CHILD_REQUIRE(-1,9);}mode_t mask=umask(r->mask);if(mask!=r->mask){errno=EPROTO;CHILD_REQUIRE(-1,9);}m.mask=mask;m.phase=100;
    if(write_all(report,&m,sizeof m))_exit(125);execve(r->executable,r->argv,r->environment);m.phase=10;m.error=errno;
failed: (void)write_all(report,&m,sizeof m);_exit(125);
#undef CHILD_REQUIRE
}
struct Run {
    struct Request *r;int state,unit,job,killfd,eventfd,clientfd,socket,leaderfd,errorfd,wake[2],streams[3];pid_t leader;
    bool made,changed,restored,reaped,drained,populated_zero,removed,kill_attempted,term_sent,wall_expired,client_dead,disconnected,cancelled,grace_expired,pipe_closed,limits_ok,controls_ok,oom,pressure,complete;
    int failure,cleanup_error,kill_error,preexec_error,preexec_phase,status,signal_number;unsigned adopted;const char *stage;
    long long started,deadline,stop_deadline;struct rusage usage;struct ChildMsg observed;size_t packet_at;unsigned char packet[sizeof(struct ChildMsg)];
    char root[1024],expected[1200],before[TEXT_CAP],after[TEXT_CAP],local_before[TEXT_CAP],local_after[TEXT_CAP],peak[128],cpu_before[TEXT_CAP],cpu_after[TEXT_CAP];
};
static int reap(struct Run *s) {
    for(;;){int status;struct rusage usage;pid_t p=wait4(-1,&status,WNOHANG,&usage);if(p==0)return 0;if(p<0){if(errno==EINTR)continue;if(errno==ECHILD){s->drained=true;return 0;}return -1;}if(p==s->leader){s->reaped=true;s->status=status;s->usage=usage;}else s->adopted++;}
}
static int drain_children(struct Run *s,long long deadline){
    for(;;){if(s->wake[0]>=0){unsigned char b[128];while(read(s->wake[0],b,sizeof b)>0){}}
        if(reap(s))return -1;if(s->drained)return 0;
        if(s->wake[0]<0){errno=ECHILD;return -1;}if(wait_fd(s->wake[0],POLLIN,deadline))return -1;
    }
}
static void kill_job(struct Run *s) {
    s->kill_attempted=true;if(s->killfd>=0&&write_all(s->killfd,"1",1)){if(!s->kill_error)s->kill_error=errno;}
    else if(s->killfd<0&&!s->kill_error)s->kill_error=EBADF;
    /* Cleanup only: an unreaped direct child cannot have a reused PID. */
    if(s->kill_error&&s->leader>0&&!s->reaped)if(kill(s->leader,SIGKILL)&&errno!=ESRCH&&!s->cleanup_error)s->cleanup_error=errno;
    s->stop_deadline=now_ms()+(long long)s->r->cleanup;
}
static int child_reports(struct Run *s) {
    for(;;){ssize_t n=read(s->errorfd,s->packet+s->packet_at,sizeof s->packet-s->packet_at);if(n<0&&errno==EINTR)continue;if(n<0&&(errno==EAGAIN||errno==EWOULDBLOCK))return 0;if(n<0)return -1;if(!n){s->pipe_closed=true;if(s->packet_at)return protocol_error();return 0;}s->packet_at+=(size_t)n;if(s->packet_at==sizeof s->packet){struct ChildMsg m;memcpy(&m,s->packet,sizeof m);s->packet_at=0;if(m.tag!=CHILD_TAG)return protocol_error();if(m.phase==100&&!m.error){s->limits_ok=true;s->observed=m;}else{if(!m.error)return protocol_error();s->preexec_error=m.error;s->preexec_phase=(int)m.phase;}}}
}
static void optional_read(int dir,const char *name,char *text,size_t cap){if(read_at(dir,name,text,cap))text[0]=0;}
static void finish_job(struct Run *s) {
    if(s->made&&!s->kill_attempted)kill_job(s);
    long long end=s->kill_attempted?s->stop_deadline:now_ms()+(long long)s->r->cleanup;
    if(s->eventfd>=0){if(empty_group(s->eventfd,end)){if(!s->cleanup_error)s->cleanup_error=errno;}else s->populated_zero=true;}
    if(s->leader>0&&!s->reaped&&s->leaderfd>=0){if(wait_fd(s->leaderfd,POLLIN,end)){if(!s->cleanup_error)s->cleanup_error=errno;}else if(reap(s)&&!s->cleanup_error)s->cleanup_error=errno;}
    if(drain_children(s,end)&&!s->cleanup_error)s->cleanup_error=errno;
    if(s->errorfd>=0&&!s->pipe_closed)if(child_reports(s)&&!s->cleanup_error)s->cleanup_error=errno;
    if(s->job>=0){if(read_at(s->job,"memory.events",s->after,sizeof s->after)&&!s->cleanup_error)s->cleanup_error=errno;optional_read(s->job,"memory.events.local",s->local_after,sizeof s->local_after);optional_read(s->job,"memory.peak",s->peak,sizeof s->peak);optional_read(s->job,"cpu.stat",s->cpu_after,sizeof s->cpu_after);}
    if(s->made&&s->populated_zero){if(remove_empty_tree(s->unit,"job",0)){if(!s->cleanup_error)s->cleanup_error=errno;}else s->removed=true;}
    if(s->changed&&(!s->made||s->removed)){char text[256];int status=read_at(s->unit,"cgroup.subtree_control",text,sizeof text);if(!status&&token(text,"memory"))status=write_at(s->unit,"cgroup.subtree_control","-memory");if(status||read_at(s->unit,"cgroup.subtree_control",text,sizeof text)||token(text,"memory")){if(!s->cleanup_error)s->cleanup_error=errno?errno:EPROTO;}else s->restored=true;}
    if(s->before[0]&&s->after[0]){const char *keys[]={"max","oom","oom_kill","oom_group_kill"};for(unsigned i=0;i<4;i++){unsigned long long a,b;int x=counter(s->before,keys[i],&a),y=counter(s->after,keys[i],&b);if(x||y){if(i!=3&&!s->cleanup_error)s->cleanup_error=EPROTO;continue;}if(b<a){if(!s->cleanup_error)s->cleanup_error=EPROTO;continue;}if(b>a){if(!i)s->pressure=true;else s->oom=true;}}}
    s->complete=!s->failure&&!s->cleanup_error&&!s->kill_error&&s->leader>0&&s->reaped&&s->drained&&s->populated_zero&&s->removed&&(!s->changed||s->restored)&&s->limits_ok&&s->pipe_closed&&s->controls_ok;
}
static void json_bool(FILE *f,bool b){fputs(b?"true":"false",f);}
static int guardian_result(struct Run *s) {
    struct Atomic a;if(atomic_open(&a,s->state,"guardian.json"))return -1;FILE *f=a.file;
    fputs("{\"schema\":1,\"profile\":\"aggregate-v1\",\"nonce\":",f);json_string(f,s->r->nonce);fputs(",\"unit\":",f);json_string(f,s->r->unit);fprintf(f,",\"guardian_pid\":%ld,\"client_pid\":%llu,\"memory_bytes\":\"%llu\",\"wall_ms\":\"%llu\",\"unit_cgroup\":",(long)getpid(),(unsigned long long)s->r->client,(unsigned long long)s->r->memory,(unsigned long long)s->r->wall);json_string(f,s->root);
    fputs(",\"stage\":",f);json_string(f,s->stage);fprintf(f,",\"failure_errno\":%d,\"complete\":",s->failure);json_bool(f,s->complete);
    fputs(",\"admission\":{\"method\":\"clone3-into-cgroup-pidfd\",\"controls_verified\":",f);json_bool(f,s->controls_ok);fprintf(f,",\"memory_max\":\"%llu\",\"memory_swap_max\":\"0\",\"memory_oom_group\":\"1\",\"child_membership_verified\":",(unsigned long long)s->r->memory);json_bool(f,s->limits_ok);fputc('}',f);
    fprintf(f,",\"leader\":{\"pid\":%ld,\"known\":",(long)s->leader);json_bool(f,s->reaped);fputs(",\"raw_wait_status\":",f);if(s->reaped)fprintf(f,"%d",s->status);else fputs("null",f);
    fputs(",\"exit_code\":",f);if(s->reaped&&WIFEXITED(s->status))fprintf(f,"%d",WEXITSTATUS(s->status));else fputs("null",f);fputs(",\"signal\":",f);if(s->reaped&&WIFSIGNALED(s->status))fprintf(f,"%d",WTERMSIG(s->status));else fputs("null",f);
    fputs(",\"core_dumped\":",f);json_bool(f,s->reaped&&WIFSIGNALED(s->status)&&WCOREDUMP(s->status));fprintf(f,",\"preexec_errno\":%d,\"preexec_phase\":%d,\"pipe_closed\":",s->preexec_error,s->preexec_phase);json_bool(f,s->pipe_closed);fputs(",\"limits_verified\":",f);json_bool(f,s->limits_ok);
    fputs(",\"affinity_verified\":",f);json_bool(f,s->limits_ok&&(s->observed.reserved&1));fputs(",\"affinity\":",f);json_affinity(f,s->r->affinity,s->r->affinity_size);fputs(",\"groups_verified\":",f);json_bool(f,s->limits_ok&&(s->observed.reserved&2));fputs(",\"supplementary_groups\":",f);json_groups(f,s->r->groups,s->r->group_count);
    fprintf(f,",\"nice\":%d,\"umask\":%u,\"maxrss_kib\":%ld,\"user_us\":\"%lld\",\"system_us\":\"%lld\",\"limits\":[",s->observed.nice_value,s->observed.mask,s->usage.ru_maxrss,(long long)s->usage.ru_utime.tv_sec*1000000+s->usage.ru_utime.tv_usec,(long long)s->usage.ru_stime.tv_sec*1000000+s->usage.ru_stime.tv_usec);
    if(s->limits_ok)for(int i=0;i<16;i++){if(i)fputc(',',f);fprintf(f,"{\"id\":%d,\"soft\":",i);json_limit(f,(rlim_t)s->observed.soft[i]);fputs(",\"hard\":",f);json_limit(f,(rlim_t)s->observed.hard[i]);fputc('}',f);}fputs("]},\"causes\":{\"target_wall\":",f);json_bool(f,s->wall_expired);fputs(",\"client_dead\":",f);json_bool(f,s->client_dead);fputs(",\"socket_eof\":",f);json_bool(f,s->disconnected);fputs(",\"cancel_request\":",f);json_bool(f,s->cancelled);fprintf(f,",\"supervisor_signal\":%d,\"grace_expired\":",s->signal_number);json_bool(f,s->grace_expired);fputs(",\"term_sent\":",f);json_bool(f,s->term_sent);fputs(",\"oom_observed\":",f);json_bool(f,s->oom);fputs(",\"max_pressure\":",f);json_bool(f,s->pressure);
    fputs("},\"memory\":{\"events_before\":",f);json_string(f,s->before);fputs(",\"events_after\":",f);json_string(f,s->after);fputs(",\"local_before\":",f);json_string(f,s->local_before[0]?s->local_before:NULL);fputs(",\"local_after\":",f);json_string(f,s->local_after[0]?s->local_after:NULL);fputs(",\"peak_charged_bytes\":",f);json_string(f,s->peak[0]?s->peak:NULL);fputs(",\"cpu_before\":",f);json_string(f,s->cpu_before[0]?s->cpu_before:NULL);fputs(",\"cpu_after\":",f);json_string(f,s->cpu_after[0]?s->cpu_after:NULL);
    fprintf(f,"},\"cleanup\":{\"errno\":%d,\"kill_errno\":%d,\"adopted_reaped\":%u,\"kill_attempted\":",s->cleanup_error,s->kill_error,s->adopted);json_bool(f,s->kill_attempted);fputs(",\"owned_children_drained\":",f);json_bool(f,s->drained);fputs(",\"populated_zero\":",f);json_bool(f,s->populated_zero);fputs(",\"job_removed\":",f);json_bool(f,s->removed);fputs(",\"controller_changed\":",f);json_bool(f,s->changed);fputs(",\"controller_restored\":",f);json_bool(f,s->restored);fputs("}}\n",f);return atomic_finish(&a);
}
static void control_socket_remove(const struct Request *r){if(unlink(r->socket)&&errno!=ENOENT)return;char path[1024];strcpy(path,r->socket);char *slash=strrchr(path,'/');if(slash){*slash=0;(void)rmdir(path);}}
static int unit_main(struct Request *r) {
    struct Run s={.r=r,.state=-1,.unit=-1,.job=-1,.killfd=-1,.eventfd=-1,.clientfd=-1,.socket=-1,.leaderfd=-1,.errorfd=-1,.wake={-1,-1},.streams={-1,-1,-1},.leader=-1,.stage="setup"};int child_pipe[2]={-1,-1};int *fds=NULL;size_t fd_count=0;char text[TEXT_CAP],memory[64];long long setup_end=now_ms()+(long long)r->setup;
#define NEED(expr,label) do{s.stage=(label);if((expr)<0){s.failure=errno?errno:EIO;goto finish;}}while(0)
#define CHECK(expr,label) NEED((expr)?0:protocol_error(),label)
    NEED(s.state=state_open(r),"state");NEED(pipe2(s.wake,O_CLOEXEC|O_NONBLOCK),"wakeup");wake_write=s.wake[1];
    struct sigaction action={.sa_handler=interrupted};sigemptyset(&action.sa_mask);for(int i=0;i<4;i++){int sigs[]={SIGTERM,SIGINT,SIGHUP,SIGCHLD};NEED(sigaction(sigs[i],&action,NULL),"signals");}action.sa_handler=SIG_IGN;NEED(sigaction(SIGPIPE,&action,NULL),"sigpipe");NEED(prctl(PR_SET_CHILD_SUBREAPER,1),"subreaper");
    NEED(s.unit=own_unit(r,s.root,sizeof s.root,true),"unit_membership");NEED(read_at(s.unit,"cgroup.type",text,sizeof text),"unit_type");CHECK(token(text,"domain"),"unit_domain");NEED(read_at(s.unit,"cgroup.procs",text,sizeof text),"unit_empty");CHECK(!text[0],"unit_empty");
    NEED(s.socket=connect_client(r,&s.clientfd,s.streams,setup_end),"client_handshake");s.signal_number=caught_signal;CHECK(!s.signal_number,"cancel_before_admission");
    NEED(groups_match(r->groups,r->group_count),"manager_supplementary_groups");
    NEED(read_at(s.unit,"cgroup.controllers",text,sizeof text),"controllers");CHECK(token(text,"memory"),"memory_available");NEED(read_at(s.unit,"cgroup.subtree_control",text,sizeof text),"controller_state");bool original=token(text,"memory");NEED(atomic_text(s.state,"controller-before",original?"1\n":"0\n"),"controller_journal");
    if(!original){s.changed=true;NEED(write_at(s.unit,"cgroup.subtree_control","+memory"),"enable_memory");}NEED(read_at(s.unit,"cgroup.subtree_control",text,sizeof text),"memory_enabled");CHECK(token(text,"memory"),"memory_enabled");
    NEED(mkdirat(s.unit,"job",0700),"job_create");s.made=true;NEED(fchmodat(s.unit,"job",0700,0),"job_permissions");NEED(s.job=openat(s.unit,"job",O_RDONLY|O_DIRECTORY|O_CLOEXEC|O_NOFOLLOW),"job_open");
    snprintf(memory,sizeof memory,"%llu",(unsigned long long)r->memory);NEED(write_at(s.job,"memory.max",memory),"memory_max");NEED(write_at(s.job,"memory.swap.max","0"),"swap_max");NEED(write_at(s.job,"memory.oom.group","1"),"oom_group");
    NEED(read_at(s.job,"memory.max",text,sizeof text),"memory_readback");text[strcspn(text,"\n")]=0;CHECK(!strcmp(text,memory),"memory_readback");NEED(read_at(s.job,"memory.swap.max",text,sizeof text),"swap_readback");CHECK(token(text,"0"),"swap_readback");NEED(read_at(s.job,"memory.oom.group",text,sizeof text),"oom_readback");CHECK(token(text,"1"),"oom_readback");s.controls_ok=true;
    NEED(s.killfd=openat(s.job,"cgroup.kill",O_WRONLY|O_CLOEXEC|O_NOFOLLOW),"kill_interface");NEED(s.eventfd=openat(s.job,"cgroup.events",O_RDONLY|O_CLOEXEC|O_NOFOLLOW),"events_interface");NEED(empty_group(s.eventfd,setup_end),"empty_job");NEED(read_at(s.job,"memory.events",s.before,sizeof s.before),"memory_before");optional_read(s.job,"memory.events.local",s.local_before,sizeof s.local_before);optional_read(s.job,"cpu.stat",s.cpu_before,sizeof s.cpu_before);
    NEED(pipe2(child_pipe,O_CLOEXEC),"child_report_pipe");NEED(fcntl(child_pipe[0],F_SETFL,O_NONBLOCK),"child_report_nonblocking");fds=open_fds(&fd_count);CHECK(fds!=NULL,"child_fd_inventory");snprintf(s.expected,sizeof s.expected,"%s/job",s.root);
    s.started=now_ms();s.deadline=s.started+(long long)r->wall;struct clone_args args={.flags=CLONE_INTO_CGROUP|CLONE_PIDFD,.pidfd=(uint64_t)(uintptr_t)&s.leaderfd,.exit_signal=SIGCHLD,.cgroup=(uint64_t)s.job};pid_t owner=getpid();
    s.signal_number=caught_signal;CHECK(s.started>=0&&s.started<setup_end&&!s.signal_number,"setup_deadline");struct pollfd alive={.fd=s.clientfd,.events=POLLIN};int alive_n=poll(&alive,1,0);NEED(alive_n,"client_lifetime_poll");if(alive_n)s.client_dead=true;CHECK(!s.client_dead,"client_still_alive");
    unsigned char pending;ssize_t pending_n=recv(s.socket,&pending,1,MSG_PEEK|MSG_DONTWAIT);if(!pending_n)s.disconnected=true;if(pending_n>0&&pending=='C')s.cancelled=true;CHECK(pending_n<0&&(errno==EAGAIN||errno==EWOULDBLOCK),"socket_alive_before_admission");
    NEED(s.leader=(pid_t)syscall(SYS_clone3,&args,sizeof args),"clone3_admission");if(!s.leader)child_exec(r,child_pipe[1],s.streams,fds,fd_count,s.expected,owner);CHECK(s.leaderfd>=0,"leader_pidfd");close(child_pipe[1]);child_pipe[1]=-1;s.errorfd=child_pipe[0];child_pipe[0]=-1;
    for(int i=0;i<3;i++){close(s.streams[i]);s.streams[i]=-1;}free(fds);fds=NULL;s.stage="running";
    for(;;){
        long long now=now_ms();if(now<0){s.failure=errno;break;}if(reap(&s)){s.failure=errno;break;}
        if(!s.pipe_closed&&child_reports(&s)){s.failure=errno;break;}
        if(caught_signal){s.signal_number=caught_signal;caught_signal=0;}
        if(!s.reaped&&!s.wall_expired&&now>=s.deadline)s.wall_expired=true;
        if(s.preexec_error||s.reaped||s.client_dead){if(!s.kill_attempted)kill_job(&s);}
        else if((s.wall_expired||s.cancelled||s.disconnected||s.signal_number)&&!s.term_sent&&!s.kill_attempted){s.term_sent=true;if(kill(-s.leader,SIGTERM)&&errno==ESRCH&&!s.reaped)(void)kill(s.leader,SIGTERM);s.stop_deadline=now+(long long)r->grace;}
        if(s.term_sent&&!s.kill_attempted&&now>=s.stop_deadline){s.grace_expired=true;kill_job(&s);}
        int populated=population(s.eventfd,text,sizeof text);if(populated<0){s.failure=errno;break;}
        if(s.kill_attempted){if(!populated&&s.reaped){s.populated_zero=true;break;}if(now>=s.stop_deadline){s.cleanup_error=ETIMEDOUT;break;}}
        long long deadline=s.kill_attempted||s.term_sent?s.stop_deadline:s.deadline;long long left=deadline-now;if(left<0)left=0;
        struct pollfd p[6]={{.fd=s.client_dead?-1:s.clientfd,.events=POLLIN},{.fd=s.disconnected?-1:s.socket,.events=POLLIN},{.fd=s.reaped?-1:s.leaderfd,.events=POLLIN},{.fd=s.pipe_closed?-1:s.errorfd,.events=POLLIN},{.fd=s.eventfd,.events=POLLPRI|POLLERR},{.fd=s.wake[0],.events=POLLIN}};
        int n=poll(p,6,left>INT_MAX?INT_MAX:(int)left);if(n<0){if(errno==EINTR)continue;s.failure=errno;break;}
        for(unsigned i=0;i<6;i++)if(p[i].revents&POLLNVAL)s.failure=EBADF;if(s.failure)break;
        if(p[0].revents&(POLLIN|POLLHUP))s.client_dead=true;
        if(p[1].revents&(POLLIN|POLLHUP)){unsigned char commands[64];ssize_t z=recv(s.socket,commands,sizeof commands,0);if(!z)s.disconnected=true;else if(z>0){for(ssize_t i=0;i<z;i++)if(commands[i]=='C')s.cancelled=true;else{s.failure=EPROTO;break;}}else if(errno!=EAGAIN&&errno!=EWOULDBLOCK&&errno!=EINTR){s.disconnected=true;}}
        if(p[5].revents&POLLIN){unsigned char b[64];while(read(s.wake[0],b,sizeof b)>0){}}
        if(s.failure)break;
    }
finish:
    free(fds);if(child_pipe[0]>=0)close(child_pipe[0]);if(child_pipe[1]>=0)close(child_pipe[1]);finish_job(&s);if(!s.failure&&!s.cleanup_error)s.stage="settled";
    int result=125;if(s.state>=0){if(guardian_result(&s))s.complete=false;else if(s.complete)result=0;}
    if(s.socket>=0){(void)send(s.socket,"D",1,MSG_NOSIGNAL);close(s.socket);}control_socket_remove(r);wake_write=-1;
    int descriptors[]={s.state,s.unit,s.job,s.killfd,s.eventfd,s.clientfd,s.leaderfd,s.errorfd,s.wake[0],s.wake[1],s.streams[0],s.streams[1],s.streams[2]};for(size_t i=0;i<sizeof descriptors/sizeof descriptors[0];i++)if(descriptors[i]>=0)close(descriptors[i]);return result;
#undef NEED
#undef CHECK
}
static int unit_result(struct Request *r) {
    int state=state_open(r);if(state<0)return 125;char root[1024]="",original[32]="",events[TEXT_CAP]="";int unit=own_unit(r,root,sizeof root,false),job=-1,eventfd=-1,error=0;bool empty=false,removed=false,restored=false,needed=false;
    if(unit<0)error=errno;
    else{job=openat(unit,"job",O_RDONLY|O_DIRECTORY|O_CLOEXEC|O_NOFOLLOW);if(job<0&&errno==ENOENT){empty=true;removed=true;}else if(job<0)error=errno;else{if(write_at(job,"cgroup.kill","1")&&!error)error=errno;eventfd=openat(job,"cgroup.events",O_RDONLY|O_CLOEXEC|O_NOFOLLOW);if(eventfd<0){if(!error)error=errno;}else if(empty_group(eventfd,now_ms()+(long long)r->cleanup)){if(!error)error=errno;}else empty=true;if(empty){if(remove_empty_tree(unit,"job",0)){if(!error)error=errno;}else removed=true;}}
        if(!read_at(state,"controller-before",original,sizeof original)){needed=original[0]=='0';if(needed&&removed){int status=read_at(unit,"cgroup.subtree_control",events,sizeof events);if(!status&&token(events,"memory"))status=write_at(unit,"cgroup.subtree_control","-memory");if(status||read_at(unit,"cgroup.subtree_control",events,sizeof events)||token(events,"memory")){if(!error)error=errno?errno:EPROTO;}else restored=true;}}
    }
    struct Atomic a;int result=125;if(!atomic_open(&a,state,"manager.json")){FILE *f=a.file;fputs("{\"schema\":1,\"nonce\":",f);json_string(f,r->nonce);fputs(",\"unit\":",f);json_string(f,r->unit);fputs(",\"service_result\":",f);json_string(f,getenv("SERVICE_RESULT"));fputs(",\"exit_code\":",f);json_string(f,getenv("EXIT_CODE"));fputs(",\"exit_status\":",f);json_string(f,getenv("EXIT_STATUS"));fprintf(f,",\"cleanup\":{\"errno\":%d,\"populated_zero\":",error);json_bool(f,empty);fputs(",\"job_removed\":",f);json_bool(f,removed);fputs(",\"controller_restore_needed\":",f);json_bool(f,needed);fputs(",\"controller_restored\":",f);json_bool(f,restored);fputs("}}\n",f);if(!atomic_finish(&a)&&!error)result=0;}
    control_socket_remove(r);if(eventfd>=0)close(eventfd);if(job>=0)close(job);if(unit>=0)close(unit);close(state);return result;
}
int main(int argc,char **argv) {
    if(argc==2&&!strcmp(argv[1],"--capture"))return capture();
    if(argc!=3||(strcmp(argv[1],"--unit-main")&&strcmp(argv[1],"--unit-result")))return 125;
    struct Request request={0};if(request_read(argv[2],&request))return 125;
    return !strcmp(argv[1],"--unit-main")?unit_main(&request):unit_result(&request);
}
