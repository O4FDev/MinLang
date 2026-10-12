# WS2 raw-syscall progress — 2026-10-12

This branch covers VMM-1 only; the WS2 owner tracks the other runtime work.

`machine.syscall(n, a, b, c, d, e, f): Integer` is implemented for hosted Linux
LP64 x86-64/AArch64 through one shared raw-trap helper. Both machine packages
use it. Negative kernel errno and unchanged libc errno are covered; unsupported
targets and freestanding C return -38. `machine.address` and the runtime
ABI, RC, TLS and call-depth implementation are unchanged.

The exact original repro failed on bf9c0e9 and now compiles. Linux x86-64
O0/O2 and ASan+UBSan execution passed, including a real nonzero fd and second
page offset for MAP_SHARED mmap, complete file writeback, msync and munmap.
The module/callback/Result compilers pass the same native regression. Core
and all three frontend fixed points match; the sanitized core matches too.
Native errno tests link both program and standard launcher runtimes. Both
Linux register ABIs, unsupported fallbacks and actual freestanding runtimes
have compile proof. The small native Mac Arm check covers helper fallback and
errno only.

Tests are catalogued, included in check/check-portable/check-sanitize, and
explicitly reachable from the Linux CI matrix. The frozen foundation remains
SHA-256 a5f30a7954381231fbe04a712b72bd9663d1bd7082c667fef851b739ec63c3cf.

Evidence: `/Users/luke/overnight/runs/minyar-ws2-20261012/raw-syscall/`, with
final exported receipts under `resume-20261012/`. Initial dirty files, prior
failed logs, completed pre-interruption jobs and final artifacts are preserved.
Only owned Boat bx_ysv6u258 was used; no packages or credit purchases were made.

Pending: parent fresh independent review of the committed source, then the
owner's merge request and integrator qualification. No push, merge request,
v2 merge or external gap-document update was made. Cross compilation does not
establish AArch64 runtime or native Windows execution. Full platform/application
qualification and the <=1% performance rule remain unproven by this narrow
regression. Raw syscall/address effects provide no managed-thread Send proof
or clone/fork/exit lifecycle safety; WS1's safe wrappers remain separate.
