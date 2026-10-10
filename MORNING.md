# Good morning: Minyar v2 (overnight, 2026-10-10)

## TL;DR
- Every branch and worktree is reconciled into **`v2`, pushed to origin and green** on check-portable, modules, http, tls, macos, ownership, peer-semantics and peer-sanitize. Every dirty worktree was snapshotted to its own branch first, so nothing was lost.
- Profiling the real programs produced six measured fixes. Atacama's History search uses **10.5x fewer instructions**. Streaming uses **4.2x fewer**. Minyarcraft's world build uses **1.86x fewer**. Multi-module compiles are **28-35% cheaper**, and appending to a Text field is now linear. There is now one `http` package.
- You can use it today: `cd ~/Projects/Atacama-desktop-app && make` builds against `../Minyar-Lang-v2`. Two decisions are waiting for you: whether to merge the Astra cycle collector, and the Atacama repo (see Decisions).

## What was built or fixed

All numbers are retired instructions of the process (`/usr/bin/time -l` or `proc_pid_rusage`), measured against the pushed v2 base `b8e0ca1`. Full evidence, profiles and tests are in `docs/v2-performance.md`.

| # | Problem found by profiling | Fix | Before | After |
| --- | --- | --- | ---: | ---: |
| 1 | Atacama History rebuilt a stack of views per row on every keystroke (Auto Layout solver, superlinear) | `macos.list`: a virtualized NSTableView (`list`, `addRow`, `listLine`, `rowButton`, `clickedRow`, ...) | 110G, 11.1 s CPU | 10.5G, 1.7 s CPU |
| 2 | Each streamed network chunk re-laid out the whole answer | `nextEvent` wakes for background work at most 60 times a second | 58.6G, 7.0 s CPU | 14.0G, 2.1 s CPU |
| 3 | Every function called the runtime's call-depth guard, so tiny accessors never inlined | Leaf functions (no user calls, small frame) carry no call-depth frame | Minyarcraft 32.1G | 25.6G |
| 4 | `record.field[i] = v` borrowed the field on every store | No borrow when the rest of the statement makes no call | Minyarcraft 25.6G | 17.3G |
| 5 | `record.text = record.text + piece` copied the whole Text every time (quadratic) | In-place append when the record holds the only other reference | 80,000 appends 4.11G | 79.8M |
| 6 | 27% of a multi-module compile was spent comparing symbol names | Symbol tables ordered by length, then from the last character | OS kernel 485M, Minyarcraft 109M, Atacama 80.5M | 342M, 71.4M, 58.1M |
| 7 | `json.parse` built every string from a parts list, a slice and a join | One slice when a string has no escapes | 20 parses of Atacama's 143 KB history response: 1.22G | 0.95G |
| 8 | Every macOS app build recompiled the Objective-C bridges (0.6 s) | Content-keyed object cache for every native bridge (it already existed for `graphics.c`) | Atacama default build 0.93-1.11 s | 0.48 s |
| 9 | Minyarcraft's GPU vertex buffers dominated its memory (40-byte float vertices, 6 per quad) | 32-byte vertices (hardware Float16 colour and light) plus `graphics.updateQuads` (4 per quad, shared indices) | peak RSS 602 MB, footprint 892 MB, 17.30G instr | 419 MB, 697-725 MB, 16.44G |
| 10 | Two competing `http` packages | One package: portable sockets/TLS backend plus an NSURLSession backend on macOS, chosen by search path; `./minyar --library DIR` | 2 packages | 1 |

Measured and not bottlenecks:
- Atacama start-up: 2.04G instructions, 0.31 s CPU, dominated by AppKit.
- Typing: about 2 ms per key; the main thread is idle 95% of the time.
- After a one-line change, the front end takes 0.02 s; the rest of the build time is clang.

Also verified:
- Minyar-OS boots in QEMU from v2. On the base it reached the desktop in 632 ms; after the merge, see "Minyar-OS on v2" below.
- Minyarcraft builds and renders.
- Atacama builds and `make test` passes against v2.

Screenshots are in `docs/v2-evidence/`: Atacama History before and after, Atacama streaming, Minyarcraft, and the Minyar-OS desktop.

How it was measured:
- `Atacama-desktop-app/tests/profile/` is a stub Atacama server plus an accessibility driver. The driver runs the real app: it opens History, types a search into 500 runs, and streams a 3,000-delta answer.
- Minyarcraft was measured with `craft --screenshot`.
- Profiles came from `sample` and `xctrace` (Time Profiler, all processes).

## Decisions for you

1. **Merge the Astra cycle collector (`port/astra-cycles`) into v2?** It lifts the rule that rejects programs which could form reference cycles, and collects cycles within a bounded amount of work.
   - It won the bake-off. Overnight it was ported onto v2, made cheaper in three rounds, and brought up to date with all of tonight's work. Its targeted tests and sanitizer profiles pass.
   - Cost on real programs: Minyarcraft +0.06% and compiler self-compile +1.0%. Atacama streaming is within noise.
   - `json.Value` can form a cycle, so **JSON parsing is +29% instructions and +10% memory** (1.22G → 1.57G on the history benchmark).
   - Self-referential types in general cost +13% instructions and up to +50% memory.
   - The brief says not to land regressions, so I did not merge it.
   - The branch predates tonight's fix to the store-borrow scan, so merge current v2 into it first.
   - **Recommendation:** merge it only if cyclic data matters to you now. A cheap middle path is to mark `json.Value` as never cyclic (it is built bottom-up and never mutated into a cycle), which would remove the JSON cost. That needs a language-level "acyclic" annotation, so it is your call.
