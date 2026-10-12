/* Faulted signal installation and integer aliases are interposed: no real
 * broadcast, process-group signal, or process-wide handler change occurs. */
#define _GNU_SOURCE 1
#include "../runtime/minyar_native.h"
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <pthread.h>
#include <sched.h>
#include <signal.h>
#include <stdarg.h>
#include <stdatomic.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
static int fd_step, fd_fail, action_step, action_fail, mask_step, mask_fail, kills, writes, write_mode;
static pid_t captured_pid;
static int captured_signal;
static struct sigaction policies[3], originals[3];
static bool in_flight;
static pthread_t writer_thread;
static pthread_mutex_t pause_mutex=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t pause_condition=PTHREAD_COND_INITIALIZER;
static _Atomic int active_write;
static int writer_fd=-1;
static bool release_write;
static void system_on_shutdown(int);
static void *paused_handler(void *p) { (void)p;system_on_shutdown(SIGTERM);return NULL; }
static int policy_index(int signal) { return signal == SIGTERM ? 0 : signal == SIGINT ? 1 : 2; }
static int intercepted_action(int signal, const struct sigaction *action, struct sigaction *old) {
    int i = policy_index(signal); assert(signal == SIGTERM || signal == SIGINT || signal == SIGPIPE);
    if (old) *old = policies[i];
    if (action) {
        if (action_fail && ++action_step == action_fail) { errno = EACCES; return -1; }
        policies[i] = *action;
    }
    return 0;
}
static int intercepted_mask(int how, const sigset_t *set, sigset_t *old) {
    if(in_flight && how==SIG_SETMASK) {
        in_flight=false;
        assert(!pthread_create(&writer_thread,NULL,paused_handler,NULL));
        pthread_mutex_lock(&pause_mutex);
        while(!atomic_load(&active_write))pthread_cond_wait(&pause_condition,&pause_mutex);
        pthread_mutex_unlock(&pause_mutex);
        errno=EACCES;return -1;
    }
    if (mask_fail && ++mask_step == mask_fail) { mask_fail = 0; errno = EACCES; return -1; }
    return sigprocmask(how, set, old);
}
static int intercepted_fcntl(int fd, int command, ...) {
    int argument = 0;
    if (command != F_GETFL && command != F_GETFD) {
        va_list args; va_start(args, command); argument = va_arg(args, int); va_end(args);
    }
    if (fd_fail && ++fd_step == fd_fail) { errno = EACCES; return -1; }
    return fcntl(fd, command, argument);
}
static int intercepted_kill(pid_t pid, int signal) { kills++; captured_pid = pid; captured_signal = signal; return 0; }
static ssize_t intercepted_write(int fd, const void *p, size_t size) {
    if(writer_fd==-2) {
        pthread_mutex_lock(&pause_mutex);writer_fd=fd;atomic_store(&active_write,1);
        pthread_cond_broadcast(&pause_condition);
        while(!release_write)pthread_cond_wait(&pause_condition,&pause_mutex);
        pthread_mutex_unlock(&pause_mutex);
        assert(fcntl(fd,F_GETFD)>=0);
        ssize_t result=write(fd,p,size);atomic_store(&active_write,0);return result;
    }
    if (write_mode) {
        writes++;
        if (writes == 1) return write_mode == 1 ? 0 : 1;
        errno = EACCES; return -1;
    }
    return write(fd, p, size);
}
static int intercepted_close(int fd) {
    if(fd==writer_fd)assert(!atomic_load(&active_write));
    return close(fd);
}
static int intercepted_yield(void) {
    pthread_mutex_lock(&pause_mutex);release_write=true;pthread_cond_broadcast(&pause_condition);
    pthread_mutex_unlock(&pause_mutex);return sched_yield();
}
#define sigaction(...) intercepted_action(__VA_ARGS__)
#define sigprocmask intercepted_mask
#define fcntl intercepted_fcntl
#define kill intercepted_kill
#define write intercepted_write
#define close intercepted_close
#define sched_yield intercepted_yield
#include "../runtime/native/system.c"
#undef sched_yield
#undef close
#undef write
#undef kill
#undef fcntl
#undef sigprocmask
#undef sigaction
static int descriptors(void) { int n=0; for(int fd=0;fd<256;fd++) if(fcntl(fd,F_GETFD)>=0)n++;return n; }
static void initialize_policies(void) {
    int signals[3] = {SIGTERM, SIGINT, SIGPIPE};
    for (int i=0;i<3;i++) { memset(&policies[i],0,sizeof(policies[i])); assert(!sigaction(signals[i],NULL,&policies[i])); originals[i]=policies[i]; }
}
static void setup(const char *kind, int failure) {
    initialize_policies(); int before=descriptors(); sigset_t original_mask, after;
    assert(!sigprocmask(SIG_SETMASK,NULL,&original_mask));
    if(!strcmp(kind,"fd"))fd_fail=failure;
    if(!strcmp(kind,"action"))action_fail=failure;
    if(!strcmp(kind,"mask"))mask_fail=failure;
    assert(minyar_system_shutdownSignalSocket()==-EACCES);
    assert(descriptors()==before && system_signal_pair[0]==-1 && system_signal_pair[1]==-1);
    for(int i=0;i<3;i++)assert(!memcmp(&policies[i],&originals[i],sizeof(policies[i])));
    assert(!sigprocmask(SIG_SETMASK,NULL,&after));
    for(int s=1;s<NSIG;s++) assert(sigismember(&after,s)==sigismember(&original_mask,s));
    fd_fail=action_fail=mask_fail=0;
    long long socket=minyar_system_shutdownSignalSocket();assert(socket>=0);
    assert(minyar_system_shutdownSignalSocket()==socket);
    for(int i=0;i<2;i++) {
        assert(fcntl(system_signal_pair[i],F_GETFD)&FD_CLOEXEC);
        assert(fcntl(system_signal_pair[i],F_GETFL)&O_NONBLOCK);
    }
    assert(policies[0].sa_handler==system_on_shutdown && policies[1].sa_handler==system_on_shutdown);
    assert(policies[2].sa_handler==SIG_IGN);
    close(system_signal_pair[0]);close(system_signal_pair[1]);assert(descriptors()==before);
}
static void aliases(void) {
    long long bad_pid[]={LLONG_MIN,LLONG_MAX,4294967295LL,4294967296LL+getpid()};
    for(size_t i=0;i<4;i++) { assert(minyar_system_sendSignal(bad_pid[i],15)==-EINVAL);assert(kills==0); }
    long long bad_signal[]={LLONG_MIN,LLONG_MAX,4294967296LL+15};
    for(size_t i=0;i<3;i++) { assert(minyar_system_sendSignal(123,bad_signal[i])==-EINVAL);assert(kills==0); }
    long long allowed[]={123,0,-1,-123};
    for(size_t i=0;i<4;i++) { assert(!minyar_system_sendSignal(allowed[i],0));assert(captured_pid==allowed[i] && captured_signal==0); }
    assert(kills==4);
}
static void saturated(void) {
    initialize_policies();assert(minyar_system_shutdownSignalSocket()>=0);
    unsigned char byte=SIGINT;
    while(write(system_signal_pair[1],&byte,1)==1){}
    assert(errno==EAGAIN||errno==EWOULDBLOCK);
    errno=ENOSPC;system_on_shutdown(SIGTERM);assert(errno==ENOSPC);
    assert(minyar_system_drainShutdownSignals()==SIGINT);
    system_on_shutdown(SIGTERM);assert(minyar_system_drainShutdownSignals()==SIGTERM);
    close(system_signal_pair[0]);close(system_signal_pair[1]);
}
int main(int argc,char **argv) {
    (void)intercepted_mask; /* Also compile the pre-transaction implementation. */
    (void)intercepted_yield;
    assert(argc>=2);
    if(!strcmp(argv[1],"aliases")) aliases();
    else if(!strcmp(argv[1],"setup")) { assert(argc==4);setup(argv[2],atoi(argv[3])); }
    else if(!strcmp(argv[1],"saturated")) saturated();
    else if(!strcmp(argv[1],"rollback-in-flight")) {
        initialize_policies();int before=descriptors();in_flight=true;writer_fd=-2;
        assert(minyar_system_shutdownSignalSocket()==-EACCES);
        assert(!pthread_join(writer_thread,NULL));assert(!atomic_load(&active_write));
        assert(descriptors()==before && system_signal_pair[0]==-1 && system_signal_pair[1]==-1);
        for(int i=0;i<3;i++)assert(!memcmp(&policies[i],&originals[i],sizeof(policies[i])));
    }
    else if(!strcmp(argv[1],"child-fds")) {
        initialize_policies();assert(minyar_system_shutdownSignalSocket()>=0);char first[24],second[24];
        snprintf(first,sizeof(first),"%d",system_signal_pair[0]);snprintf(second,sizeof(second),"%d",system_signal_pair[1]);
        pid_t child=fork();assert(child>=0);
        if(!child) { char *args[]={argv[0],"excluded",first,second,NULL};execv(argv[0],args);_exit(111); }
        int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && WEXITSTATUS(status)==0);
        close(system_signal_pair[0]);close(system_signal_pair[1]);
    }
    else if(!strcmp(argv[1],"excluded")) {
        for(int i=2;i<argc;i++)assert(fcntl(atoi(argv[i]),F_GETFD)==-1 && errno==EBADF);
    }
    else if(!strcmp(argv[1],"stderr")) {
        MinyarText t={(const unsigned char *)"abc",3,0,NULL,NULL};write_mode=1;
        assert(minyar_system_writeStandardError(&t)==-EIO);assert(writes==1);
        writes=0;write_mode=2;assert(minyar_system_writeStandardError(&t)==-EACCES);assert(writes==2);
    } else assert(!"unknown control");
    puts("system review control passed");return 0;
}
