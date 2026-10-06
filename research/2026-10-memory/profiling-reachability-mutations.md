# Targeted literal-true reachability mutation result

Six unique source-anchor mutants compiled and were killed by the calibrated
17-test O0/O2 reachability suite. Every proposed detector actually failed its
named mutant. The unchanged compiler calibration passed; no build error,
process timeout, setup failure or incomplete suite entered the denominator.
The score is **6/6 viable targeted mutants detected**, not an estimate of every
possible compiler bug or the broader operator-site mutation score.

| Mutated contract | Intended detector | Observed failing subcases |
| --- | --- | --- |
| Count a dead break as an exit | Unreachable break after return | 3 |
| Ignore reachable breaks | Reachable break requires following return | 11 |
| Dispatch changed while marker as for | Continue after reachable break | 2 |
| Leak branch dead state | Nested loop then reachable outer break | 1 |
| Reset dead nested block to reachable | Dead nested branches and loops | 1 |
| Treat compound condition as literal true | `true && flag` / `true == flag` fallthrough | 3 |

Each isolated copy was compiled by stage zero, linked at O0, then used by the
entire unchanged suite; generated native programs run at both O0 and O2. The
source anchors, full subprocess stdout/stderr, failure IDs, candidate SHA256,
calibration, command timeouts and before/after source hashes are retained in
`build/peer-research/mutants/run-ruy4i6pl/results.json` and copied to
`profiling-reachability-mutations-result.json`. No measured source changed.

The runner is `scripts/peer-research-mutants.py`. Its six pure accounting tests
cover unique/stale/ambiguous anchors, calibrated suite completion, honest
survivors, exclusion of timeout/setup/unexpected errors, and an explicit viable
denominator. Initial missing-runner red was followed by one corrected test
fixture typo (`no anchor` itself contained the searched word); no production
bug is claimed from that harness correction.
