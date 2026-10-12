# R1 response for independent R2

Original brief: portable system environment/getenv (ADAPTER-1), signals G5,
stderr G9, get/set soft/hard rlimits G10, and safe explicit path/argv/envp/cwd/
uid/gid/supplementary-groups spawn with owned wait/poll handles. Normal launches
use posix_spawn; Linux credential launches use own-stack clone-vfork with only
native raw syscalls in the shared-VM child, no TLS errno/libc setxid/managed code.
Reset and unblock child SIGPIPE while preserving parent state. Windows requires
truthful portable implementations/unsupported errno contracts. Frozen bf9c0e9;
no v2 integration, push, rebase, downstream edits or nested agents.
Validate NUL, explicit argv/envp and empty environments, Unicode paths, invalid
IDs, synchronous launch errno, cwd isolation, CLOEXEC and lifecycle. Keep parent
signal state unchanged, and do not execute Minyar or allocate managed memory
before the child has completed exec.

Independent [R1 report](review-system-r1.md) requested changes on 163224e:

1. **Arm64 kernel ABI:** accepted. Old declaration omitted restorer on aarch64
   and was 24 bytes with mask at 16. Fix 96051de makes restorer unconditional for
   supported Linux x86_64/aarch64 LP64, size 32/mask 24, with production size,
   offset and alignment assertions. Mandatory target-specific compile controls
   use the exact production declaration and compare it to pinned primary kernel
   declarations. Both target controls pass. No libc SA_RESTORER dependence.
2. **TSan child call:** accepted. Old no_sanitize(thread) permitted
   __tsan_func_entry. Fix requires capability-guarded complete
   disable_sanitizer_instrumentation and retains all prior exclusions. Full
   native x86_64 objects under native/ASan-UBSan/TSan at O0/O1/O2 each have zero
   child call instructions and no instrumentation/TLS references with coverage,
   profile, stack-protector and function instrumentation enabled. Sanitizer
   symbols outside the child are positive controls. Missing capability is a
   mandatory compile failure; it is never silently accepted.

Test-first [red receipt](r1-author-red/receipt.json): arm64 ABI failure, TSan
calls/references at all three optimization levels, and missing fail-closed guard
(eight failures). Old code is [system_process-before.h](system_process-before.h).
Original reviewer logs and source/receipt audits remain alongside this response.

Exact committed fix source: 96051dedc6c5716819d2f0fcd5a2240ab8d1314f.
Own Boat only: bx_ppv9fjr7 `/home/user/ws4/system-r2`, unprivileged compiler/Python.
Six native/SAN/language and root C cases all exited 0; root is ONLY the explicitly
authorized `sudo -n timeout 20` C fixture. It still proves actual root, drop to
owner 1000:1000, saved-ID removal, failed regain of root, groups 777/888 and empty
groups, child SIGPIPE/default/unblock and unchanged parent credentials/mask.
Pinned compiler f4f589... and runtime effee319... stayed identical before/after.
[Final qualification](r1-final-96051de/qualification.json),
[mandatory boundary controls](r1-final-96051de/boundary/receipt.json).

Remaining acceptance: native aarch64 execution and whole-provider aarch64
instrumentation inspection, all Windows compilation/execution, privileged
macOS positive credential success (CI only, never laptop sudo), shared ≤1%
performance checks and integration. Existing unprivileged macOS SPI results
and source review do not substitute for privileged CI proof. No broad skip.
Driver hash 6997d6e... and external QUIC pins are unchanged and remain subject
to the owner's coordinated final receipt. No hosts/lifecycle/security settings
were modified; own qualification jobs are idle. Parent must delegate a fresh R2
with this original brief, R1 report, response and unresolved platform objections.
