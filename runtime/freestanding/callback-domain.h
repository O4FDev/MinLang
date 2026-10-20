/* The bare runtime has one global RC/allocator/frame state and no TLS setup.
 * Its managed callbacks belong to the first physical CPU that uses them.
 * Every domain check verifies that CPU before entering managed callback code.
 * This profile does not support migration, managed AP work, hotplug, or calls
 * from interrupt/NMI context. A scheduler needs its own complete heap domain. */
#ifndef MINYAR_FREESTANDING_CALLBACK_DOMAIN_H
#define MINYAR_FREESTANDING_CALLBACK_DOMAIN_H

#if MINYAR_THREADED
#error Freestanding callbacks require the single execution domain profile.
#endif

static atomic_uint_fast64_t minyar_freestanding_callback_owner;

static long long minyar_freestanding_callback_domain(uint64_t cpu) {
    if (cpu > UINT32_MAX)
        minyar_stop("freestanding callback CPU identity is invalid.");
    uint64_t domain = cpu + 1;
    uint_fast64_t expected = 0;
    if (!atomic_compare_exchange_strong_explicit(&minyar_freestanding_callback_owner,
            &expected, domain, memory_order_relaxed, memory_order_relaxed) &&
        expected != domain)
        minyar_stop("freestanding callbacks require their original CPU.");
    return (long long)domain;
}

static uint64_t minyar_freestanding_callback_cpu(void) {
#if defined(__x86_64__)
    unsigned maximum, a, b, c, d;
    __asm__ volatile("cpuid" : "=a"(maximum), "=b"(b), "=c"(c), "=d"(d)
                     : "a"(0), "c"(0));
    /* Extended topology reports the full x2APIC ID, including on xAPIC CPUs.
     * Prefer the v2 topology leaf, then the original extended topology leaf. */
    const unsigned leaves[] = {0x1f, 0xb};
    for (unsigned index = 0; index < 2; index++) {
        if (maximum < leaves[index]) continue;
        __asm__ volatile("cpuid" : "=a"(a), "=b"(b), "=c"(c), "=d"(d)
                         : "a"(leaves[index]), "c"(0));
        if (b && ((c >> 8) & 255)) return d;
    }
    __asm__ volatile("cpuid" : "=a"(a), "=b"(b), "=c"(c), "=d"(d)
                     : "a"(1), "c"(0));
    if (!(d & (1u << 9)))
        minyar_stop("freestanding callbacks require a CPU identity provider.");
    unsigned apic_id = b >> 24;
    /* The legacy 8-bit ID is unique only in xAPIC mode. Refuse a truncated
     * x2APIC identity when the machine supplies no usable topology leaf. */
    __asm__ volatile("rdmsr" : "=a"(a), "=d"(d) : "c"(0x1b));
    if (a & (1u << 10))
        minyar_stop("freestanding callbacks require full x2APIC topology.");
    return apic_id;
#elif defined(__aarch64__)
    uint64_t mpidr;
    __asm__ volatile("mrs %0, mpidr_el1" : "=r"(mpidr));
    return (mpidr & UINT64_C(0xffffff)) | ((mpidr >> 8) & UINT64_C(0xff000000));
#else
#error Freestanding callbacks need an architecture CPU identity provider.
#endif
}

#endif
