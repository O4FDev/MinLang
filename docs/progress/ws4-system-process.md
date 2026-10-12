# System/process track

Frozen base: bf9c0e9; no rebase, v2 merge, push or Boat provisioning by this child.

Current R2 candidate: **96051dedc6c5716819d2f0fcd5a2240ab8d1314f** fixes both
confirmed R1 P1s. All six pinned Linux qualification cases and the mandatory
kernel-layout/instrumentation boundary controls passed. Await independent R2;
Windows, privileged macOS success and native Linux aarch64 proof remain pending.

Environment/resource-limit chunk: copied getenv/environment, missing/empty distinction,
named portable resources with soft/hard setters, Windows clocks/RSS/stderr and explicit
unsupported POSIX operations. Test-first `python3 tests/system-services.py` failed on
missing APIs, then passed all four native macOS cases. Language, Linux and Windows
validation remains pending parent-owned Boat execution. No gap is marked landed in v2.

Process API implementation and privilege tests are next. macOS credential setters are
private SPI and must be dynamically discovered with exact signatures. XNU requires root
for these spawn attributes; groups setter needs a non-NULL array even for zero groups.

First implementation commit: d3f7b966937b4d5496e623d2d7cb45779e44ddbb.
Assigned Linux box bx_ppv9fjr7, namespace `/home/user/ws4/system-r2`: immutable
bf9c0e9 baseline copied with compiler SHA f4f589328d1b53b8cf92c9aa8b0da1f5168bca1b4e8cf9198ff1b542cc59212b.
`python3 tests/system-services.py --language` and `--mode sanitize` passed (exit 0).

Process regressions first failed on missing native functions, then
`python3 tests/system-process.py` passed on native macOS: argv/envp/empty env,
Unicode executable/cwd, NUL/malformed input, synchronous ENOENT, stale handles,
pending poll, child exit 127, SIGPIPE disposition AND mask, FD_CLOEXEC, and actual
macOS credential SPI privilege denial with parent credentials/mask preserved.
Those initial macOS checks did not prove privileged macOS execution or Windows.

