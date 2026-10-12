#ifndef MINYAR_MACHINE_H
#define MINYAR_MACHINE_H

/* Raw Linux LP64 syscall ABI. This deliberately bypasses libc: the result is
 * the kernel's signed value (including negative errno), and libc errno is
 * untouched. Integer arguments may contain borrowed pointers; the caller
 * owns their validity and lifetime. No runtime/collector state is accessed.
 * Bare-metal builds must never issue a hosted Linux syscall. */
long long minyar_machine_syscall(long long n, long long a, long long b, long long c,
                               long long d, long long e, long long f) {
#if defined(__linux__) && defined(__LP64__) && defined(__STDC_HOSTED__) && __STDC_HOSTED__ == 1 && defined(__x86_64__)
    register long long r10 __asm__("r10") = d;
    register long long r8 __asm__("r8") = e;
    register long long r9 __asm__("r9") = f;
    long long result = n;
    __asm__ volatile("syscall"
                     : "+a"(result)
                     : "D"(a), "S"(b), "d"(c), "r"(r10), "r"(r8), "r"(r9)
                     : "rcx", "r11", "memory", "cc");
    return result;
#elif defined(__linux__) && defined(__LP64__) && defined(__STDC_HOSTED__) && __STDC_HOSTED__ == 1 && defined(__aarch64__)
    register long long x8 __asm__("x8") = n;
    register long long x0 __asm__("x0") = a;
    register long long x1 __asm__("x1") = b;
    register long long x2 __asm__("x2") = c;
    register long long x3 __asm__("x3") = d;
    register long long x4 __asm__("x4") = e;
    register long long x5 __asm__("x5") = f;
    __asm__ volatile("svc #0"
                     : "+r"(x0)
                     : "r"(x8), "r"(x1), "r"(x2), "r"(x3), "r"(x4), "r"(x5)
                     : "memory", "cc");
    return x0;
#else
    (void)n; (void)a; (void)b; (void)c; (void)d; (void)e; (void)f;
    return -38; /* Fixed ENOSYS fallback, independent of host errno numbering. */
#endif
}

#endif
