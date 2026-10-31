# Real-world suite

Other Minyar projects, built and run as their authors ship them, measured with
the Minyar tree under test. This is the score that says whether a compiler
change helps programs that are not in `benchmarks/compare`.

```sh
# On the Linux box that holds the read-only project copies:
python3 benchmarks/realworld/run.py --tree /home/agent/swarm/rw \
    --projects /home/agent/swarm/realworld --json build/realworld/report.json
```

One line per project: build seconds, workload retired instructions
(`valgrind --tool=cachegrind --cache-sim=no`, deterministic), and wall time
(median of `--repeat` fresh processes with the min/max spread). Ratios compare
against `baseline.json`, recorded on goal/2026-10-30; the final line is the
geomean of each ratio column.

## Projects and workloads

| project | build | workload |
| --- | --- | --- |
| neo-db | `minyar build --release --locked` (whole database) | its own `bench/embedded/embed_bench.min`: create, load 1,000 rows, 2,000 prepared select-1 and primary-key rounds, 2,000 durable inserts |
| minyar-query | `tools/build.sh release` | analytical SQL over a 200,000-row generated CSV: filter, two-column GROUP BY, ORDER BY, LIMIT |
| minyar-js | `make` | `data/js_workload.js`: sieve, recursion, object counters, string building, char codes |
| minyar-terminal | `minyar --release src/main.min` | replay a pinned vtebench 3.3 MiB dense-cell payload into a 120x40 terminal |
| minyar-sandbox | `minyar src/main.min` | its `serve` policy session: 20,000 lifecycle transitions and billing conversions on stdin |
| minyar-sim | `scripts/build-native.sh` | its native discrete-event benchmark, 100,000 universes |

Inputs are generated from constants in `run.py` (`data/query_gen.py`,
`data/js_workload.js`, the LCG-built sandbox session) and their SHA-256 is in
every report, so a workload cannot be tuned per run. Each workload runs twice
under cachegrind; the suite fails if the instruction count or the output
changes.

## Project copies

`sandbox/...`-style copies live outside this repository and are never edited
in place: `sync-projects.sh` rsyncs each upstream repository to the box,
records its commit in `.rw-commit` (the suite refuses a copy pinned to another
commit), and applies `adoption/*.patch`.

The patches are the exact, minimal edits those projects need to build with the
current tree (adoption evidence). Today all of them are the same source-level
API change: `Text(bytes)` no longer accepts `Bytes`, so a project must decode
with `text.decode`/`text.decodeOrStop`. A project that needs a patch is a
compatibility regression in the language, not a benchmark problem.

## Adding a project

Add an entry to `PROJECTS` in `run.py` with its pinned commit, build command,
artifact, workload argv, and the `contains` strings its output must include.
Keep the workload under a second of native time (cachegrind is ~30-50x slower)
and make it print something that proves the work happened.