Apple primary source design evidence:
- [SPI exact prototypes](https://github.com/apple-oss-distributions/xnu/blob/main/libsyscall/wrappers/spawn/spawn_private.h): uid/gid setters accept `const posix_spawnattr_t *`; groups adds `int`, `gid_t *`, `uid_t gmuid`.
- [Parent-side wrappers](https://github.com/apple-oss-distributions/xnu/blob/main/libsyscall/wrappers/spawn/posix_spawn.c): credential attributes allocate in the caller and validate groups including a non-NULL pointer at zero count.
- [Kernel spawn](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_exec.c): credential attributes require root; kernel applies gid, groups, then uid.
- [Group semantics](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_prot.c): zero groups installs group zero. Package prepends the requested/inherited effective gid to the supplementary list.
- [Credential model](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_credential.c): gmuid KAUTH_UID_NONE disables memberd expansion, keeping the explicit group list authoritative.

Linux shared-VM child has a guarded independent stack and only inline kernel
syscalls, with no-sanitize/no-stack-protector/no-instrument annotations. All
signals (including reserved NPTL signals) are blocked across clone. Child resets
caught dispositions before restoring its inherited mask minus SIGPIPE. Child
does not share the parent's descriptor table, cwd, or signal dispositions.

Historical author qualification: **68948fb2182baa100086d76e21a67b1cb80a58cc**.
The parent-turn interruption cancelled task ownership, so the resumed child first
verified this worktree and found no live remote qualification/fixture processes.
Earlier remote receipts were for a086d75; a fresh, separately named run qualified
68948fb without overwriting them.

All six commands below exited 0 on Linux x86_64, Clang 18.1.3, Python 3.12.3,
only in bx_ppv9fjr7 `/home/user/ws4/system-r2`:

```sh
python3 tests/system-services.py --language --prebuilt
python3 tests/system-services.py --mode sanitize --language --prebuilt
python3 tests/system-process.py --language --prebuilt
python3 tests/system-process.py --mode sanitize --language --prebuilt
python3 tests/system-process.py --root
python3 tests/system-process.py --mode sanitize --root
```

The last two compile without privilege and use `sudo -n timeout 20` only for the
bounded C fixture. The fixture asserts actual root, drops to its unprivileged
executable owner (1000:1000 on this box), verifies real/effective/saved IDs,
`setuid(0)` failure, explicit groups 777/888 and empty supplementary groups,
child SIGPIPE disposition/mask, synchronous cwd/exec errors, and unchanged parent
UID/GID/groups/mask. This avoids changing the private home directory's permissions.
Tests also cover exact argv (empty/quotes/backslashes/shell punctuation/20k bytes),
explicit Unicode/empty env, Unicode executable/cwd, stderr/stdout inheritance,
invalid IDs/NUL/malformed vectors, CLOEXEC, exit 127, poll and consumed handles.

The supplied compiler SHA f4f589328d1b53b8cf92c9aa8b0da1f5168bca1b4e8cf9198ff1b542cc59212b
and runtime object SHA effee3192380318446fa53efc9d223dfb98aa04a37bb0c236889bf1131ff306a
were checked before/after and remained unchanged. Sanitized language fixtures use
the canonical default runtime wrapper, preserving its stack-frame ABI.

Additional audit exited 0: compile system.c with ASan/UBSan, sanitizer coverage,
profile/coverage mapping and `-fstack-protector-all`, then disassemble
`system_clone_child`. Its actual x86_64 machine code contains syscalls and **zero
call instructions** in that ASan/UBSan configuration. R1 found this did not cover
TSan function-entry instrumentation or the incorrect aarch64 restorer layout.
The broader exclusion claim is superseded by the R1 correction below.

Exact source hashes/modes, commands, tool versions, exit codes and verified log
hashes: [qualification.json](ws4-system-process-evidence/final-68948fb/qualification.json).
Audit and completion receipt: [complete.json](ws4-system-process-evidence/final-68948fb/complete.json).
Historical reds remain described in [prior-findings.md](ws4-system-process-evidence/prior-findings.md).

Remaining proof: Windows backend compilation/execution awaits parent's verified
private relay to recipient bx_r5nrrwwx; no recipient/Phase1/Y VM was operated.
Privileged macOS credential success requires CI. Linux aarch64 execution also
remains uncovered. Parent supplies independent review, driver/files hunk resolution
and source-bound driver pin receipt. No merge/push/rebase or downstream gap-closure
claim was made; v2 integration is queued behind Phase1 readiness.

CI-only macOS positive credential recipe (never run on the laptop; defaults stay
unprivileged). Parent/WS7 must explicitly admit this ephemeral CI fixture:

```sh
test "${GITHUB_ACTIONS:-}" = true
test "${RUNNER_OS:-}" = macOS
test -n "${RUNNER_TEMP:-}"
clang -std=c11 -O2 -Wall -Wextra -Werror tests/system-process.c \
  -pthread -o "$RUNNER_TEMP/ws4-system-process"
shasum -a 256 "$RUNNER_TEMP/ws4-system-process"
sudo -n "$RUNNER_TEMP/ws4-system-process" root-contracts "$RUNNER_TEMP"
```

The C fixture has its own 20-second alarm and reaps every successful child.
Capture source manifest, compiler version, executable hash, command and exit code
as CI evidence. Missing SPI or privilege must fail this positive proof; no skip
or fallback to managed/fork child execution is authorized.

R1 response and source-pinned correction receipts:
[R1-response.md](ws4-system-process-evidence/r1/R1-response.md).
The kernel action now has handler/flags/restorer/mask on both supported LP64
targets, size 32 with offsets 0/8/16/24 and alignment 8. Production asserts and
mandatory freestanding target controls compare the actual declaration with
hash-pinned Linux v6.8 arm64/x86 UAPIs and the kernel's struct declaration; libc
SA_RESTORER visibility is irrelevant.

`disable_sanitizer_instrumentation` is required by compiler capability guards,
with all prior no-sanitize/coverage/profile/stack-protector/function protections
retained. A missing capability fails compilation. New full-provider x86_64
objects at O0/O1/O2 under native, ASan/UBSan and TSan all have zero child calls
and no child instrumentation/TLS references. TSan/ASan symbols elsewhere in the
same objects prove the sanitizer flags were active. Each audit additionally
enables sanitizer coverage, profile/coverage mapping, all stack protectors and
function instrumentation. This is object inspection, not TSan execution proof.

Test-first controls produced eight failures on 163224e, then zero after the fix.
The six commands listed above were rerun against exact 96051de, all exit 0,
followed by `python3 tests/system-process-boundary.py --evidence ...`, exit 0.
Compiler f4f589... and runtime effee319... remained unchanged. Original R1
report, old code, red probes, source hashes and disassemblies are preserved;
[qualification.json](ws4-system-process-evidence/r1/r1-final-96051de/qualification.json)
and [boundary receipt](ws4-system-process-evidence/r1/r1-final-96051de/boundary/receipt.json)
bind the new source, tool bytes, commands, exit codes and logs.

Driver SHA remains 6997d6e16333c855c2db4fa7d02fd02fffe897e4f69458d8bebc4feb4bd34feb;
its external QUIC pin receipt remains owner-coordinated, unchanged by this fix.
