# WS2 VMM-1 handoff — 2026-10-12

Nothing from this chunk has landed on v2. `ws2/raw-syscall` is based on
e4f1709996bb7513d8e8eb005406fcfbe8858fa4, including approved frozen-foundation
commits 7b63db6, 9f036e5 and e4f1709. The final implementation SHA is recorded
in the external `resume-20261012/receipt.json` and the owner's handoff.

VMM-1 now has a compiler intrinsic, shared hosted Linux LP64 raw syscall
helper, both machine APIs, explicit -38 fallback and unsafe-effect documentation.
The original fixture is byte-pinned. The native regression replaces its KVM
device dependency with regular-file ioctl ENOTTY; it separately proves all
six arguments using nonzero-fd/nonzero-offset shared mmap and writeback.

Passed gates: `check-foundation-baseline`, `check-suite-catalogue`,
`check-raw-syscall-linux-native`, `check-raw-syscall-sanitize`,
`check-raw-syscall-abi`, and `check-raw-syscall-frontends`. Ordinary core,
module, callback and Result stage2/stage3 LLVM are byte-identical; sanitized
core LLVM matches. Exact commands, source/tool/artifact hashes, binaries,
LLVM, file oracles and prior evidence are retained outside the repository.

The parent must independently review the committed change before offering it
for merge. When combining the additive include after `<math.h>` with WS1,
retain WS1's thread-config include; it is absent from this branch's baseline.
No ABI/RC/TLS/depth policy is changed here. No general threaded syscall safety,
AArch64 kernel execution, Windows native run, privileged KVM proof, full
platform/application gap closure or <=1% performance qualification is claimed.
