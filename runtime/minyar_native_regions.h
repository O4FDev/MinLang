#ifndef MINYAR_NATIVE_REGIONS_H
#define MINYAR_NATIVE_REGIONS_H
#include <errno.h>
#ifdef __linux__
#include <sys/mman.h>
#include <sys/eventfd.h>
#include <sys/ioctl.h>
#include <signal.h>
#include <unistd.h>
#endif

typedef struct {
    RcThreadControl owner;
    unsigned char *base;
    size_t length;
    unsigned protection;
} RcNativeRegion;
typedef struct {
    RcThreadControl owner;
    size_t length;
    RcNativeRegion *regions[];
} RcNativeRegions;
#if defined(MINYAR_RC_TESTING) && defined(__linux__)
static _Atomic size_t rc_native_region_maps, rc_native_region_unmaps;
#endif

void minyar_native_thread_setup(void) {
}

#ifdef __linux__
static void rc_native_region_destroy(void *pointer) {
    RcNativeRegion *region = pointer;
    if (munmap(region->base, region->length))
        minyar_stop("a native memory region could not be unmapped.");
    RC_NATIVE_ACCOUNT(atomic_fetch_add(&rc_native_region_unmaps, 1));
    rc_thread_native_free(region, sizeof(*region));
}
#endif

static long long rc_native_region_map(long long length, long long protection, long long flags,
                                      long long descriptor, long long offset, void **output) {
    int saved_errno = errno;
    long long status = -ENOSYS;
#ifdef __linux__
    if (length <= 0 || (unsigned long long)length > SIZE_MAX || protection < 0 ||
        (protection & ~(PROT_READ | PROT_WRITE | PROT_EXEC)) || flags < 0 || flags > INT_MAX ||
        (flags & MAP_FIXED) || descriptor < -1 || descriptor > INT_MAX || offset < 0 ||
        (long long)(off_t)offset != offset) {
        status = -EINVAL;
    } else {
        void *base =
            mmap(NULL, (size_t)length, (int)protection, (int)flags, (int)descriptor, (off_t)offset);
        if (base == MAP_FAILED)
            status = -(long long)errno;
        else {
            RcNativeRegion *region = rc_thread_native_allocate(sizeof(*region));
            rc_thread_control_init(&region->owner, 1, rc_native_region_destroy);
            region->base = base;
            region->length = (size_t)length;
            region->protection = (unsigned)protection;
            RC_NATIVE_ACCOUNT(atomic_fetch_add(&rc_native_region_maps, 1));
            *output = rc_thread_wrap(region);
            status = 0;
        }
    }
#else
    (void)length;
    (void)protection;
    (void)flags;
    (void)descriptor;
    (void)offset;
    (void)output;
#endif
    errno = saved_errno;
    return status;
}

void *minyar_native_region_map(long long length, long long protection, long long flags,
                               long long descriptor, long long offset) {
    void *region = NULL;
    long long status = rc_native_region_map(length, protection, flags, descriptor, offset, &region);
    if (status) {
        char message[120];
        snprintf(message, sizeof(message), "native memory mapping failed with code %lld.", status);
        minyar_stop(message);
    }
    return region;
}

void *minyar_native_region_try_map(long long length, long long protection, long long flags,
                                   long long descriptor, long long offset) {
    void *region = NULL;
    long long status = rc_native_region_map(length, protection, flags, descriptor, offset, &region);
    MinyarRecord *record = minyar_record_new(2);
    minyar_record_set(record, 0, status);
    minyar_record_set_reference(record, 1, (long long)(uintptr_t)region);
    minyar_rc_release(region);
    return record;
}

void *minyar_native_region_result_value(const MinyarRecord *result) {
    if (minyar_record_get(result, 0))
        minyar_stop("an unsuccessful NativeRegion Result has no region.");
    void *region = (void *)(uintptr_t)minyar_record_get(result, 1);
    minyar_rc_retain(region);
    return region;
}

static unsigned char *rc_native_region_range(const RcThreadLeaf *leaf, long long offset,
                                             long long size, unsigned protection) {
    RcNativeRegion *region = leaf->control;
    if (offset < 0 || size < 0 || (unsigned long long)size > region->length ||
        (unsigned long long)offset > region->length - (size_t)size)
        minyar_stop("this access is outside the native memory region.");
    if ((region->protection & protection) != protection)
        minyar_stop("this native memory region does not permit this access.");
    return region->base + offset;
}

