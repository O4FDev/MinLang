# Resuming the parked run-2 lanes

Stopped 2026-11-01 09:55 UTC when the shared OpenRouter key hit its $30 lifetime limit (account credit remained). Each lane
can resume as a fresh Wafer session (reasoning effort `high` for compiler/runtime work) from its report in
~/Projects/minyar-goal-20261030/reports/run2/<lane>.md plus the notes below. Rules for resumed lanes are in
~/Projects/minyar-goal-20261030/briefs/run2-swarm.md (no full gates in lanes, WAITING on long waits, remote logs live on the box,
base copies via `git worktree add --detach`). The goal-run2 build boxes are gone: a resumed lane needs a new box or the fast gate.

Restoring saved work: `git -C <worktree> stash apply refs/wip/<lane>` for uncommitted edits; `tar -xzf logs/wip/<lane>-untracked.tgz -C <worktree>` for new files.

| lane | branch head | last READY | preserved | state / next step |
|---|---|---|---|---|
| esc | d7344853d perf(runtime): retire a header-backed List buffer  (4 commits past goal tip) | **READY FOR GATE: (none yet — d7b7be9c7 is the candidate; set after th |   | see below |
| rgv | 298e30f7c perf(loops): version while loops that accumulate f (4 commits past goal tip) | READY FOR GATE: afbe68aad | refs/wip/rgv 4e964dab5  | see below |
| map2 | ef81b33c5 perf(maps): end a long Text key's hash in a serial (4 commits past goal tip) | none |   | see below |
| big | 994f9bc3e perf(loops): cover checked counter and step arithm (0 commits past goal tip) | none | refs/wip/big 63f3b1ab4 + untracked tgz | see below |
| simd | a38e31def docs(text): the split scan tests sixteen bytes at  (0 commits past goal tip) | none | refs/wip/simd f021f6c08 + untracked tgz | see below |
| fbip | 97c5580f5 perf(runtime): reuse a dead List's slot buffer for (4 commits past goal tip) | READY FOR GATE: 97c5580f5 |   | see below |
| brw5 | 1fa396a48 perf(runtime): keep the inlined drop body one stra (0 commits past goal tip) | none |   | see below |

- **esc**: inline List slots (b13fb94ea…, d7344853d); was fixing service +0.66%, mapreduce@1 +0.22%, topk@1 +0.16% and rebasing on goal; next step in reports/run2/esc.md line 122. fbip's buffer-reuse cache (97c5580f5) waits on esc's final commit.
- **rgv**: steered to cover the hidden stencil shape (bound = local copied from a length; per-iteration expression stored to another List); uncommitted edits in loop-versioning.min/assignment.min saved as refs/wip/rgv.
- **map2**: Text-key hash + Map growth; committed work up to ef81b33c5 (no READY yet; check reports/run2/map2.md and measure before trusting).
- **big**: runtime mmap/mremap for buffers ≥ 512 KiB (new runtime/minyar_big_buffer.h in the untracked tgz + edits in refs/wip/big); goal: res3 kernels give identical Ir with and without MALLOC_MMAP_THRESHOLD_, then re-score candidate/r2s on top.
- **simd**: PAR-6 `simd` module (library/simd.min, compiler/simd-compiler.min, runtime/minyar_simd.h, tests incl. ChaCha20, docs/simd.md: all untracked in the tgz) + compiler edits in refs/wip/simd; no READY yet.
- **brw5**: died 3 min in; nothing to keep (worktree at goal tip). Restart from the brw5 task in this conversation's last dispatch (last-use argument moves into callees).
- **res2/r2s**: candidate/r2s waits on big (b05 +0.18% is the glibc mmap-threshold effect).

Older lanes removed from the laptop on 2026-11-01 (all merged or abandoned; branches kept): scratch files in
~/Projects/minyar-goal-20261030/logs/wt-archive/*.tgz, uncommitted edits in refs/wip/wt-ownership2-exp, wt-ownership2-par, wt-ownership3-d1.

Held candidates that a resumed lane would unblock:
- `candidate/r2s` (res2 eager retirement: 12 hidden programs faster, b05 +0.18% from glibc's adaptive mmap threshold) waits on lane **big** (runtime mmap/mremap for buffers >= 512 KiB).
- fbip 97c5580f5 (dead-List buffer reuse: service -2.4%, logstats -2.1%) waits on lane **esc** (inline List slots) reaching READY.
- **rgv** (merged for List walks) has uncommitted work toward the hidden stencil shape (bound copied from a length, per-iteration expression stored to another List).
- **simd** (gap PAR-6) has an uncommitted `simd` module with ChaCha20 and dot-product tests.
