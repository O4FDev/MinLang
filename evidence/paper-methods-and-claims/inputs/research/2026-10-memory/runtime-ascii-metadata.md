# Known ASCII metadata through borrowed Text copies

Selected raw results, source diffs and hashes survive `make clean` in the
[durable runtime index](evidence/runtime/index.json); original acquisition paths
remain recorded there.

This is an engineering experiment on the existing Text representation, not a
novel reference-counting mechanism. The candidate was first evaluated in external
runtime snapshots. It changes no syntax, header layout, allocation sequence or
cleanup schedule. The count and timing controls below support acceptance of the
local copy-path expression; production validation is recorded as it completes.

## Hypothesis and representation condition

`join_by_copying` copies both operands into a new owning Text, then supplies an
unknown character count (`-1`). A later `.length`, character lookup or slice
builds the lazy index. For ASCII this index build counts the bytes and leaves
offsets null; it allocates no offsets. Even when both operand counts already
certify ASCII, the new result currently repeats that scan.

The isolated candidate passes the joined byte length as character count exactly
when each operand's known character count equals its own byte length. Otherwise
it passes `-1`. Under the existing valid-UTF-8 metadata invariant, equal byte and
scalar counts certify that every scalar occupies one byte, including embedded
NUL. Their concatenation has the same certificate; its fresh header has null
offsets. Unknown or Unicode operands remain unknown, preserving lazy malformed
input validation. Read-only self operands, views with certified ASCII bytes,
immortal cached values and known empty Text obey the same condition. This proof
assumes truthful metadata from runtime constructors; it does not validate an
arbitrary native caller fabricating a Text header.

The expression is local to the copy path. The compiler arena's separate in-place
extension path continues to create an unknown-count result. The previously
repaired consuming path already preserves the same ASCII certificate.

## Red/green counter evidence

Command, under the normal-QoS CPU/output/memory-limited wrapper:

```sh
python3 tests/memory-research-ascii-join.py --language
```

First evidence: [run-ie72rhd_/results.json](evidence/runtime/results/ascii-first-counts.json),
21 checks across two direct C builds and two generated-program links. The runner
first executes the baseline metadata target and requires its failed assertion:
"certified ASCII joins must avoid lazy-index scans". Only then does it change the
copied candidate's `join_by_copying` expression. The candidate target succeeds;
baseline and candidate malformed UTF-8 inputs both trap with the existing error.
Production sources are untouched.

| Generated mode | Baseline index builds | Candidate index builds | Baseline input bytes to index builder | Candidate input bytes |
| --- | ---: | ---: | ---: | ---: |
| Known 65,536-byte ASCII, 128 borrowed joins followed by length | 129 | 1 | 8,454,272 | 65,536 |
| Unknown ASCII, same joins | 128 | 128 | 8,388,736 | 8,388,736 |
| Known ASCII, joined result queried only for byte length | 1 | 1 | 65,536 | 65,536 |
| Known 8-byte ASCII | 128 | 0 | 1,152 | 0 |
| Known accented/non-BMP Unicode | 129 | 129 | 99,200 | 99,200 |

The long known, unknown and no-query modes each execute 8,599 observed managed
service-helper calls in both variants; their actual helper work is zero. The
short mode has 392 calls and Unicode mode 659, unchanged. These are observations
of `rc_service_pending`, not a complete count of explicit poll calls or an
aggregate per-expression budget theorem. All generated outputs match exactly.
Input bytes to the index builder are a workload counter, not a count of CPU
loads: ASCII scanning uses word reads, Unicode scanning has additional passes,
and native compiler optimizations still matter.

The direct long known-ASCII query changes one 65,537-byte index build to zero.
Both variants make exactly two backing/header allocations, zero reallocations
and two managed service hooks. With queued record debt at K32, both perform
exactly 64 cleanup work units through those hooks. Unknown and Unicode results
still build their index. Consuming certified ASCII reuses its header with zero
allocation/service/index calls, providing an oracle for the semantic-equivalent
"always invalidate" performance mutant.

Independent review requested more representation cases. They were added before
acceptance: known empty left/right/both; known left with unknown empty/ASCII or
known Unicode right; a retained sliced ASCII view and immortal Character cache
values on either side. These cases slice first, verify exact copied bytes and
character values, and recover all owned objects/backing storage. The expanded
system/K32/O2 run passed at `run-41o8qr07`. Fixed-pool/K1 ASan+UBSan with generated
function AddressSanitizer attributes passed at `run-is7ea_xn`. Each records 21
checks. LeakSanitizer is disabled; UBSan covers C runtime operations rather than
all generated arithmetic instructions.

## Timing protocol and decision