long long minyar_native_region_length(const RcThreadLeaf *leaf) {
    return (long long)((RcNativeRegion *)leaf->control)->length;
}
long long minyar_native_region_address(const RcThreadLeaf *leaf) {
    return (long long)(uintptr_t)((RcNativeRegion *)leaf->control)->base;
}

#define MINYAR_REGION_INTEGER(Name, Size, Cast, Maximum)                                           \
    long long minyar_native_region_get_##Name(const RcThreadLeaf *leaf, long long offset) {        \
        const unsigned char *data = rc_native_region_range(leaf, offset, Size, 1);                 \
        return (long long)(Cast)bytes_load(data, Size);                                            \
    }                                                                                              \
    void minyar_native_region_set_##Name(const RcThreadLeaf *leaf, long long offset,               \
                                         long long value) {                                        \
        if (Size != 8 && ((unsigned long long)value > Maximum))                                    \
            minyar_stop("this value does not fit in the native memory region field.");             \
        unsigned char *data = rc_native_region_range(leaf, offset, Size, 2);                       \
        bytes_store(data, (unsigned long long)value, Size);                                        \
    }
MINYAR_REGION_INTEGER(uint8, 1, uint8_t, UINT8_MAX)
MINYAR_REGION_INTEGER(uint16, 2, uint16_t, UINT16_MAX)
MINYAR_REGION_INTEGER(uint32, 4, uint32_t, UINT32_MAX)
MINYAR_REGION_INTEGER(int64, 8, int64_t, UINT64_MAX)
#undef MINYAR_REGION_INTEGER

static void *rc_native_region_atomic(const RcThreadLeaf *leaf, long long offset, size_t size,
                                     size_t alignment, unsigned protection) {
    void *address = rc_native_region_range(leaf, offset, (long long)size, protection);
    if ((uintptr_t)address % alignment)
        minyar_stop("a native memory atomic field is not aligned.");
    return address;
}

long long minyar_native_region_load_u8(const RcThreadLeaf *leaf, long long offset) {
    _Atomic uint8_t *p =
        rc_native_region_atomic(leaf, offset, sizeof(*p), _Alignof(_Atomic uint8_t), 1);
    return atomic_load_explicit(p, memory_order_acquire);
}
void minyar_native_region_store_u8(const RcThreadLeaf *leaf, long long offset, long long value) {
    if ((unsigned long long)value > UINT8_MAX)
        minyar_stop("this atomic value does not fit in UInt8.");
    _Atomic uint8_t *p =
        rc_native_region_atomic(leaf, offset, sizeof(*p), _Alignof(_Atomic uint8_t), 2);
    atomic_store_explicit(p, (uint8_t)value, memory_order_release);
}
long long minyar_native_region_load_u32(const RcThreadLeaf *leaf, long long offset) {
    _Atomic uint32_t *p =
        rc_native_region_atomic(leaf, offset, sizeof(*p), _Alignof(_Atomic uint32_t), 1);
    return atomic_load_explicit(p, memory_order_acquire);
}
void minyar_native_region_store_u32(const RcThreadLeaf *leaf, long long offset, long long value) {
    if ((unsigned long long)value > UINT32_MAX)
        minyar_stop("this atomic value does not fit in UInt32.");
    _Atomic uint32_t *p =
        rc_native_region_atomic(leaf, offset, sizeof(*p), _Alignof(_Atomic uint32_t), 2);
    atomic_store_explicit(p, (uint32_t)value, memory_order_release);
}
long long minyar_native_region_cas_u32(const RcThreadLeaf *leaf, long long offset,
                                       long long expected, long long value) {
    if ((unsigned long long)expected > UINT32_MAX || (unsigned long long)value > UINT32_MAX)
        minyar_stop("this atomic value does not fit in UInt32.");
    _Atomic uint32_t *p =
        rc_native_region_atomic(leaf, offset, sizeof(*p), _Alignof(_Atomic uint32_t), 3);
    uint32_t old = (uint32_t)expected;
    atomic_compare_exchange_strong_explicit(p, &old, (uint32_t)value, memory_order_acq_rel,
                                            memory_order_acquire);
    return old;
}
long long minyar_native_region_load_i64(const RcThreadLeaf *leaf, long long offset) {
    _Atomic uint64_t *p =
        rc_native_region_atomic(leaf, offset, sizeof(*p), _Alignof(_Atomic uint64_t), 1);
    return (long long)atomic_load_explicit(p, memory_order_acquire);
}
void minyar_native_region_store_i64(const RcThreadLeaf *leaf, long long offset, long long value) {
    _Atomic uint64_t *p =
        rc_native_region_atomic(leaf, offset, sizeof(*p), _Alignof(_Atomic uint64_t), 2);
    atomic_store_explicit(p, (uint64_t)value, memory_order_release);
}
long long minyar_native_region_add_i64(const RcThreadLeaf *leaf, long long offset,
                                       long long value) {
    _Atomic uint64_t *p =
        rc_native_region_atomic(leaf, offset, sizeof(*p), _Alignof(_Atomic uint64_t), 3);
    return (long long)atomic_fetch_add_explicit(p, (uint64_t)value, memory_order_acq_rel);
}

