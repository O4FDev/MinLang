# Raw Linux syscalls

`machine.syscall(n, a, b, c, d, e, f): Integer` passes a syscall number and
six Integer arguments to the **target** kernel ABI. Hosted Linux LP64 x86-64
uses rax/rdi/rsi/rdx/r10/r8/r9 and `syscall`; AArch64 uses x8/x0..x5 and `svc #0`.
It returns the signed kernel result, including negative errno, and leaves
libc `errno` unchanged. Values in [-4095, -1] are Linux syscall errors. The
machine and arch/arm64 machine packages share the same runtime helper; no
arbitrary native package shim or compiler-driver C object is required.

Unsupported operating systems, architectures (including x32), and
freestanding C runtimes return the fixed value **-38**. The helper makes no
syscall there. Syscall numbers, structure layout, flags and pointer alignment
are the caller's target-specific responsibility. For example, Linux x86-64
getpid is `machine.syscall(39, 0, 0, 0, 0, 0, 0)`; on AArch64 its number is 172.

This primitive has unsafe OS and memory effects. `machine.address(bytes)` is
the first buffer pointer; keep the Bytes owner alive, without growing,
clearing or releasing it while a kernel operation uses the pointer. A saved
Integer pointer does not retain its owner, validate its range, or establish
safe transport between managed threads. Kernel operations that retain a
pointer after returning require the owner to survive that whole interval.
A syscall can also mutate arbitrary accessible memory or descriptors.

`clone`, `fork`, `exit` and related calls can bypass runtime lifecycle,
collector and thread invariants. No safety guarantee is made for them.
Arbitrary `ioctl` and `futex` likewise have unsafe effects. WS1's independently
checked safe wrappers/whitelist (getpid, sleep, fsync, KVM_RUN with zero pointer
argument) are separate from this raw primitive. Threaded admission must track
raw syscall and address effects transitively, including pre-saved Integer
pointers; this intrinsic does not provide that admission mechanism.

`make check-raw-syscall` runs the native regression or hosted fallback.
`check-raw-syscall-linux-native` requires actual Linux x86-64/AArch64 execution;
`check-raw-syscall-sanitize` instruments compiler, generated LLVM and runtime;
`check-raw-syscall-frontends` exercises current module/callback/Result frontends.
`check-raw-syscall-abi` checks both Linux register ABIs, unsupported-target
fallbacks, and the actual freestanding runtime compilation. Cross assembly
is compile evidence only and does not certify execution on an Arm kernel.

The exact neo-vm VMM-1 repro is retained as `vmm-1-original.min` and compiled,
while `linux.min` converts its device dependency to a temporary regular-file
KVM ioctl with expected ENOTTY. The Python oracle checks child getpid,
ENOSYS/ENOENT/EBADF/EFAULT, Bytes read/write and live-owner loads/stores. Its
six-argument mmap uses a **real nonzero fd and nonzero page-aligned offset**,
MAP_SHARED, distinct first/second pages, complete file-content writeback,
msync and munmap. Anonymous or zero-offset mmap is not the argument-six proof.
The native errno checks link both the program runtime and the exact standard
launcher runtime. O0/O2 artifacts, exact input/tool/binary hashes and command
results are saved under separate `build/raw-syscall` directories for native,
sanitizer, ABI and frontend modes; `--output` selects an evidence directory.
