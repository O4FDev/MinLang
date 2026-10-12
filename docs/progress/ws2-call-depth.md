# WS2 G14 recovery candidate — 2026-10-12

Development and owned Boat testing are authorized from `bf9c0e9`; only the
integrator merges into `v2`. Prior delegated turns were cancelled, not approved.
All dirty work, earlier failures and evidence were retained. This candidate
needs a fresh independent parent-owned review before a merge offer; no gap,
platform or performance qualification is claimed.

## Implementation

The separate recovery frontend is assembled after closure/Result adapters,
without changing ordinary compiler core or its frozen comparator. Immediate
named/indirect checkpoints run before later arguments or result projections.
Temporary registrations survive fallible evaluation, partial Lists are rooted
once, and partially built records retain their owners. Every supported
transitive language call retains a logical guard, including parallel recursion.
Entry rejection returns a typed dummy without leaves; accepted unwind pairs RC
and depth leaves. Stack v1 selection includes indirect calls in `state[14]` and
rewrites only exact RC entry/leave pieces. Checkpoints update PHI predecessors;
recovery disables integer-dispatch body replacement. The 1,500-branch ordinary
control proves that dispatch optimization is actually exercised separately.

`calldepth.run(Integer, Callback<Integer>)` validates domain before touching
scope state, counts the root callback as one frame, caps inner scopes by parent
capacity, and restores nested state. Nonpositive limits fail before callback
body execution. `remaining()` is noncounting/advisory and returns -1 outside a
scope. Existing errors factories report code 14 with reporting suspension, so
an exhausted enclosing scope does not re-trip. Code 13 remains reserved for G15.
Failure preserves already completed side effects. Ordinary fatal guards remain
unchanged. Native reserve/fallback rejection can unwind cooperatively, but
actual guard-page overflow in a large generated/native prologue and arbitrary
native faults are not covered. Native bridges must cooperate. Raw
`machine.callEntry` is rejected in recovery mode.

Public launcher request status 88 selects full flattened graph compilation,
including `--incremental`; ordinary module probes can run first but no module
artifacts are reused for the selected recovery output. Source, Make rules and
suite catalogue are committed together. `check-calldepth` and launcher tests
are wired into `check`/`check-portable`, sanitizer tests into `check-sanitize`,
and all four recovery targets into `scripts/check-linux.py`. The Linux profile
target covers O0/O2/ThinLTO, fake-stack ASan/UBSan, poll budgets, heap policies,
small stacks and the dispatch control. Portable mode uses O0/O2, platform-aware
LSan and POSIX-only pthread fixture selection; Windows/macOS full qualification
remains outstanding.

## Verification and exact evidence

Owned Boat `bx_8pvzt8f7`, `/home/user/ws2-call-depth`, was inspected before any
new work. The old stop receipt preceded a later resume; the host was live/idle.
Existing matrix job `cmd_wwr1vjixxdx7` and compatibility job
`cmd_pwtyjqorxoq6` had exited 0. All 25 saved manifests matched their source and
compiler bytes before changes; they were archived before updates. Those runs
covered all recovery cases at O0/O2/ThinLTO, ASan/UBSan fake stacks, native
256KiB stacks, domain rejection, system/fixed/lazy K1/K32/K1024, eager K32, exact
RC object/debt ledgers, pthread isolation and ordinary/closure/Result/module
fixed points. Passing unchanged work was reused.

Final detached job `cmd_xwqscwotsjwl`, PID 43555, exited 0. Its 21 recorded
checks include actual Make `check-calldepth`, `check-calldepth-sanitize` and
`check-calldepth-launcher`, plus the changed G14/code14 assertion and new
exhausted-reporting case across every heap/budget at O0/O2/ThinLTO and
ASan/UBSan. The million `nest` failure is explicitly asserted to be error 14;
then 1,000 recursion returns 1,000 and the program prints alive. The C controls
exercise fallback bounds and actual four-thread scope/reporting isolation.
Recovery, closure, Result and module Stage2/3 LLVM are byte-identical.

The first resumed launcher assertion incorrectly forbade the ordinary module
probe before feature selection. Its failure log is retained. The corrected
assertion checks no module reuse after status 88; repeated incremental builds
and a Result import before recovery both pass. Earlier missing declaration,
owner-move token and baseline failures also remain in the archives.

Final archive includes 1,343 exact source hashes and 1,739 binary/object/IR
artifact hashes, commands, stdout/stderr, source snapshots, generated runtime,
frontend Stage2/3 LLVM and representative recovery/dispatch IR. Product inputs
were checked against this worktree; the separately verified TLS test overlay is
the only source difference. Inert AppleDouble transfer sidecars are recorded
separately and were preserved. Binaries remain on the stopped owned host;
exported byte hashes identify them. Final process/history and stop receipts are
retained beside the archives. Stop `stop_317665886821a0f6` completed at
2026-10-12 15:16:53.997 UTC, with host state stopped and snapshot completed.
No other host, purchase or local security
operation was used. Small native Darwin C scope/pthread/reporting checks and a
weak LLVM symbol spelling probe passed; they are not full macOS qualification.

Archive SHA256 values:

- `prelink-evidence.tar.gz`: `127c876c698a1707f5d50949564a9fa3caa02cc8e58bb1abc3d5792051c5dbdf`
- `depth-tls-evidence.tar.gz`: `a6b24f72bf16b39594080500c71d277db24551f8288c72d49aaf92c9190a23d3`
- `before-resume-evidence.tar.gz`: `f39f39038421d4677c30d246d4b01d9381376059b496d1b8f744ae0a5aa27de8`
- `final-evidence.tar.gz`: `651869d187b69d81235773c7568d23899c54e4defcc047c23ee06264fcd53654`

## Review and composition handoff

TLS prerequisite `ab185b2` was not approved by R2 due to its MSYS test guard.
Isolated follow-up `85c2693` fixes the predicate and simulates actual decorator
selection. It has fresh exact input provenance and remains subject to parent
fresh review. See `ws2-depth-tls-r2.md`; recovery files were excluded from it.
The reviewed WS1 numeric selector is the existing dependency, not `c38057c`.

`compiler/build-calldepth-compiler.py` exports `adapt(source)` for application
AFTER the thread adapter. Factoring preserves standalone assembled SHA256
`ea917e607735370bcd4db25c8a2c1b4dc3b12c8a3ccd10bff35defe238b1652d`.
`ws2-calldepth-adapter.md` records the exact slots, labels, RC pieces and full
program marker. WS1 parent and exact compiler child were contacted directly:
a native uniform bridge must use recovery status entry, no leaves on rejected
entry, immediate pending check after target call, and matching accepted leaves.
Native callers must check pending before consuming dummy returns. Anchor
acceptance is not linked composition certification. WS1 retains bridge/native
root ownership and linked combined tests; no WS1 code was imported here.

G15 latest tip `68ebeea` was inspected; its chain also contains the frozen
baseline dependency. `library/errors.min` contains only additive G14 code 14
here. Parent must compose G15 code 13 without overwriting either branch's file.
No blind snapshot overwrite or dependency cherry-pick was done.

Outstanding: fresh full-G14 review, TLS follow-up fresh review, linked WS1 bridge
composition tests, full Windows/macOS/Linux platform gates and <=1% full
single-threaded app benchmarks, followed by integrator merge and owning gap
updates. These focused passes establish neither those qualifications nor G13.
