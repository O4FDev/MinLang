# Overnight runs

An overnight run is several agent lanes working on their own branches at once.
A merge train lands their work on `v2` through one shared gate. The tools are
in `tools/run/`. They use only `sh` and the Python 3 standard library, plus
OrbStack for the gate VM.

## Start a run

```sh
sh tools/run/start.sh ~/Projects/minyar-run-YYYYMMDD "one sentence goal."
```

This creates the run directory with:

- `CHARTER.md`, filled in from `tools/run/charter-template.md`. Add the end
  time and landing deadlines.
- `env`, which holds the run settings.
- `queue/`, `locks/`, `logs/`, `reports/` and `gate/` (gate logs).
- `train/`, a worktree of the run branch.
- `LANDED`, the record of every landing.
- The wrappers lanes call as `$C/heavy`, `$C/light`, `$C/land.sh` and
  `$C/tick.sh`.

Then start the base gate and the train, using the two commands `start.sh`
prints:

```sh
python3 tools/run/train.py RUN_DIR --base   # gate the base once: base.fail, base.ready
nohup python3 tools/run/train.py RUN_DIR > RUN_DIR/logs/train.out 2>&1 &
```

The gate VM (`MINYAR_GATE_VM`, default `rpcgate`) is an OrbStack Linux
machine that can read the run directory's path. `vmgate.sh` clones the repo
into it on first use and keeps one warm tree, `~/gate-run`. Settings live in
the environment that `start.sh` records:

- `MINYAR_RUN_BRANCH` (default `v2`).
- `MINYAR_HEAVY_SLOTS` and `MINYAR_LIGHT_SLOTS` (default 3 each).
- For a macOS whose newest SDK breaks local links: `MINYAR_RUN_SDKROOT`,
  `MINYAR_RUN_MACOSX_DEPLOYMENT_TARGET` and `MINYAR_RUN_LINK_PARTITIONS`.

## The tools

- `heavy CMD`: runs CMD in one of the shared build slots, first come, first
  served.
- `light CMD`: its own queue for commands that finish in under 90 s on one
  core. The command is killed at 120 s.
- `land.sh LANE`: queues the lane's branch head and waits for the train's
  verdict.
- `train.py`: stacks every queued lane on the branch and runs one gate. On
  green it fast-forwards and pushes. On red it reruns only the failing checks
  on each lane alone to find the culprit, then gates the innocent lanes
  together again. If no lane fails alone, it splits the stack. A gate log
  counts only if its first line names the commit under test. Checks in
  `base.fail` are not held against anyone.
- `tick.sh`: one screen of run state for the orchestrator.

## Lessons from the 2026-11-09 run

The figures are from that run's `logs/train.log`, `LANDED` and lane reports.
There were 9 lanes on a 10-core, 16 GB laptop, with one local arm64 Linux
gate VM.

- **A full gate took 14 to 17 minutes.** Between 00:29 and 05:15 the train
  ran 28 full gates and 15 re-runs of only the failing checks. 16 lane
  landings reached `v2` in 9 fast-forwards; the last stack carried 6 lanes.
- **Re-gating each lane in full after a red stack costs one full gate per
  lane.** This happened four times: at 00:58, 01:56 and 02:41, and at 03:50
  when no single lane reproduced a failure. Re-running only the failing
  checks per lane cost minutes instead. At 03:29, 7 lanes reran 1 check in
  under 5 minutes. At 04:24, 8 lanes reran 15 checks in under 20 minutes.
- **Of 14 red verdicts, 4 were real failures.** 9 were superseded by a newer
  request from the same lane, and 1 was a rebase conflict.
- **The slot queue, not the toolchain, set the pace of edits.** Before `light`
  existed, dx measured 99 to 485 s waits for a 0.4 s check or a 1.6 s build.
  The first `heavy` gave a freed slot to whoever polled first, and one
  security job waited 25 minutes behind 9 waiters. From 02:08, `heavy` is first
  come, first served, and `light` takes the short commands.
- **Stale gate logs.** A gate whose VM run never started could be judged from
  the previous gate's log. The train now deletes the log first and accepts it
  only if its first line names the commit under test.
- **Build output was committed by accident.** dx committed the `target/`
  build directory of the bytecode-vm example and removed it in a later
  landing. Nothing rejected it.
- **A memory cap blocked compiler changes.** `scripts/with-limits.sh` caps
  address space at 768 MiB on Linux. The compiler's ThinLTO link peaked at
  764 to 766 MiB VmPeak under it; about 330 MiB of the uncapped 908 MiB peak
  was glibc arena reservations. So 0.3% more compiler IR made the link run out
  of memory. That blocked dx and any other compiler change until perf-compile
  changed the link partitioning (landed at 05:15).
- **CI on `v2` had been red since 2026-10-19, so nobody looked at it.** About
  40 checks outside `check-portable` were failing unseen. CI now shards the
  full suite and fails only on failures outside
  `tools/ci-known-failures.txt` (see `docs/garden.md`).

## Making the next run several times faster, at no cost

- **Pre-check every lane with `minyar dev check`** against one index built in
  the gate VM at the start of the run. Tonight no index existed, so
  `check-changed` fell back to all of `check-portable` for most changes.
- **Gate selectively.** Let the train run only the checks that the stack's
  changed files can affect, using the same recorded dependencies, with a full
  gate every few trains. A second free gate VM would let attribution re-runs
  proceed beside the next stack's gate, if memory allows.
- **Share a warm toolchain.** Give lanes one prebuilt `build/` snapshot of
  the base, copied with `cp -c` (a clone on APFS), instead of each lane
  bootstrapping the compiler in the shared slot queue.
- **Reject the obvious before gating.** Before stacking, the train should
  refuse `target/` and `build/` output and run `make check-garden` and the
  formatter. These take seconds and would have caught the committed build
  output and the formatting drift.
- **Start with `light`, first-come-first-served `heavy` and per-lane
  re-runs from the first minute.** Tonight all three were added mid-run.
