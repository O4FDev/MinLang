# Lua deferred decisions, round five

The 42 previously deferred Lua decisions have been reviewed against their exact
pinned source scopes, complete applicable helper bodies, and current Minyar
contracts. The original source keys, hashes and spans are preserved in the
before/after records in `pyswru-deferred-round5-decisions.jsonl`. This review does
not change any file-discovery or source-reading status for other languages.

The result is 33 adaptations, seven cases covered by existing tests or harness
methodologies, and two rejected mechanisms. Foreign-buffer Text ownership with
a caller-provided free callback and runtime executable-bytecode serialization
have no Minyar API counterpart. The seven existing coverage decisions explicitly
state their transferable methodology and excluded Lua behavior; they do not
claim that fatal Minyar OOM provides Lua's catch-and-continue recovery.

Seventeen new methods and one strengthened write-failure method implement the
accepted cases. All passed their focused native and ASan/UBSan checks. The
separate implementation handoff includes all 33 validated source keys. Exact
per-method reports, configurations, input hashes and the nine-method normal-exit
ownership subset are recorded in
`build/peer-pyswru-deferred-round5-validation.json`; proposed maintained-gate
metadata is in `build/peer-pyswru-deferred-round5-method-metadata.json`.

The largest adaptation generates the exact 263,145-element literal and checks
every element. Its original LLVM backend links exceeded 180 seconds at each of
O0, O2, O3 and Os. The Minyar frontend emitted 14,365,268 bytes of LLVM in about
0.14 seconds. A sampled Apple clang 17 process spent all 1,997 main-thread samples
under greedy register allocation, principally interference checks and splitting.
A diagnostic copy with a block boundary after each 1,024 element additions linked
at O0 in 46.40 seconds, but that transformed LLVM is not accepted as test evidence.
The parent agent implemented bulk scalar-literal lowering. The original maintained
test then passed all four native variants in 2.018 seconds, ASan/UBSan O0/O2 in
1.698 seconds, and normal-exit ownership O0/O2 in 1.356 seconds. These runs used
the actual new compiler and runtime, with every cell checked; the exact source
key is now included in the implementation handoff.

The runtime tests cover all actual allocation ordinals and independently derived
byte-budget boundaries for depth-100 owned recursion and two 10,000-byte Texts
joined into 20,000 bytes. The direct cleanup probe releases exactly 200,001
acyclic records with the allocator refusing new allocations, and checks zero
remaining objects, bytes, blocks and frames. Its formatter checks 16 independent
decimal boundary strings with zero and pattern initialization. The strict-warning
campaign documents its applicable C11 subset and four actual runtime profiles.

All four physical line endings are exercised in declarations, diagnostics,
line comments and raw multiline Text. Tests preserve Minyar's LF-only line/comment
contract and actual Text bytes, rather than Lua's long-bracket normalization.
The zero-write shim distinguishes no bytes written, partial writing and buffered
close failure, with baseline and unchanged-input controls.

Linux execution of this new batch and central manifest integration belong to
the parent checkpoint. Earlier Linux receipts are not credited to these changes.
Python, Swift and Ruby deferred decisions remain open, as does the broader
comprehensive peer review.
