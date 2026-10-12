#define MINYAR_RC_TESTING 1
#ifdef MINYAR_TEST_CYCLES
#include "../build/thread-cycle-engine.c"
#else
#include "../runtime/minyar_runtime.c"
#endif
#include <assert.h>
#include "thread-test-host.h"
#ifdef __linux__
#include <fcntl.h>
#if defined(__x86_64__)
#include <linux/kvm.h>
#include <sys/mman.h>
#endif
#endif
static RcTestGate started;
static _Atomic unsigned sleeping, progressed;
#ifndef _WIN32
static volatile sig_atomic_t interrupted;
static void wake_signal(int signal_number) { (void)signal_number; interrupted++; }
static long long monotonic_ns(void) {
    struct timespec t;
    assert(!clock_gettime(CLOCK_MONOTONIC, &t));
    return (long long)t.tv_sec * 1000000000 + t.tv_nsec;
}
#endif
static long long sleeper(long long duration, void *input, void *channel) {
    (void)input; (void)channel;
    minyar_rc_enter(128);
    MinyarText *integer = minyar_integer_text(12345);
    for (long long i = 0; i < 128; i++) minyar_rc_local(i, integer);
    minyar_rc_release(integer);
    minyar_rc_leave();
#if defined(MINYAR_BOUNDED_RC) && MINYAR_RC_POLL_BUDGET < 128
    assert(rc_pending_count);
#endif
    atomic_store(&sleeping, 1);
    rc_test_gate_arrive(&started);
    errno = EDOM;
    assert(minyar_thread_sleep_ns(duration) == 0);
    assert(errno == EDOM);
    assert(!rc_pending_count);
    atomic_store(&sleeping, 0);
    return 71;
}
static long long progress(long long unused, void *input, void *channel) {
    (void)unused; (void)channel;
    assert(atomic_load(&sleeping));
    assert(minyar_frozen_bytes_get_uint8(input, 0) == 42);
    MinyarBytes *bytes = minyar_frozen_bytes_local_copy(input);
    minyar_bytes_add(bytes, 7);
    minyar_rc_release(bytes);
    atomic_fetch_add(&progressed, 1);
    return 93;
}
static void blocking_progress(void) {
    MinyarBytes *b = minyar_bytes_new(1);
    minyar_bytes_set(b, 0, 42);
    RcThreadLeaf *f = minyar_frozen_bytes_copy(b);
    RcThreadLeaf *c = minyar_bytes_channel_new(0, 1);
    rc_test_gate_init(&started, 2);
#ifndef _WIN32
    struct sigaction action = {0}, previous;
    action.sa_handler = wake_signal;
    assert(!sigemptyset(&action.sa_mask));
    assert(!sigaction(SIGUSR1, &action, &previous));
    long long before = monotonic_ns();
#endif
    RcThreadLeaf *t = minyar_thread_spawn(sleeper, 200000000, f, c);
    rc_test_gate_arrive(&started);
    RcThreadLeaf *p = minyar_thread_spawn(progress, 0, f, c);
    assert(minyar_thread_join(p) == 93);
    assert(atomic_load(&sleeping) && atomic_load(&progressed) == 1);
#ifndef _WIN32
    for (unsigned i = 0; i < 3; i++) {
        assert(!pthread_kill(((RcManagedThread *)t->control)->thread, SIGUSR1));
        assert(minyar_thread_sleep_ns(10000000) == 0);
    }
#endif
    assert(minyar_thread_join(t) == 71);
#ifndef _WIN32
    assert(monotonic_ns() - before >= 200000000);
    assert(interrupted);
    assert(!sigaction(SIGUSR1, &previous, NULL));
#endif
    minyar_rc_release(t); minyar_rc_release(p);
    minyar_thread_join_children();
    rc_test_gate_dispose(&started);
    minyar_rc_release(c); minyar_rc_release(f); minyar_rc_release(b);
}
static void kvm_capability(void) {
#if defined(__linux__) && defined(__x86_64__)
    int kvm = open("/dev/kvm", O_RDWR | O_CLOEXEC);
    if (kvm < 0) {
        printf("KVM capability unqualified: open /dev/kvm errno %d\n", errno);
        return;
    }
    assert(ioctl(kvm, KVM_GET_API_VERSION, 0) == 12);
    int vm = ioctl(kvm, KVM_CREATE_VM, 0);
    assert(vm >= 0);
    void *memory = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    assert(memory != MAP_FAILED);
    ((unsigned char *)memory)[0] = 0xf4; /* Real-mode HLT guest. */
    struct kvm_userspace_memory_region region = {0};
    region.memory_size = 4096;
    region.userspace_addr = (uintptr_t)memory;
    assert(!ioctl(vm, KVM_SET_USER_MEMORY_REGION, &region));
    int vcpu = ioctl(vm, KVM_CREATE_VCPU, 0);
    assert(vcpu >= 0);
    int mapping_size = ioctl(kvm, KVM_GET_VCPU_MMAP_SIZE, 0);
    assert(mapping_size > 0);
    struct kvm_run *run = mmap(NULL, (size_t)mapping_size, PROT_READ | PROT_WRITE, MAP_SHARED, vcpu, 0);
    assert(run != MAP_FAILED);
    struct kvm_sregs sregs;
    assert(!ioctl(vcpu, KVM_GET_SREGS, &sregs));
    sregs.cs.base = 0; sregs.cs.selector = 0;
    assert(!ioctl(vcpu, KVM_SET_SREGS, &sregs));
    struct kvm_regs regs = {0};
    regs.rflags = 2;
    assert(!ioctl(vcpu, KVM_SET_REGS, &regs));
    errno = EDOM;
    assert(minyar_thread_kernel_run(vcpu) == 0);
    assert(errno == EDOM && run->exit_reason == KVM_EXIT_HLT);
    assert(!munmap(run, (size_t)mapping_size));
    assert(!close(vcpu)); assert(!close(vm)); assert(!close(kvm));
    assert(!munmap(memory, 4096));
    puts("KVM capability passed: real vCPU KVM_RUN exited HLT");
#else
    puts("KVM capability unqualified: fixture requires Linux x86-64");
#endif
}
int main(void) {
    errno = EDOM;
    assert(minyar_thread_process_id() > 0 && errno == EDOM);
    assert(minyar_thread_sleep_ns(-1) == -EINVAL && errno == EDOM);
    assert(minyar_thread_sleep_ns(0) == 0 && errno == EDOM);
    assert(minyar_thread_fsync(-1) == -EINVAL && errno == EDOM);
    assert(minyar_thread_fsync((long long)INT_MAX + 1) == -EINVAL && errno == EDOM);
    assert(minyar_thread_kernel_run(-1) == -EINVAL && errno == EDOM);
    assert(minyar_thread_kernel_run((long long)INT_MAX + 1) == -EINVAL && errno == EDOM);
    FILE *file = tmpfile();
    assert(file);
    assert(fwrite("fixture", 1, 7, file) == 7 && !fflush(file));
#ifdef _WIN32
    int descriptor = _fileno(file);
#else
    int descriptor = fileno(file);
#endif
    errno = EDOM;
    assert(minyar_thread_fsync(descriptor) == 0 && errno == EDOM);
#ifdef __linux__
    assert(minyar_thread_kernel_run(descriptor) == -ENOTTY && errno == EDOM);
#else
    assert(minyar_thread_kernel_run(descriptor) == -ENOSYS && errno == EDOM);
#endif
    assert(!fclose(file));
    blocking_progress();
    kvm_capability();
    rc_thread_domain_dispose();
    assert(!rc_object_count && !rc_bytes);
    assert(!atomic_load(&rc_thread_native_bytes) && !atomic_load(&rc_thread_native_allocations));
    puts("thread pointer-free OS wrappers, errno and blocking progress passed");
}
