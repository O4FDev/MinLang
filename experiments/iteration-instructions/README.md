# Scalar sequence instruction study

Run only on the existing Linux Boat box through `bx`, after correctness checks.
The first child process is `sudo -n perf stat -e instructions:u -- true`.
An unavailable counter stops the runner with exit 77 before compilation; it
retains the raw reason and does not change kernel policy or retry another event.

Supply already built before/after compiler binaries and one shared runtime:

```sh
python3 experiments/iteration-instructions/instructions.py \
  --compiler before=./build/iteration-immediate-before/minyarc \
  --compiler after=./build/minyarc \
  --runtime build/minyar-runtime.o --scope-owners \
  --revision 'record the base commit and exact candidate source diff' \
  --output build/iteration-instructions-before-after
```

The output directory must be new. `--revision` supplies caller-recorded
provenance for synced `bx` trees, which omit `.git`; retain the exact compiler
source snapshots and diff separately. Compiler, runtime, source, library and
toolchain hashes identify the actual measured bytes.

Each process selects either the immediate named map/filter loop or its
handwritten peer. Both receive a dynamic List, and each repeated traversal is
preceded by a common mutation. An independent Python checksum validates every
invocation. Compiler and variant order alternate; the declared warmup pair is
separate, and all seven retained sample pairs remain in the report.

Counts cover the whole child process, including startup, List setup/mutation,
ownership, the selected traversal, printing and teardown. They are not isolated
loop counts or elapsed-time measurements. Inspect the saved raw/optimized LLVM
and assembly alongside the separate `iteration-study/audit-immediate.py` setup
audit. The runner accepts only positive unscaled counters reporting 100 percent
running; perf's displayed percentage has finite precision.
