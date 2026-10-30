#ifndef MINYAR_THREAD_ATOMICS_H
#define MINYAR_THREAD_ATOMICS_H
/* Managed threading fragment, included only by MINYAR_THREADED == 1.
 *
 * AtomicInteger and AtomicBoolean are shared cells: a native control with an
 * atomic count of handles, plus one 64-bit word. Each thread holds its own
 * local leaf; generated code loads the control from the leaf and performs
 * loads, stores, read-modify-writes and compare-exchanges inline with the
 * requested LLVM ordering at byte offset 16. Only blocking waits and wakes
 * call into this file. */
#include <stdatomic.h>
#include <stddef.h>
#if defined(__linux__)
#include <linux/futex.h>
#include <sys/syscall.h>
#include <unistd.h>
#include <errno.h>
#elif defined(__APPLE__)
#include <errno.h>
/* The compare-and-wait primitive libc++ uses for std::atomic::wait. */
extern int __ulock_wait(uint32_t operation, void *address, uint64_t value, uint32_t timeout_microseconds);
extern int __ulock_wake(uint32_t operation, void *address, uint64_t wake_value);
#define MINYAR_UL_COMPARE_AND_WAIT64 5
#define MINYAR_ULF_WAKE_ALL 0x00000100
#endif

typedef struct {
    RcThreadControl owner;
    _Atomic long long value;
    /* Pad each cell to a cache line, so unrelated hot cells do not share one. */
    char padding[64 - sizeof(RcThreadControl) - sizeof(long long)];
} RcAtomicCell;
_Static_assert(offsetof(RcAtomicCell, value) == 16, "generated atomic operations address the value at offset 16");

static void rc_atomic_destroy(void *pointer) {
    rc_thread_native_free(pointer, sizeof(RcAtomicCell));
}

void *minyar_atomic_new(long long initial) {
    RcAtomicCell *cell = rc_thread_native_allocate(sizeof(*cell));
    memset(cell, 0, sizeof(*cell));
    atomic_init(&cell->value, initial);
    rc_thread_control_init(&cell->owner, 1, rc_atomic_destroy);
    return rc_thread_wrap(cell);
}

/* Blocks while the cell holds `expected`, at most `milliseconds` (negative:
 * no limit). True once the value differs; false at the deadline. Wakes may be
 * spurious inside; the loop re-checks the value before returning. */
_Bool minyar_atomic_wait(const RcThreadLeaf *leaf, long long expected, long long milliseconds) {
    RcAtomicCell *cell = leaf->control;
    long long deadline = milliseconds < 0 ? -1 : rc_queue_now() + (milliseconds > LLONG_MAX / 2000000LL ? LLONG_MAX / 2 : milliseconds * 1000000LL);
    rc_thread_domain_drain();
    for (;;) {
        if (atomic_load_explicit(&cell->value, memory_order_acquire) != expected) return 1;
        long long left = -1;
        if (deadline >= 0) {
            left = deadline - rc_queue_now();
            if (left <= 0) return atomic_load_explicit(&cell->value, memory_order_acquire) != expected;
        }
#if defined(__linux__)
        /* The futex word is the low half of the little-endian cell. Every
         * notify wakes it, and the loop compares the whole 64-bit value. */
        struct timespec timeout = { (time_t)(left / 1000000000LL), (long)(left % 1000000000LL) };
        syscall(SYS_futex, (uint32_t *)(void *)&cell->value, FUTEX_WAIT_PRIVATE, (uint32_t)expected,
                left < 0 ? NULL : &timeout, NULL, 0);
#elif defined(__APPLE__)
        uint32_t micros = 0;
        if (left >= 0) micros = left / 1000 > UINT32_MAX - 1 ? UINT32_MAX - 1 : (uint32_t)(left / 1000) + 1;
        __ulock_wait(MINYAR_UL_COMPARE_AND_WAIT64, (void *)&cell->value, (uint64_t)expected, micros);
#elif defined(_WIN32)
        WaitOnAddress((volatile void *)&cell->value, &expected, sizeof(expected),
                      left < 0 ? INFINITE : (DWORD)(left / 1000000 + 1));
#else
        struct timespec pause = {0, 50000};
        nanosleep(&pause, NULL);
#endif
    }
}

void minyar_atomic_notify(const RcThreadLeaf *leaf, _Bool all) {
    RcAtomicCell *cell = leaf->control;
#if defined(__linux__)
    syscall(SYS_futex, (uint32_t *)(void *)&cell->value, FUTEX_WAKE_PRIVATE, all ? INT_MAX : 1, NULL, NULL, 0);
#elif defined(__APPLE__)
    __ulock_wake(MINYAR_UL_COMPARE_AND_WAIT64 | (all ? MINYAR_ULF_WAKE_ALL : 0), (void *)&cell->value, 0);
#elif defined(_WIN32)
    if (all) WakeByAddressAll((void *)&cell->value); else WakeByAddressSingle((void *)&cell->value);
#else
    (void)cell; (void)all;
#endif
}

#endif
