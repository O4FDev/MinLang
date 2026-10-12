# WS4 files R1 fix

Fix commit: `ab22fb9bf9f6a097ccab32b723ae255e7a66cde1`, separate from the original `35c7378` implementation and
`6141695` evidence. Original receipts and the parent's R1 report/repros are unchanged. Worktree `ws4-files`,
branch `ws4/files`, frozen base `bf9c0e9`; no rebase, push, integration or downstream code edits.

R1's P2 was correct: total file blocks cannot establish reservation of an arbitrary prefix. Darwin now walks
`F_LOG2PHYS_EXT` extents for the requested existing prefix, without moving the shared file offset. When a range
appears unbacked, one weak `fsync` and requery distinguishes delayed allocation from a remaining hole. Remaining
holes return `-ENOTSUP` before allocation/truncation. A backed prefix can extend via `F_PREALLOCATE`, with the
requested extra length based on logical EOF. Fresh files remain supported. The write-access check also rejects
read-only nonempty reservations consistently with Linux. No whole-file `st_blocks` shortcut remains.

Primary contracts: [Apple fcntl manual](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/fcntl.2.html),
[Apple XNU fcntl implementation](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_descrip.c)
and [Apple XNU extent-query structure](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/fcntl.h).
The kernel distinguishes physical-EOF allocation from extent queries and reports an unbacked extent as device
offset -1. The weak flush is not the package's stable-storage sync promise.

Seven added mandatory controls: sparse tail, sparse middle (a hole after an initial backed extent), fresh
preallocation, 131073-byte fresh preparation, dense extension, exact-size truncation EIO, and ENOSPC after a
successful 64 KiB zero prefix. Every native managed-value entry used by files.c is guarded by the fixture's
caller-thread identity, including byte creation, append and text copy. Fault cases assert sticky completion
errors, no durable sync after the failed step, surviving prefix/tail contents and descriptor cleanup.

On this resumed APFS host, fsync materialized ftruncate's zero range in the initial sparse fixture. The maintained
Darwin controls explicitly punch the gap and verify its negative physical mapping before the API. They require
-ENOTSUP, unchanged contents/size/cursor, and no added allocation. Linux requires prefix reservation during
preallocation and no further allocation on the subsequent prefix write. No assertion or gate was relaxed.

Qualification of the exact fix sources:

- Mac: `python3 tests/files-focused.py`: 82 O0/O2 controls passed; `--sanitize`: 41 ASan/UBSan controls passed,
  including generated Minyar readiness-loop integration. Retained files-review: all 30 cases at O2 passed;
  stable-storage sync-failure fixture at O2 passed. Native sparse tail: result -45, blocks 128/128/256 across
  before/reserve/later-prefix-write; sparse middle: -45, blocks 256/256/384; size 1 MiB and cursor 123 preserved.
  Fresh reservation: blocks 128 before/after write; dense extension: blocks 24 before/after write.
- Linux: only `bx_ppv9fjr7:/home/user/ws4/files-r2/fix-r1`; eight committed source files overlaid on a copy of the
  original admitted source/build. Mode/SHA/source commit and unchanged runtime SHA checked. Baseline compiler
  SHA256 `f4f589328d1b53b8cf92c9aa8b0da1f5168bca1b4e8cf9198ff1b542cc59212b`; Clang 18.1.3.
  `python3 tests/files-focused.py`: 84 native controls passed; `--sanitize`: 42 ASan/UBSan/LSan controls passed.
  All 30 retained review cases at O0/O2/sanitize and sync-failure fixture at O0/O2/sanitize passed.
  Boat receipt `cmd_7soyjb42ojnv`, exit 0. Reproduction: `python3 /home/user/ws4/files-r2/fix-r1/qualify.py`.
- Catalogue validation and `git diff --check` passed; mandatory Make/catalogue wiring retained.

Commands, source/tool provenance, exits and original logs: `ws4-files-evidence/fix-r1/` (compressed Linux logs
include the full results manifest). Interrupted/intermediate Mac logs are labelled and are not qualification.
No local privileged/security operations, sandbox lifecycle actions, paid spend or active background jobs.

Awaiting a fresh R2 independent review. Windows backend/driver companion and Windows qualification remain
required before merge; native/sanitizer gates have not been skipped or weakened. Parent performance/crash
qualification, final v2 integration and downstream gap closure remain open.