2. **Atacama is now a git repository.** It wasn't one; per the overnight rules I ran `git init` and committed a snapshot before touching it.
   - The changes are on branch `v2-list`.
   - Its Makefile now defaults to `../Minyar-Lang-v2`.
   - **Recommendation:** keep the repo and merge `v2-list`.
3. **About 600 MB of research data is committed in v2 (`research/`, `evidence/`).** It was already on origin through `integrate/desktop-tests-minecraft`.
   - **Recommendation:** move it to Git LFS or a separate repository next week; it slows clones.
4. **Old branches can go.** `fix/ci-*`, `codex/ci-runner-portability`, `research/bounded-reclamation`, the `t3code/*` branches and `feat/desktop-canvas` are all contained in v2. `docs/v2-reconciliation.md` has the evidence. I did not delete anything.

## What I tried that didn't work

- **Joining the compiler's output once instead of twice.** The output was byte-identical, but there was no measurable gain (the compiler's arena dominates memory), so I reverted it.
- **`sample` on Minyarcraft runs shorter than about 3 s.** It produced empty call graphs. `xctrace record --all-processes` worked instead.
- **Bugs I introduced, and how they were caught (none reached origin):**
  - **Ownership slot collision.** The clean-up after code review put a new compiler-state slot where the ownership-slot map lives, so a binding got slot -1. `check-modules` caught it: `private-fields` crashed about 30% of the time. Fixed, with a deterministic case in `tests/regressions.py`.
  - **Use-after-free in the store-borrow elision.** An 8-agent review workflow (4 reviewers, each checked by a skeptic) found that the call scan stopped at line ends inside a multi-line record literal, and at `;` inside brackets. A call could then replace the List being stored into. I reproduced both under ASan, made the scan track all brackets, and added FileCheck contracts that fail on the earlier compilers.
  - **The append rewrite matched a string literal `"+"` as the operator.** It now checks token kinds.
  - **CI breaks:** `tests/toolchain-portability.py` used the old `graphics()` signature, and `--app` packaging picked Homebrew's Python, whose `plistlib` is broken. Both fixed.
  - The review also corrected about a dozen documentation claims.
- **`make check-budget` (the compiler self-compile budget) still fails.** It was already failing before tonight. It is now at 80.7M instructions against a 75M limit, down from about 91M. Peak memory is 10.8 MiB against a 10 MiB limit.
- **Streaming in Atacama didn't get faster from fix 5.** Its answers are only about 25 KB; the gain shows up on longer texts.

## Next 10, ranked


1. Decide on Astra (above); if merging, rerun `check-cycles` and `check-cycle-profiles` on v2.
2. Get `check-budget` green: about 6M more instructions and 0.8 MiB to cut from the self-compile (`minyar_join_texts` 14%, dyld start-up about 20%).
3. Streaming answers: an incremental text view for long Atacama answers. After throttling, the remaining cost is NSTextField re-measuring the whole label.
4. Generalise the in-place field append to any target path (`a.b.c = a.b.c + x`, `xs[i] = xs[i] + t`), using the destination-hint protocol that locals already use.
5. Replace the token scan behind indexed-store borrow elision with the same user-call counter that leaf detection now uses.
6. A portable streaming `http` backend. This needs a `Request` record, because packages can't hold state.
7. Run the Minyar-OS frame profiler under KVM/HVF instead of TCG, for stable frame budgets.
8. Profile Minyarcraft's steady-state frames (meshing on block edits) now that start-up is 1.86x cheaper.
9. Move `research/` and `evidence/` out of the main repository.
10. Delete the superseded branches listed in `docs/v2-reconciliation.md`.

## How to run and verify

```sh
cd ~/Projects/Minyar-Lang-v2          # branch v2 (also on origin)
make all                               # bootstrap the compiler
make check-portable                    # about 25 min on a quiet machine
make check-ownership check-peer-semantics check-peer-sanitize
make check-modules check-http check-tls check-macos
MINYAR_LLVM_BIN=/opt/homebrew/opt/llvm/bin make check-codegen

# Desktop list benchmark (rebuild time per row count)
./minyar --release benchmarks/desktop/history-rows.min -o build/history-rows && build/history-rows 800
./minyar --release benchmarks/desktop/history-list.min -o build/history-list && build/history-list 800

# Minyarcraft world build (retired instructions)
./minyar --release examples/craft/main.min -o build/craft
/usr/bin/time -l build/craft --screenshot /tmp/craft.png noon

# Atacama against v2, and the profiling driver
cd ~/Projects/Atacama-desktop-app && git switch v2-list && make && make test
python3 tests/profile/stub-server.py 47391 500 3000 &
clang -fobjc-arc -fmodules tests/profile/drive.m -o build/drive
build/drive build/Atacama.app/Contents/MacOS/application 47391 history
build/drive build/Atacama.app/Contents/MacOS/application 47391 stream

# Minyar-OS
make -C os && python3 os/tools/qemu-drive.py <(echo '[["wait", 20], ["shot", "desktop"]]')
```
