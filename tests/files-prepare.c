/* Worker lifetime/fault controls. No Minyar allocation may enter the worker. */
#define _GNU_SOURCE 1
#include "../runtime/minyar_native.h"
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <pthread.h>
#include <stdarg.h>
#include <stdatomic.h>
#include <stdint.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
static _Atomic int entered, release_worker, sync_calls;
static int block_worker, write_error, sync_error, short_writes, zero_write, interrupted_write;
static int fd_fail, fd_step, mutex_fail, condition_fail, create_fail, pair_fail, allocation_error;
static int mutex_live, condition_live;
static ssize_t controlled_write(int fd, const void *p, size_t n, off_t offset) {
    if (block_worker) {
        atomic_store(&entered, 1);
        struct timespec tick = {0, 1000000};
        while (!atomic_load(&release_worker)) nanosleep(&tick, NULL);
    }
    if (write_error) { errno = write_error; return -1; }
    if (interrupted_write) { interrupted_write=0; errno=EINTR; return -1; }
    if (zero_write) return 0;
    if (short_writes && n > 37) n = 37;
    return pwrite(fd, p, n, offset);
}
static int controlled_sync(int fd) {
    atomic_fetch_add(&sync_calls, 1);
    if (sync_error) { errno = sync_error; return -1; }
    return fsync(fd);
}
static int controlled_fcntl(int fd, int command, ...) {
    if (fd_fail && ++fd_step==fd_fail) { errno=EACCES; return -1; }
#ifdef __APPLE__
    if (command==F_FULLFSYNC) return controlled_sync(fd);
    if (command==F_PREALLOCATE) {
        va_list args; va_start(args,command); void *store=va_arg(args,void *); va_end(args);
        if (allocation_error) { errno=allocation_error; return -1; }
        return fcntl(fd,command,store);
    }
#endif
    if (command==F_GETFL || command==F_GETFD) return fcntl(fd,command);
    va_list args; va_start(args,command); int value=va_arg(args,int); va_end(args);
    return fcntl(fd,command,value);
}
#ifdef __linux__
static int controlled_allocate(int fd,int mode,off_t offset,off_t length) {
    if (allocation_error) { errno=allocation_error; return -1; }
    return fallocate(fd,mode,offset,length);
}
#define fallocate controlled_allocate
#endif
static int controlled_mutex_init(pthread_mutex_t *m,const pthread_mutexattr_t *a) {
    if (mutex_fail) return EAGAIN;
    int rc=pthread_mutex_init(m,a); if(!rc) mutex_live++; return rc;
}
static int controlled_mutex_destroy(pthread_mutex_t *m) {
    int rc=pthread_mutex_destroy(m); if(!rc) mutex_live--; return rc;
}
static int controlled_condition_init(pthread_cond_t *c,const pthread_condattr_t *a) {
    if (condition_fail) return EAGAIN;
    int rc=pthread_cond_init(c,a); if(!rc) condition_live++; return rc;
}
static int controlled_condition_destroy(pthread_cond_t *c) {
    int rc=pthread_cond_destroy(c); if(!rc) condition_live--; return rc;
}
static int controlled_create(pthread_t *t,const pthread_attr_t *a,void *(*f)(void *),void *p) {
    return create_fail ? EAGAIN : pthread_create(t,a,f,p);
}
static int controlled_pair(int domain,int type,int protocol,int sv[2]) {
    if(pair_fail) { errno=ENFILE; return -1; } return socketpair(domain,type,protocol,sv);
}
#define pthread_mutex_init controlled_mutex_init
#define pthread_mutex_destroy controlled_mutex_destroy
#define pthread_cond_init controlled_condition_init
#define pthread_cond_destroy controlled_condition_destroy
#define pthread_create controlled_create
#define socketpair controlled_pair
#define fdatasync controlled_sync
#define fcntl controlled_fcntl
#define pwrite controlled_write
#include "../runtime/native/files.c"
#undef pwrite
#undef fcntl
#undef fdatasync
#undef socketpair
#undef pthread_create
#undef pthread_cond_destroy
#undef pthread_cond_init
#undef pthread_mutex_destroy
#undef pthread_mutex_init
#ifdef __linux__
#undef fallocate
#endif
void minyar_rc_release(void *);
static int descriptors(void) {
    int count=0; for(int i=0;i<512;i++) if(fcntl(i,F_GETFD)>=0) count++; return count;
}
static int temporary(void) {
    char path[]="/tmp/minyar-prepare-XXXXXX"; int fd=mkstemp(path); assert(fd>=0); unlink(path);
    char dirty[4096]; memset(dirty, 123, sizeof(dirty)); assert(write(fd,dirty,sizeof(dirty))==sizeof(dirty));
    return fd;
}
static void verify_zero(int fd, long long length) {
    assert(minyar_files_size(fd)==length);
    MinyarBytes *b=minyar_files_readAt(fd,0,length+10); assert(b->byte_length==length);
    for(long long i=0;i<length;i++) assert(!b->bytes[i]); minyar_rc_release(b);
}
int main(int argc,char **argv) {
    assert(argc==2); int fd=temporary(), before=descriptors();
    if (!strcmp(argv[1],"preallocate")) {
        assert(minyar_files_preallocate(fd,-1)==-EINVAL);
        assert(minyar_files_preallocate(-1,4096)==-EBADF);
        assert(!minyar_files_preallocate(fd,8192)); assert(minyar_files_size(fd)==8192);
        assert(!minyar_files_preallocate(fd,1)); assert(minyar_files_size(fd)==8192);
        MinyarBytes *b=minyar_files_readAt(fd,0,1); assert(b->bytes[0]==123); minyar_rc_release(b);
        assert(!minyar_files_preallocate(fd,0));
    } else if (!strcmp(argv[1],"stale")) {
        long long old=0;
        for(int i=0;i<40;i++) {
            long long h=minyar_files_prepareStart(fd,8192); assert(h>0&&h!=old);
            assert(minyar_files_prepareDone(old)==-EBADF && minyar_files_prepareStop(old)==-EBADF);
            assert(minyar_files_prepareWait(h,5000)==1); verify_zero(fd,8192);
            assert(!minyar_files_prepareStop(h)); old=h;
        }
        assert(minyar_files_prepareNotifySocket(old)==-EBADF);
        assert(minyar_files_prepareError(old)==-EBADF && minyar_files_prepareDrain(old)==-EBADF);
        assert(minyar_files_prepareWait(old,0)==-EBADF);
    } else if (!strcmp(argv[1],"active-close") || !strcmp(argv[1],"saturated")) {
        block_worker=1; long long h=minyar_files_prepareStart(fd,8192); assert(h>0);
        int reader=dup(fd); assert(reader>=0); close(fd);
        struct timespec tick={0,1000000}; for(int i=0;i<5000&&!atomic_load(&entered);i++) nanosleep(&tick,NULL);
        assert(atomic_load(&entered)); assert(!minyar_files_prepareDone(h));
        assert(!minyar_files_prepareDrain(h)); assert(minyar_files_prepareWait(h,0)==-ETIMEDOUT);
        assert(minyar_files_prepareWait(h,-2)==-EINVAL);
        if(!strcmp(argv[1],"saturated")) {
            FilesPrepare *p=files_prepare(h); char byte=1;
            while(write(p->notify_write,&byte,1)==1) {}
            assert(errno==EAGAIN||errno==EWOULDBLOCK);
        }
        atomic_store(&release_worker,1); assert(minyar_files_prepareWait(h,5000)==1);
        verify_zero(reader,8192); assert(minyar_files_prepareDrain(h)>0); assert(!minyar_files_prepareStop(h));
        close(reader); assert(descriptors()==before-1); return 0;
    } else if (!strcmp(argv[1],"write-error") || !strcmp(argv[1],"sync-error") ||
               !strcmp(argv[1],"allocate-error") || !strcmp(argv[1],"zero-write")) {
        int error=ENOSPC;
        if(!strcmp(argv[1],"write-error")) write_error=ENOSPC;
        if(!strcmp(argv[1],"sync-error")) sync_error=error=EIO;
        if(!strcmp(argv[1],"allocate-error")) allocation_error=error=ENOSPC;
        if(!strcmp(argv[1],"zero-write")) zero_write=1, error=EIO;
        long long h=minyar_files_prepareStart(fd,65536); assert(h>0);
        assert(minyar_files_prepareWait(h,5000)==-error); assert(minyar_files_prepareDone(h)==1);
        assert(minyar_files_prepareError(h)==-error); assert(minyar_files_prepareWait(h,0)==-error);
        assert(minyar_files_prepareDrain(h)>0); assert(minyar_files_prepareStop(h)==-error);
        assert(atomic_load(&sync_calls)==(!strcmp(argv[1],"sync-error") ? 1 : 0));
    } else if (!strcmp(argv[1],"short")) {
        short_writes=interrupted_write=1; long long h=minyar_files_prepareStart(fd,256); assert(h>0);
        assert(minyar_files_prepareWait(h,5000)==1); verify_zero(fd,256); assert(!minyar_files_prepareStop(h));
        assert(atomic_load(&sync_calls)==1);
    } else if (!strcmp(argv[1],"stop")) {
        long long h=minyar_files_prepareStart(fd,8192); assert(h>0);
        assert(!minyar_files_prepareStop(h)); verify_zero(fd,8192);
    } else if (!strcmp(argv[1],"capacity")) {
        long long jobs[FILES_MAX_PREPARES];
        for(int i=0;i<FILES_MAX_PREPARES;i++) { jobs[i]=minyar_files_prepareStart(fd,0); assert(jobs[i]>0); }
        assert(minyar_files_prepareStart(fd,0)==-EMFILE);
        for(int i=0;i<FILES_MAX_PREPARES;i++) assert(!minyar_files_prepareStop(jobs[i]));
    } else if (!strcmp(argv[1],"cross-kind")) {
        long long s=minyar_files_syncerStart(fd),p=minyar_files_prepareStart(fd,0); assert(s>0&&p>0);
        assert(minyar_files_prepareDone(s)==-EBADF && minyar_files_prepareError(s)==-EBADF);
        assert(minyar_files_prepareNotifySocket(s)==-EBADF && minyar_files_prepareDrain(s)==-EBADF);
        assert(minyar_files_prepareWait(s,0)==-EBADF && minyar_files_prepareStop(s)==-EBADF);
        assert(minyar_files_syncerNotifySocket(p)==-EBADF && minyar_files_syncerRequest(p,1)==-EBADF);
        assert(minyar_files_syncerSynced(p)==-EBADF && minyar_files_syncerError(p)==-EBADF);
        assert(minyar_files_syncerDrain(p)==-EBADF && minyar_files_syncerWait(p,1,0)==-EBADF);
        assert(minyar_files_syncerSwitch(p,fd,0)==-EBADF && minyar_files_syncerStop(p)==-EBADF);
        assert(!minyar_files_prepareStop(p)); assert(!minyar_files_syncerStop(s));
    } else if (!strncmp(argv[1],"setup-",6)) {
        const char *kind=argv[1]+6; int error=EAGAIN;
        if(!strncmp(kind,"fd-",3)) fd_fail=atoi(kind+3),error=EACCES;
        else if(!strcmp(kind,"mutex")) mutex_fail=1;
        else if(!strcmp(kind,"condition")) condition_fail=1;
        else if(!strcmp(kind,"create")) create_fail=1;
        else if(!strcmp(kind,"pair")) pair_fail=1,error=ENFILE;
        else abort();
        assert(minyar_files_prepareStart(fd,1)==-error);
        assert(descriptors()==before && !mutex_live && !condition_live);
        for(int i=0;i<FILES_MAX_PREPARES;i++) assert(!files_prepares[i].used);
        fd_fail=mutex_fail=condition_fail=create_fail=pair_fail=0;
        long long h=minyar_files_prepareStart(fd,1); assert(h>0); assert(!minyar_files_prepareStop(h));
    } else abort();
    assert(descriptors()==before && !mutex_live && !condition_live); close(fd); return 0;
}