void minyar_native_region_copy_from(const RcThreadLeaf *leaf, long long offset,
                                    const MinyarBytes *bytes) {
    unsigned char *p = rc_native_region_range(leaf, offset, bytes->byte_length, 2);
    memcpy(p, bytes->bytes, (size_t)bytes->byte_length);
}
void *minyar_native_region_copy_to(const RcThreadLeaf *leaf, long long offset, long long length) {
    const unsigned char *p = rc_native_region_range(leaf, offset, length, 1);
    MinyarBytes *bytes = minyar_bytes_new(length);
    memcpy((void *)bytes->bytes, p, (size_t)length);
    return bytes;
}

static void rc_native_regions_destroy(void *pointer) {
    RcNativeRegions *set = pointer;
    for (size_t i = 0; i < set->length; i++)
        rc_thread_control_release(set->regions[i]);
    rc_thread_native_free(set, sizeof(*set) + set->length * sizeof(*set->regions));
}
void *minyar_native_regions_share(const MinyarList *list) {
    if ((unsigned long long)list->length >
        (SIZE_MAX - sizeof(RcNativeRegions)) / sizeof(RcNativeRegion *))
        minyar_stop("too many native memory regions.");
    RcNativeRegions *set =
        rc_thread_native_allocate(sizeof(*set) + (size_t)list->length * sizeof(*set->regions));
    rc_thread_control_init(&set->owner, 1, rc_native_regions_destroy);
    set->length = (size_t)list->length;
    for (size_t i = 0; i < set->length; i++) {
        RcThreadLeaf *leaf = (void *)(uintptr_t)list->values[i];
        set->regions[i] = leaf->control;
        rc_thread_control_retain(set->regions[i]);
    }
    return rc_thread_wrap(set);
}
long long minyar_native_regions_length(const RcThreadLeaf *leaf) {
    return (long long)((RcNativeRegions *)leaf->control)->length;
}
void *minyar_native_regions_get(const RcThreadLeaf *leaf, long long index) {
    RcNativeRegions *set = leaf->control;
    if (index < 0 || (unsigned long long)index >= set->length)
        minyar_stop("this native memory region index is outside its set.");
    rc_thread_control_retain(set->regions[index]);
    return rc_thread_wrap(set->regions[index]);
}

#ifdef __linux__
static pthread_once_t rc_native_kick_once = PTHREAD_ONCE_INIT;
static int rc_native_kick_error;
static void rc_native_on_kick(int signal) {
    (void)signal;
}
static void rc_native_kick_install(void) {
    struct sigaction previous;
    if (sigaction(SIGUSR1, NULL, &previous))
        rc_native_kick_error = errno;
    else if (previous.sa_handler != SIG_DFL)
        rc_native_kick_error = EBUSY;
    else {
        struct sigaction action = {0};
        action.sa_handler = rc_native_on_kick;
        sigemptyset(&action.sa_mask);
        if (sigaction(SIGUSR1, &action, NULL))
            rc_native_kick_error = errno;
    }
}
#endif

