# Fast gate: the full gate on shard boxes

`tools/fast-gate.sh TREE` runs the full landing gate for a working tree (the targets in
`tools/fast-gate/checks.txt`: `check-portable`, the benchmark checks and the gate extras, about 440 checks) on
on-demand DigitalOcean shard boxes, and prints one verdict line per tree:

```
FAST GATE PASSED: TREE: 442 checks in the plan (each shard's check-in-parallel: [442]; 340 of the 340 reference checks + 102 new), 442 run on 8 shards + the cache box, 0 failed, 0 problems; wall W s (S s since the command started); results …/merged.tsv
```

It is the merge gate. `minyar dev check` is for iteration; `tools/fast-gate.sh` runs before merging and replaces the
single-box `make check-in-parallel CHECKS="…"` gate, with the same verdict for every check. Several trees can be gated
one after another on the same shards: `tools/fast-gate.sh TREE1 TREE2::"check-portable check-benchmarks" …` (a
`::` suffix gives a tree its own target list). A multi-tree run ends by comparing every tree whose commit has a
recorded single-box gate (`tools/fast-gate/recorded.tsv`) with that record, check for check (`agree.py`).

## How it works

- **Boxes.** Eight `s-8vcpu-16gb-amd` droplets named `shard-<run>-<i>`, tagged `test-shard`, from the snapshot in
  `tools/fast-gate/image.txt` (`make-image.sh` and `image-provision.sh` build it: the pinned LLVM toolchain,
  FileCheck, Rust, the gate box packages and a base tree for delta syncs). The run deletes them on any exit;
  `test-shard-guard` deletes any shard after 2 h and stops all of them at the daily budget.
- **Cache box.** The persistent `shard-cache` box (`create-cache.sh`, an `s-4vcpu-8gb` tagged `test-shard` and
  `test-shard-cache`) receives the tree at the start, builds the compiler and the check runner and plans the gate
  while the shards boot; the shards copy its tree, build outputs and plan over the VPC. Once done it also runs one
  slower shard of the plan in a copy of its own (`--cache-shard`). Without it each shard builds for itself.
- **Every shard runs the whole gate.** Each shard runs the tree's own `make check-in-parallel` over the full target
  list. A `make` shim first on `PATH` (`tools/fast-gate/shim/make`) finishes at once the checks and shared builds that
  were packed onto other shards, so every check runs exactly as on one box, with the same runner, environment, order
  constraints and timeouts. The verdict of a check is its own shard's; an aggregate passes when its own recipe and
  every check under it passed.
- **Plan and packing.** `plan.py` reproduces the runner's plan from Make's database (checks, aggregates, shared
  builds); `pack.py` packs it onto the shards longest first from measured times (`times.tsv`, `goal-times.tsv`),
  keeps the shared builds a shard needs together, builds slow shared builds beside the checks, and models the
  runner's own rules (exclusive checks wait for an idle shard; an aggregate waits for its children). Refresh the
  tables from runs with `update-times.py RUN…` (medians over runs; shard boxes are shared-CPU).
- **Fewer boxes.** `--boxes N` below `--shards` runs the same plan in waves on N boxes; `estimate.py RUN` projects
  such a run to one box per shard.

## Budget

`test-shard-guard` on brief-crawl-1 counts every shard (and the cache box) as at least one hour at the droplet price,
against $10 per UTC day; `tools/fast-gate.sh` refuses to start a run that would pass it. One 8-shard run costs about
$1.33 as the guard counts it, so gate several trees in one call when you can.
