/* Real descriptors/threads and deterministic faults for the imported provider.
 * Every case runs in its own bounded process. No managed values enter a worker. */
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
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#include "files-test-path.h"

static int fd_step, fd_fail, mutex_fail, condition_fail, create_fail;
static int mutex_live, condition_live, condition_step, directory_mode, directory_reads, directory_closes;
static _Atomic int sync_failure;
static int positioned_io, positioned_calls;
static int intercepted_fcntl(int fd, int command, ...) {
    int argument = 0;
    if (command != F_GETFL && command != F_GETFD
#ifdef __APPLE__
        && command != F_FULLFSYNC
#endif
    ) {
        va_list args; va_start(args, command); argument = va_arg(args, int); va_end(args);
    }
    if (fd_fail && ++fd_step == fd_fail) { errno = EACCES; return -1; }
#ifdef __APPLE__
    if (command == F_FULLFSYNC && atomic_load(&sync_failure)) { errno = EIO; return -1; }
#endif
    return fcntl(fd, command, argument);
}
static int intercepted_mutex_init(pthread_mutex_t *m, const pthread_mutexattr_t *a) {
    if (mutex_fail) return EAGAIN;
    int rc = pthread_mutex_init(m, a); if (!rc) mutex_live++; return rc;
}
static int intercepted_mutex_destroy(pthread_mutex_t *m) {
    int rc = pthread_mutex_destroy(m); if (!rc) mutex_live--; return rc;
}
static int intercepted_condition_init(pthread_cond_t *c, const pthread_condattr_t *a) {
    if (condition_fail && ++condition_step == condition_fail) return EAGAIN;
    int rc = pthread_cond_init(c, a); if (!rc) condition_live++; return rc;
}
static int intercepted_condition_destroy(pthread_cond_t *c) {
    int rc = pthread_cond_destroy(c); if (!rc) condition_live--; return rc;
}
static int intercepted_create(pthread_t *t, const pthread_attr_t *a, void *(*f)(void *), void *p) {
    return create_fail ? EAGAIN : pthread_create(t, a, f, p);
}
static struct dirent *intercepted_readdir(DIR *d) {
    if (!directory_mode) return readdir(d);
    static struct dirent entry;
    if (!directory_reads++) { strcpy(entry.d_name, "one"); errno = EBUSY; return &entry; }
    errno = directory_mode == 1 ? EIO : 0;
    return NULL;
}
static int intercepted_closedir(DIR *d) {
    directory_closes++;
    int rc = closedir(d);
    if (directory_mode == 3) { errno = EACCES; return -1; }
    return rc;
}
static int intercepted_datasync(int fd) {
    if (atomic_load(&sync_failure)) { errno = EIO; return -1; }
    return fdatasync(fd);
}
static ssize_t intercepted_pwrite(int fd, const void *data, size_t count, off_t position) {
    if (positioned_io) { positioned_calls++; return count ? 1 : 0; }
    return pwrite(fd, data, count, position);
}
static ssize_t intercepted_pread(int fd, void *data, size_t count, off_t position) {
    if (positioned_io) { positioned_calls++; if(count) { ((char *)data)[0]='x';return 1; } return 0; }
    return pread(fd, data, count, position);
}
#define fcntl intercepted_fcntl
#define pthread_mutex_init intercepted_mutex_init
#define pthread_mutex_destroy intercepted_mutex_destroy
#define pthread_cond_init intercepted_condition_init
#define pthread_cond_destroy intercepted_condition_destroy
#define pthread_create intercepted_create
#define readdir intercepted_readdir
#define closedir intercepted_closedir
#define fdatasync intercepted_datasync
#define pwrite intercepted_pwrite
#define pread intercepted_pread
#define FILES_MAX_SYNCERS 32
#include "../runtime/native/files.c"
#undef pread
#undef pwrite
#undef fdatasync
#undef closedir
#undef readdir
#undef pthread_create
#undef pthread_cond_destroy
#undef pthread_cond_init
#undef pthread_mutex_destroy
#undef pthread_mutex_init
#undef fcntl
void minyar_rc_release(void *);

