#define MINYAR_RC_TESTING 1
#ifdef MINYAR_TEST_CYCLES
#include "../build/thread-cycle-engine.c"
#else
#include "../runtime/minyar_runtime.c"
#endif
#include <assert.h>
#include <fcntl.h>
#include <linux/kvm.h>

static RcThreadLeaf *map(long long length) {
    return minyar_native_region_map(length, PROT_READ | PROT_WRITE,
                                   MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
}
static RcThreadLeaf *regions(RcThreadLeaf *a, RcThreadLeaf *b) {
    MinyarList *list = minyar_list_new();
    minyar_list_references(list);
    minyar_list_add(list, (long long)(uintptr_t)a);
    minyar_list_add(list, (long long)(uintptr_t)b);
    RcThreadLeaf *set = minyar_native_regions_share(list);
    minyar_list_truncate(list, 0);
    assert(minyar_native_regions_length(set) == 2);
    minyar_rc_release(list);
    return set;
}
static long long counter(long long seed, void *input, void *channel) {
    (void)channel;
    minyar_rc_enter(1);
    RcThreadLeaf *region = minyar_native_regions_get(input, 0);
    minyar_rc_local_take(0, region);
    for (long long i = 0; i < seed; i++) minyar_native_region_add_i64(region, 16, 1);
    assert(minyar_native_region_get_uint8(region, 0) == 123);
    minyar_rc_leave();
    return seed;
}
static void shared_lifetime(void) {
    RcThreadLeaf *a = map(4096), *b = map(64);
    minyar_native_region_set_uint8(a, 0, 123);
    minyar_native_region_set_uint16(a, 1, 65535);
    minyar_native_region_set_uint32(a, 3, UINT32_MAX);
    minyar_native_region_set_int64(a, 7, LLONG_MIN);
    assert(minyar_native_region_get_uint16(a, 1) == 65535);
    assert(minyar_native_region_get_uint32(a, 3) == UINT32_MAX);
    assert(minyar_native_region_get_int64(a, 7) == LLONG_MIN);
    minyar_native_region_store_i64(a, 16, 0);
    minyar_native_region_store_u32(b, 0, 3);
    assert(minyar_native_region_cas_u32(b, 0, 0, 1) == 3);
    assert(minyar_native_region_load_u32(b, 0) == 3);
    MinyarBytes *bytes = minyar_bytes_new(3);
    minyar_bytes_set_uint8(bytes, 0, 7);
    minyar_native_region_copy_from(a, 32, bytes);
    MinyarBytes *copy = minyar_native_region_copy_to(a, 32, 3);
    assert(minyar_bytes_get_uint8(copy, 0) == 7);
    minyar_rc_release(bytes); minyar_rc_release(copy);
    RcThreadLeaf *set = regions(a, b), *channel = minyar_bytes_channel_new(0, 1);
    RcThreadLeaf *threads[4];
    for (unsigned i = 0; i < 4; i++) threads[i] = minyar_thread_spawn(counter, 10000, set, channel);
    minyar_rc_release(a); minyar_rc_release(b); minyar_rc_release(channel);
    for (unsigned i = 0; i < 4; i++) {
        assert(minyar_thread_join(threads[i]) == 10000);
        minyar_rc_release(threads[i]);
    }
    a = minyar_native_regions_get(set, 0);
    assert(minyar_native_region_load_i64(a, 16) == 40000);
    minyar_rc_release(a); minyar_rc_release(set);
    rc_thread_domain_drain();
    assert(atomic_load(&rc_native_region_maps) == atomic_load(&rc_native_region_unmaps));
}
static void failures_and_files(void) {
    errno = EDOM;
    MinyarRecord *bad = minyar_native_region_try_map(0, 3, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    assert(errno == EDOM && minyar_thread_result_code(bad) == -EINVAL);
    minyar_rc_release(bad);
    bad = minyar_native_region_try_map(4096, 3, MAP_PRIVATE | MAP_FIXED | MAP_ANONYMOUS, -1, 0);
    assert(minyar_thread_result_code(bad) == -EINVAL);
    minyar_rc_release(bad);
    int fd = memfd_create("minyar-region", MFD_CLOEXEC);
    assert(fd >= 0 && !ftruncate(fd, 4096));
    RcThreadLeaf *shared = minyar_native_region_map(4096, 3, MAP_SHARED, fd, 0);
    RcThreadLeaf *cow = minyar_native_region_map(4096, 3, MAP_PRIVATE, fd, 0);
    minyar_native_region_set_uint8(shared, 0, 41);
    assert(minyar_native_region_get_uint8(cow, 0) == 41);
    minyar_native_region_set_uint8(cow, 0, 42);
    assert(minyar_native_region_get_uint8(shared, 0) == 41);
    assert(!madvise((void *)(uintptr_t)minyar_native_region_address(shared), 4096, MADV_HUGEPAGE));
    assert(!close(fd));
    assert(minyar_native_region_get_uint8(shared, 0) == 41);
    minyar_rc_release(cow); minyar_rc_release(shared);
    int event = (int)minyar_thread_eventfd(EFD_CLOEXEC | EFD_NONBLOCK);
    assert(event >= 0);
    assert(minyar_thread_eventfd_read(event) == -EAGAIN && errno == EDOM);
    assert(minyar_thread_eventfd_notify(event, 2) == 0);
    assert(minyar_thread_eventfd_read(event) == 2 && errno == EDOM);
    assert(!close(event));
}
static long long dispatch(long long descriptor, void *input, void *channel) {
    (void)channel;
    minyar_rc_enter(2);
    RcThreadLeaf *slot = minyar_native_regions_get(input, 0);
    RcThreadLeaf *run = minyar_native_regions_get(input, 1);
    minyar_rc_local_take(0, slot); minyar_rc_local_take(1, run);
    while (minyar_native_region_load_u32(slot, 0) != 3) {
        long long result = minyar_native_region_kernel_run(run, descriptor);
        if (minyar_native_region_load_u32(slot, 0) == 3) break;
        minyar_native_region_set_int64(slot, 8, result);
        minyar_native_region_add_i64(slot, 32, 1);
        long long prior = minyar_native_region_cas_u32(slot, 0, 0, 1);
        if (prior == 3) break;
        assert(prior == 0);
        assert(minyar_thread_eventfd_notify(minyar_native_region_get_int64(slot, 24), 1) == 0);
        while (minyar_native_region_load_u32(slot, 0) == 1) assert(minyar_thread_sleep_ns(100000) == 0);
        prior = minyar_native_region_cas_u32(slot, 0, 2, 0);
        if (prior == 3) break;
        assert(prior == 2);
    }
    minyar_rc_leave();
    return 0;
}
static long long kicked(long long descriptor, void *run, void *channel) {
    (void)channel;
    return minyar_native_region_kernel_run(run, descriptor);
}
static void real_kvm(void) {
    int kvm = open("/dev/kvm", O_RDWR | O_CLOEXEC);
    assert(kvm >= 0 && ioctl(kvm, KVM_GET_API_VERSION, 0) == 12);
    int vm = ioctl(kvm, KVM_CREATE_VM, 0);
    assert(vm >= 0);
    RcThreadLeaf *memory = map(4096);
    const unsigned char code[] = {0xe4, 0x10, 0xe6, 0x11, 0xf4};
    for (size_t i = 0; i < sizeof(code); i++) minyar_native_region_set_uint8(memory, (long long)i, code[i]);
    struct kvm_userspace_memory_region guest = {0};
    guest.memory_size = 4096;
    guest.userspace_addr = (uintptr_t)minyar_native_region_address(memory);
    assert(!ioctl(vm, KVM_SET_USER_MEMORY_REGION, &guest));
    int vcpu = ioctl(vm, KVM_CREATE_VCPU, 0);
    assert(vcpu >= 0);
    int size = ioctl(kvm, KVM_GET_VCPU_MMAP_SIZE, 0);
    assert(size > 0);
    RcThreadLeaf *run = minyar_native_region_map(size, 3, MAP_SHARED, vcpu, 0);
    struct kvm_sregs sregs;
    assert(!ioctl(vcpu, KVM_GET_SREGS, &sregs));
    sregs.cs.base = 0; sregs.cs.selector = 0;
    assert(!ioctl(vcpu, KVM_SET_SREGS, &sregs));
    struct kvm_regs regs = {0}; regs.rflags = 2;
    assert(!ioctl(vcpu, KVM_SET_REGS, &regs));
    RcThreadLeaf *slot = map(64), *set = regions(slot, run), *channel = minyar_bytes_channel_new(0, 1);
    int event = (int)minyar_thread_eventfd(EFD_CLOEXEC);
    assert(event >= 0);
    minyar_native_region_set_int64(slot, 16, vcpu);
    minyar_native_region_set_int64(slot, 24, event);
    minyar_native_region_set_int64(slot, 40, minyar_native_region_address(run));
    RcThreadLeaf *thread = minyar_thread_spawn(dispatch, vcpu, set, channel);
    for (unsigned exit = 0; exit < 3; exit++) {
        assert(minyar_thread_eventfd_read(event) == 1);
        assert(minyar_native_region_load_u32(slot, 0) == 1);
        assert(minyar_native_region_get_int64(slot, 8) == 0);
        if (exit < 2) {
            assert(minyar_native_region_get_uint32(run, offsetof(struct kvm_run, exit_reason)) == KVM_EXIT_IO);
            long long offset = minyar_native_region_get_int64(run, offsetof(struct kvm_run, io.data_offset));
            if (!exit) minyar_native_region_set_uint8(run, offset, 42);
            else assert(minyar_native_region_get_uint8(run, offset) == 42);
            minyar_native_region_store_u32(slot, 0, 2);
        } else {
            assert(minyar_native_region_get_uint32(run, offsetof(struct kvm_run, exit_reason)) == KVM_EXIT_HLT);
            minyar_native_region_store_u32(slot, 0, 3);
            assert(minyar_thread_kernel_kick(thread, run) == 0);
        }
    }
    assert(minyar_thread_join(thread) == 0);
    assert(minyar_native_region_load_u32(slot, 0) == 3);
    assert(minyar_native_region_load_i64(slot, 32) == 3);
    assert(minyar_thread_kernel_kick(thread, run) == -ESRCH);
    minyar_rc_release(thread);
    minyar_native_region_set_uint8(memory, 0, 0xeb); minyar_native_region_set_uint8(memory, 1, 0xfe);
    regs.rip = 0; assert(!ioctl(vcpu, KVM_SET_REGS, &regs));
    minyar_native_region_store_u8(run, 1, 0);
    thread = minyar_thread_spawn(kicked, vcpu, run, channel);
    assert(minyar_thread_kernel_kick(thread, run) == 0);
    assert(minyar_thread_join(thread) == -EINTR);
    minyar_rc_release(thread);
    assert(!close(event));
    minyar_rc_release(channel); minyar_rc_release(set); minyar_rc_release(slot);
    minyar_rc_release(run); minyar_rc_release(memory);
    rc_thread_domain_drain();
    assert(!close(vcpu)); assert(!close(vm)); assert(!close(kvm));
    puts("native regions real KVM IO dispatch, HLT, stop-preserving CAS and entering/parked kick passed");
}
static void fatal_case(const char *name) {
    RcThreadLeaf *region = map(64);
    if (!strcmp(name, "bounds")) minyar_native_region_get_int64(region, 60);
    else if (!strcmp(name, "negative")) minyar_native_region_get_uint8(region, -1);
    else if (!strcmp(name, "alignment")) minyar_native_region_store_u32(region, 1, 0);
    else if (!strcmp(name, "value")) minyar_native_region_set_uint8(region, 0, 256);
    else if (!strcmp(name, "result")) {
        MinyarRecord *r = minyar_native_region_try_map(0, 3, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        minyar_native_region_result_value(r);
    } else if (!strcmp(name, "protection")) {
        RcThreadLeaf *readonly = minyar_native_region_map(4096, 1, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        minyar_native_region_set_uint8(readonly, 0, 1);
    } else abort();
}
int main(int count, char **arguments) {
    if (count == 2) { fatal_case(arguments[1]); return 99; }
    shared_lifetime(); failures_and_files(); real_kvm();
    rc_thread_domain_dispose();
    assert(atomic_load(&rc_native_region_maps) == atomic_load(&rc_native_region_unmaps));
    assert(atomic_load(&rc_thread_native_bytes) == 0 && atomic_load(&rc_thread_native_allocations) == 0);
    assert(rc_object_count == 0 && rc_bytes == 0);
    puts("native regions sharing, bounds, atomic fields, mapping lifetime, CoW and eventfd passed");
}