long long minyar_native_region_kernel_run(const RcThreadLeaf *region, long long descriptor) {
    int saved_errno = errno;
    long long result = -ENOSYS;
    (void)rc_native_region_range(region, 1, 1, 3);
#ifdef __linux__
    if (descriptor < 0 || descriptor > INT_MAX)
        result = -EINVAL;
    else {
        int error = pthread_once(&rc_native_kick_once, rc_native_kick_install);
        if (!error)
            error = rc_native_kick_error;
        sigset_t signal, previous;
        sigemptyset(&signal);
        sigaddset(&signal, SIGUSR1);
        if (!error)
            error = pthread_sigmask(SIG_UNBLOCK, &signal, &previous);
        if (error)
            result = -(long long)error;
        else {
            rc_thread_domain_drain();
            result = ioctl((int)descriptor, 0xAE80, (void *)0) ? -(long long)errno : 0;
            error = pthread_sigmask(SIG_SETMASK, &previous, NULL);
            if (error && !result)
                result = -(long long)error;
        }
    }
#else
    (void)descriptor;
#endif
    errno = saved_errno;
    return result;
}

long long minyar_thread_kernel_kick(const RcThreadLeaf *thread, const RcThreadLeaf *region) {
    int saved_errno = errno;
    long long result = -ENOSYS;
    minyar_native_region_store_u8(region, 1, 1);
#ifdef __linux__
    int error = pthread_once(&rc_native_kick_once, rc_native_kick_install);
    if (!error)
        error = rc_native_kick_error;
    if (!error) {
        RcManagedThread *t = thread->control;
        rc_thread_control_retain(t);
        rc_thread_mutex_lock(&t->mutex);
        if (t->joined || t->finished)
            error = ESRCH;
        else if (t->joining)
            error = EBUSY;
        else
            error = pthread_kill(t->thread, SIGUSR1);
        rc_thread_mutex_unlock(&t->mutex);
        rc_thread_control_release(t);
    }
    result = -(long long)error;
#else
    (void)thread;
#endif
    errno = saved_errno;
    return result;
}

long long minyar_thread_eventfd(long long flags) {
    int saved_errno = errno;
    long long result = -ENOSYS;
#ifdef __linux__
    if (flags < 0 || flags > INT_MAX || (flags & ~(EFD_CLOEXEC | EFD_NONBLOCK | EFD_SEMAPHORE)))
        result = -EINVAL;
    else {
        result = eventfd(0, (int)flags);
        if (result < 0)
            result = -(long long)errno;
    }
#else
    (void)flags;
#endif
    errno = saved_errno;
    return result;
}
long long minyar_thread_eventfd_notify(long long descriptor, long long value) {
    int saved_errno = errno;
    long long result = -ENOSYS;
#ifdef __linux__
    if (descriptor < 0 || descriptor > INT_MAX || value < 0)
        result = -EINVAL;
    else {
        uint64_t message = (uint64_t)value;
        ssize_t written;
        rc_thread_domain_drain();
        do {
            written = write((int)descriptor, &message, sizeof(message));
        } while (written < 0 && errno == EINTR);
        result = written == (ssize_t)sizeof(message) ? 0 : written < 0 ? -(long long)errno : -EIO;
    }
#else
    (void)descriptor;
    (void)value;
#endif
    errno = saved_errno;
    return result;
}
long long minyar_thread_eventfd_read(long long descriptor) {
    int saved_errno = errno;
    long long result = -ENOSYS;
#ifdef __linux__
    if (descriptor < 0 || descriptor > INT_MAX)
        result = -EINVAL;
    else {
        uint64_t message = 0;
        ssize_t count;
        rc_thread_domain_drain();
        do {
            count = read((int)descriptor, &message, sizeof(message));
        } while (count < 0 && errno == EINTR);
        result = count != (ssize_t)sizeof(message) ? count < 0 ? -(long long)errno : -EIO
                 : message > LLONG_MAX             ? -ERANGE
                                                   : (long long)message;
    }
#else
    (void)descriptor;
#endif
    errno = saved_errno;
    return result;
}
#endif