static MinyarText text(const char *s) {
    MinyarText t = {(const unsigned char *)s, (long long)strlen(s), 0, NULL, NULL}; return t;
}
static int descriptors(void) {
    int count = 0; for (int fd = 0; fd < 256; fd++) if (fcntl(fd, F_GETFD) >= 0) count++; return count;
}
static int temporary(void) {
    char path[PATH_MAX]; files_test_path(path,sizeof(path),"minyar-review-file-XXXXXX");
    int fd = mkstemp(path); assert(fd >= 0); assert(!unlink(path)); assert(write(fd, "x", 1) == 1); return fd;
}
static void valid_retry(int fd) {
    fd_fail = mutex_fail = condition_fail = create_fail = 0;
    long long h = minyar_files_syncerStart(fd); assert(h > 0);
    assert(minyar_files_syncerWait(h, 1, 5000) >= 1);
    assert(minyar_files_syncerStop(h) == 0);
    assert(mutex_live == 0 && condition_live == 0);
}
static void setup(const char *kind, int failure) {
    int fd = temporary(), before = descriptors();
    if (!strcmp(kind, "fd")) fd_fail = failure;
    if (!strcmp(kind, "mutex")) mutex_fail = 1;
    if (!strcmp(kind, "condition")) condition_fail = failure;
    if (!strcmp(kind, "create")) create_fail = 1;
    assert(minyar_files_syncerStart(fd) == (!strcmp(kind, "fd") ? -EACCES : -EAGAIN));
    assert(descriptors() == before && mutex_live == 0 && condition_live == 0);
    for (int i = 0; i < FILES_MAX_SYNCERS; i++) assert(!files_syncers[i]);
    valid_retry(fd); close(fd);
}
static void listing(int mode) {
    char path[PATH_MAX]; files_test_path(path,sizeof(path),"minyar-review-directory-XXXXXX"); assert(mkdtemp(path));
    MinyarText p = text(path); directory_mode = mode;
    MinyarBytes *b = minyar_files_listNames(&p);
    if (mode == 1 || mode == 3) {
        assert(b->byte_length == 0);
        assert(minyar_files_lastError() == (mode == 1 ? -EIO : -EACCES));
    } else if (mode == 2) {
        assert(b->byte_length == 4 && !memcmp(b->bytes, "one\0", 4));
        assert(minyar_files_lastError() == 0);
    } else assert(b->byte_length == 0 && minyar_files_lastError() == 0);
    assert(directory_closes == 1); minyar_rc_release(b); assert(!rmdir(path));
}
static void names(void) {
    const char *entries[] = {"a\nb", "a", "b", "\n", "\nedge", "tail\n", "\xce\xbb"};
    char directory[PATH_MAX]; files_test_path(directory,sizeof(directory),"minyar-review-names-XXXXXX"); assert(mkdtemp(directory));
    char path[PATH_MAX];
    for (size_t i = 0; i < 7; i++) {
        snprintf(path, sizeof(path), "%s/%s", directory, entries[i]);
        int fd = open(path, O_CREAT|O_EXCL|O_WRONLY, 0600); assert(fd >= 0);
        assert(write(fd, entries[i], strlen(entries[i])) == (ssize_t)strlen(entries[i])); close(fd);
    }
    MinyarText d = text(directory); MinyarBytes *raw = minyar_files_listNames(&d);
    size_t at = 0, count = 0;
    while (at < (size_t)raw->byte_length) {
        const unsigned char *end = memchr(raw->bytes + at, 0, (size_t)raw->byte_length - at);
        assert(end); size_t size = (size_t)(end - raw->bytes - at); bool found = false;
        for (size_t i = 0; i < 7; i++) if (strlen(entries[i]) == size && !memcmp(entries[i], raw->bytes+at, size)) found = true;
        assert(found); count++; at += size + 1;
    }
    assert(count == 7); minyar_rc_release(raw);
    for (size_t i = 0; i < 7; i++) { snprintf(path, sizeof(path), "%s/%s", directory, entries[i]); assert(!unlink(path)); }
    assert(!rmdir(directory));
}
static void diagnostic(void) {
    long long invalid[] = {LLONG_MIN, LLONG_MAX, (long long)INT_MAX+1, -(long long)INT_MAX-1};
    for (size_t i = 0; i < 4; i++) {
        MinyarText *t = minyar_files_errorText(invalid[i]);
        assert(t->byte_length == 35 && !memcmp(t->bytes, "invalid operating-system error code", 35)); minyar_rc_release(t);
    }
    long long valid[] = {0, EIO, -EIO, INT_MAX, -(long long)INT_MAX};
    for (size_t i = 0; i < 5; i++) { MinyarText *t = minyar_files_errorText(valid[i]); assert(t->byte_length > 0); minyar_rc_release(t); }
}
static void stale(void) {
    int fd = temporary(); long long a = minyar_files_syncerStart(fd); assert(a > 0);
    assert(!minyar_files_syncerStop(a)); long long b = minyar_files_syncerStart(fd); assert(b > 0 && b != a);
    assert(minyar_files_syncerNotifySocket(a) == -EBADF);
    assert(minyar_files_syncerRequest(a, 1) == -EBADF);
    assert(minyar_files_syncerSynced(a) == -EBADF && minyar_files_syncerError(a) == -EBADF);
    assert(minyar_files_syncerDrain(a) == -EBADF && minyar_files_syncerWait(a, 1, 0) == -EBADF);
    assert(minyar_files_syncerSwitch(a, fd, 0) == -EBADF && minyar_files_syncerStop(a) == -EBADF);
    assert(minyar_files_syncerWait(b, 1, 5000) >= 1);
    /* An old readiness token cannot drain or stop the replacement job. */
    assert(minyar_files_syncerDrain(a) == -EBADF); assert(minyar_files_syncerDrain(b) > 0);
    assert(!minyar_files_syncerStop(b)); close(fd);
}
static void capacity(void) {
    int fd = temporary(), before = descriptors(); long long prior[FILES_MAX_SYNCERS] = {0};
    for (int round = 0; round < 2; round++) {
        long long jobs[FILES_MAX_SYNCERS];
        for (int i = 0; i < FILES_MAX_SYNCERS; i++) { jobs[i] = minyar_files_syncerStart(fd); assert(jobs[i] > 0 && jobs[i] != prior[i]); }
        assert(minyar_files_syncerStart(fd) == -EMFILE);
        for (int i = 0; i < FILES_MAX_SYNCERS; i++) { assert(!minyar_files_syncerStop(jobs[i])); prior[i] = jobs[i]; }
    }
    assert(descriptors() == before); close(fd);
}
static void sticky(bool rotation) {
    int first = temporary(), second = temporary(), third = temporary(), before = descriptors();
    long long h = minyar_files_syncerStart(first); assert(h > 0);
    if (rotation) assert(minyar_files_syncerWait(h, 1, 5000) == 1);
    atomic_store(&sync_failure, 1);
    if (rotation) {
        assert(!minyar_files_syncerSwitch(h, second, 2)); assert(!minyar_files_syncerSwitch(h, third, 3));
    }
    assert(minyar_files_syncerWait(h, rotation ? 3 : 1, 5000) == -EIO);
    assert(minyar_files_syncerSynced(h) == (rotation ? 1 : 0)); assert(minyar_files_syncerError(h) == -EIO);
    assert(minyar_files_syncerStop(h) == -EIO); assert(descriptors() == before);
    close(first); close(second); close(third);
}
static void borrowed_lifetime(void) {
    int fd = temporary(); long long h = minyar_files_syncerStart(fd); assert(h > 0); close(fd);
    assert(minyar_files_syncerWait(h, 1, 5000) == 1);
    fd = temporary(); assert(!minyar_files_syncerSwitch(h, fd, 1)); close(fd);
    assert(minyar_files_syncerWait(h, 2, 5000) == 2); assert(!minyar_files_syncerStop(h));
}
static void saturated(void) {
    int fd = temporary(); long long h = minyar_files_syncerStart(fd); assert(h > 0);
    FilesSyncer *s = files_syncer(h); char byte = 1;
    while (write(s->notify_write, &byte, 1) == 1) {}
    assert(errno == EAGAIN || errno == EWOULDBLOCK);
    assert(minyar_files_syncerWait(h, 1, 5000) == 1); assert(!minyar_files_syncerStop(h)); close(fd);
}
static void bounds(void) {
    int fd=temporary();MinyarBytes b=text("abc");positioned_io=1;
    assert(minyar_files_writeAt(fd,&b,0,3,LLONG_MAX-1)==-EOVERFLOW);
    assert(positioned_calls==0);
    MinyarBytes *read=minyar_files_readAt(fd,LLONG_MAX-1,3);
    assert(read->byte_length==0 && minyar_files_lastError()==-EOVERFLOW && positioned_calls==0);
    minyar_rc_release(read);
    read=minyar_files_readAt(fd,0,LLONG_MAX);
    assert(read->byte_length==0 && minyar_files_lastError()==-EOVERFLOW);
    minyar_rc_release(read);close(fd);
}
static void append_position(void) {
    int fd=temporary();assert(!fcntl(fd,F_SETFL,fcntl(fd,F_GETFL)|O_APPEND));MinyarBytes b=text("a");
    assert(minyar_files_writeAt(fd,&b,0,1,0)==-EINVAL);
    assert(minyar_files_size(fd)==1);close(fd);
}
static void boundaries(void) {
    int fd=temporary();long long h=minyar_files_syncerStart(fd);assert(h>0);
    assert(minyar_files_syncerRequest(h,-1)==-EINVAL);
    assert(minyar_files_syncerWait(h,-1,0)==-EINVAL);
    assert(minyar_files_syncerWait(h,1,-2)==-EINVAL);
    assert(minyar_files_syncerSwitch(h,fd,-1)==-EINVAL);
    assert(minyar_files_syncerWait(h,2,5000)==2);
    assert(minyar_files_syncerSwitch(h,fd,1)==-EINVAL);
    assert(!minyar_files_syncerStop(h));close(fd);
}
static void child_descriptors(const char *executable) {
    int fd=temporary();long long h=minyar_files_syncerStart(fd);assert(h>0);close(fd);
    FilesSyncer *s=files_syncer(h);char first[24],second[24],third[24];
    snprintf(first,sizeof(first),"%d",s->fd);snprintf(second,sizeof(second),"%d",s->notify_read);
    snprintf(third,sizeof(third),"%d",s->notify_write);
    pid_t child=fork();assert(child>=0);
    if(!child) { char *args[]={(char *)executable,"excluded",first,second,third,NULL};execv(executable,args);_exit(111); }
    int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && WEXITSTATUS(status)==0);
    assert(!minyar_files_syncerStop(h));
}
int main(int argc, char **argv) {
    (void)intercepted_datasync; /* Darwin uses the strong fcntl branch. */
    assert(argc >= 2); const char *mode = argv[1];
    if (!strcmp(mode, "names")) names();
    else if (!strcmp(mode, "listing")) listing(argc > 2 ? atoi(argv[2]) : 0);
    else if (!strcmp(mode, "diagnostic")) diagnostic();
    else if (!strcmp(mode, "closed-fd")) { close(0); int before=descriptors(); assert(minyar_files_syncerStart(0)==-EBADF); assert(descriptors()==before); }
    else if (!strcmp(mode, "stale")) stale();
    else if (!strcmp(mode, "capacity")) capacity();
    else if (!strcmp(mode, "setup")) { assert(argc == 4); setup(argv[2], atoi(argv[3])); }
    else if (!strcmp(mode, "sticky")) sticky(argc > 2);
    else if (!strcmp(mode, "borrowed")) borrowed_lifetime();
    else if (!strcmp(mode, "saturated")) saturated();
    else if (!strcmp(mode, "bounds")) bounds();
    else if (!strcmp(mode, "append-position")) append_position();
    else if (!strcmp(mode, "boundaries")) boundaries();
    else if (!strcmp(mode, "child-fds")) child_descriptors(argv[0]);
    else if (!strcmp(mode, "excluded")) {
        for(int i=2;i<argc;i++)assert(fcntl(atoi(argv[i]),F_GETFD)==-1 && errno==EBADF);
    }
    else assert(!"unknown control");
    puts("files review control passed"); return 0;
}