`tests/memory-research-ascii-join-bench.py` copies uninstrumented baseline and
candidate runtimes and the current compiler artifact. The same generated LLVM
links to both runtimes. It increases only the repeated borrowed-call workload:
4,096 long joins, 262,144 short joins and 16,384 Unicode joins. Construction,
cleanup and three output lines remain inside the generated program measurement.
Every output is checked. Each of twelve blocks randomizes mode order, then
randomizes adjacent baseline/candidate order. Warmups and all raw pairs remain
in the artifact; no observations are discarded.

Process CPU time is primary, with wall time and nominal CPU-clock resolution
also retained. A 95% percentile bootstrap resamples complete observed pairs to
estimate the median ratio, assuming independent pairs; it does not model all
host trends. The declared material negative-control regression is more than 3%
median slowdown with a paired interval excluding parity. Broad intervals require
more evidence, not a speed claim. Short, unknown, Unicode and no-query modes are
required negative controls. Counts alone demonstrate avoided index work; they
do not establish an operating-system latency bound or HFT suitability.

The exclusive project timing run passed all output checks:
[run-603xbkqt/results.json](evidence/runtime/results/ascii-paired-timing.json).
It ran on Darwin 25 / arm64 under normal QoS with CPU/output/memory limits and
nice 15. Other project compiler jobs were paused; external OS activity remained.

| Generated workload | CPU baseline/candidate median | 95% paired bootstrap interval |
| --- | ---: | ---: |
| Known long ASCII, length queried | 2.392 | 2.345–2.411 |
| Unknown long ASCII | 1.003 | 0.998–1.012 |
| Known long ASCII, byte length only | 0.991 | 0.979–0.997 |
| Known short ASCII, length queried | 1.036 | 1.026–1.049 |
| Known accented/non-BMP Unicode | 0.993 | 0.990–1.001 |

Ratios above one favor the candidate. The no-query mode has a measured roughly
0.9% slowdown, including an interval below parity; it must not be described as
unchanged timing. The Unicode point estimate is roughly 0.7% slower with an
interval including parity. Neither crosses the declared 3% material-rejection
criterion. The large known-ASCII benefit, short positive control and unchanged
allocation/service counts support this bounded engineering tradeoff. The result
does not establish that every Text join is faster or explain all code-layout and
host effects. Raw wall durations, pair ranges, clock resolution and initial/latest
load averages remain in the artifact.
Baseline batches used approximately 8.4–28.2 ms of process CPU; the reported CPU
clock resolution is 1,000 ns. The no-query pair range is 0.916–1.018, including one
larger slowdown retained in both the raw artifact and figure. The median/interval
decision rule does not bound tail regressions or an individual operation's time.

![ASCII timing ratios with all paired samples and control detail](runtime-ascii-timing.svg)

Vector PDF and high-resolution PNG exports accompany the SVG; the generator and
input/output hashes are in `runtime-timing-figures.py` and
`runtime-timing-figures.json`. The figure repeats the artifact's recorded interval
estimates and displays every pair rather than replacing the raw evidence.

## Production validation

The accepted expression is now in `runtime/minyar_runtime.c::join_by_copying`.
Final runtime SHA256:
`c4e78f59096e0af8926c8d06febb9277e8c7cb7e5de8fc63b907d3afb613fcb4`.
The final formatter added only a newline between the ternary alternatives after
the focused runs; the condition and code tokens are identical to the evaluated
candidate. A maintained assertion now checks the known ASCII certificate before
calling length/indexing, so an avoidable scan cannot silently satisfy only the
semantic oracle. The same fixture also checks certified consuming ASCII.

The first final focused Text invocation passed 64 checks across 21
eager/system/fixed/lazy C configurations at K1/K32, with eighteen C cases and
malformed-input diagnostics:
[run-_gj9t242/results.json](evidence/runtime/results/text-c-only-correction.json).
It omitted `--language`; an initial progress report incorrectly described it as
107 native/generated checks. Inspection of the saved JSON caught that reporting
mistake. The requested generated matrix is rerun separately before integration
freeze, and the runner now records/asserts requested and observed coverage plus
an explicit summary instead of relying on a remembered configuration count.
The exact formatted-runtime `--language` rerun then passed:
[run-zxq8d1m_/results.json](evidence/runtime/results/final-text-matrix.json).
Its derived and asserted summary is 107 recorded checks, 21 C configurations,
21 generated executions and 21 expected UTF-8 traps, with eighteen C cases per
configuration. This covers the final source hash quoted above.
The expanded metadata counter suite passed lazy/K32 C and generated ASan+UBSan
at [run-r4eocr5x/results.json](evidence/runtime/results/ascii-final-lazy-sanitizer.json) (21 checks), and
eager native C at `run-6k38fw4n` (8 checks). Earlier fixed/K1 sanitized and
system/K32 native candidate controls are preserved above. The research runner
accepts explicit before/after runtime directories for replay after adoption;
portable CI uses the current-source Text fixture without archived snapshots or
instrumentation. Whole integration evidence is owned by the separate peer lane.
