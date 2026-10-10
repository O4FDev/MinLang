# Profiling coverage and explicit gaps

This ledger tracks performance attribution separately from correctness gates.
A successful test validates its asserted contract; it does not mean its entire
subsystem has been profiled. Measurements below refer to retained artifacts,
not an assertion that every function or workload has been exhaustively covered.
The source-frozen baseline full gate completed with one public cold-bootstrap
scheduling timeout; all other invoked gates completed their assertions. Later
source changes have focused evidence and await the final full integration gate.

The Unicode gap returned U+00C3 instead of U+00E9 after an indexed nonASCII Text
was consumed into a join. Its original snapshot is retained in
`build/memory-research-text-join-index-red/run-8o4rlalr/results.json`. The production
repair passed 21 runtime configurations / 107 checks. A separate matching
SYSTEM/K32 original-versus-current portable stress runs at O0/O2 in
`build/peer-research/unicode-peer-system-toxvm0vm/results.json`. This discovery
illustrates a path that the earlier broad gate did not assert.

Literal-true loop reachability has also been repaired with red-first regression,
independent review and exact bootstrap fixed points. Unreachable source still
resolves names and validates types. The supported scope is a single literal
Boolean `true`; correlated and compound conditions remain conservative.

The public launcher's build child now requests normal macOS scheduling priority
while retaining memory, CPU, output and nice controls. Bulk builds remain in the
background class. The actual default cold-launcher test passed after the fix;
policy tests separately verify the scoped context and inherited limits.

| Subsystem | Performance evidence so far | Unmeasured work and next bounded experiment |
| --- | --- | --- |
| Bootstrap C subset | Initial stage rebuild and fixed point passed; no isolated C frontend timing | Separate stage-zero parse/type/LLVM emission and binary creation from self-hosted phases; fixture sizes chosen from existing bootstrap portability tests |
| Lexer and source origins | Marked tokenize contributes 23% of compiler-self CPU; compiler-self/source hashes retained | Split source acquisition versus token bytes/origins, Unicode paths and tokenizer allocation counts; marker overhead is excluded from acceptance budgets |
| Declaration discovery | Coarse scanned declarations/record names/function discovery boundaries | Attribute individual symbol-kind costs and duplicate/error paths without making diagnostics timing a production requirement |
| Symbol lookup | Indexed lookup construction rises 5.38× for 4× functions; sorting consistent with nlogn | Count successful/failed lookup comparisons and symbol storage; no evidence yet that replacing lookup would help |
| Expression/type/control/ownership lowering | compileFunctions 53% of self CPU; body cost near linear on functions/locals | Selected finer function probes/count-only instrumentation, managed versus scalar expression families, source-frozen literal-true reachability regression now passes |
| LLVM text emission | Output byte identity checked for every marked sample | Separate text construction, buffer copying, native write and backend processing; production checked arithmetic and effect order retained |
| Module source load/rewrite | 32/128-module marked load exclusives 70/72%, rewrite 9/11% | Separate file reads/path canonicalization/visited lookup, import depth versus width, warm filesystem versus fresh process; coarse function cost includes several operations |
| Compiler allocation arenas | Production self RSS 9.25 MiB; larger locals 12.98 MiB | Count requested object/data/List allocations and arena used/reserved/extended bytes on isolated runtime copy; RSS does not identify ownership or allocated bytes |
| Incremental module frontend | Existing guarded module compiler rebuilt and policy tests passed | True cache cold/warm/body delta/interface delta with exact affected-module identities and independent outputs; warm filesystem alone is not a module-cache hit |
| Launcher/build driver/cache publication | Initial/full-gate builds logged; runtime-cache 4 tests passed | Profile validation, cache lookup, atomic publication, runtime/backend reuse and link wall/CPU individually; source/toolchain changes kept separate |
| Clang LLVM optimization/link | Production compiler resources exclude these costs | Retain frontend-only versus complete executable compilation and link measurements; investigate binary size/LTO tradeoffs only after pinned baseline |
| Default eager/bounded ownership service | Runtime agent has independent correctness/paired append evidence | Compare cleanup debt service, live roots, queued-dead bytes, retire queues and iterative destruction under matching controls; source-version changes recorded |
| Fixed/lazy pools | Final guarded append pressure and owner-debt controls pass | Allocation/fragmentation/recovery profiles with tight capacities; committed/RSS versus reserved virtual bytes recorded separately |
| Stack/private ownership admission | Normal-QoS broad gate completed all 36 bounded stack configurations; final runtime checks are separately recorded | Trace dynamic stack ownership fallback and lifetime invariants separately from application timing |
| Collections and scalar storage | Guarded reserve-once production change and 13 peer semantic tests pass their focused checks | Text/List creation, shared aliases, unique scalar leaves, bounds traps, iterator/slice hotspots; ordinary append control retained |
| Text/Unicode/numeric conversion | Peer Text/Character initial adaptations pass O0/O2 | ASCII versus nonASCII index/iteration/slice/concat/format/parse, allocation and UTF8 validation costs; scalar index is distinct from byte index and grapheme |
| Native standard interfaces/files | Existing runtime/native and library correctness gates available | Deterministic prepared file/text parsing, file size/read/write, native ABI boundary cost; I/O runs isolated from steady-state allocation timing |
| Graphics/OpenGL platform | Sources/test gates identified; no graphics timing evidence | Loader/link/error checks where platform permits; interactive rendering/GPU timing needs a suitable graphical environment and is an explicit unmeasured platform path |
| Test/tooling infrastructure | Runtime-cache 72s, ownership-policy 48s in first host-starved gate | Split harness/process startup/native compilation/execution; preserve timeout classification and normal-QoS rerun evidence rather than treating throttled wall time as runtime cost |
| Realistic prepared allocation trace | Not measured | Deterministic bounded message parsing/orderbook-style update trace with independent expected final checksum, prepared inputs, no steady-state I/O and multiple cleanup profiles; no HFT certification claim |
| Cross-platform and systematic campaigns | Gates identified, no new Linux/Windows/AFL duration run yet | Existing platform runners, bounded mutation/coverage and duration-based fuzz campaigns after correctness; portable API checks do not replace execution on target OS |

Phase evidence is `build/peer-research/profiling-8j7fw1ra/results.json`;
uninstrumented resources are its `production-resources.json`. The initial broad
gate's mixed source provenance and interruption are in
`profiling-full-gate-sources.json`. Host starvation and the normal-QoS wrapper
are recorded in `profiling-normal-qos.json`; bulk-wrapper default scheduling remains unchanged; the public bootstrap child
has a bounded foreground exception. Quiet-host timing remains a separate reservation from correctness.

Independent peer ownership review is in `peer-nim-koka-lean.json`. That report
includes additional source files and directories outside the 32-file aggregate;
its evidence does not automatically promote unreviewed entries in `peers.json`.
