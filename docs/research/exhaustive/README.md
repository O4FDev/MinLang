# Exhaustive peer audit in progress

This is the expanded audit requested after the initial ten-language survey.
It is **not complete**. Acquiring a source archive, hashing files or enumerating
test roots does not establish that any test was read.

Each language directory contains a pinned inventory, a JSONL decision ledger,
and progress notes. Each decision identifies a repository/revision, file hash,
case or assertion scope, source span, disposition, reason, local coverage and
whether implementation is still required. Broad helper/generator decisions do
not imply every generated case has been reviewed. Runtime input domains can be
unbounded; the generator and its finite checked-in variants must be distinguished
from all possible generated executions.

Inventory file counts include support/data/production candidates where embedded
tests might exist. They are not test-case counts. Pending repository dependencies,
auxiliary roots, embedded cases and generated domains remain explicit. Per-case
decisions are recorded only after reading the relevant source bodies.

Run `python3 tools/check-peer-audit.py` to validate internal consistency. Add
`--source-root /tmp/minyar-peer-full` to verify source hashes and spans against
the acquired snapshots. `--require-complete` must fail while discovery,
case enumeration, file reviews, deferred dispositions, generated cohorts or
required implementations are pending. This
validator checks the records; it cannot independently prove that an agent read
and understood a source file.

Agents own their language inventories/decisions. Validated implementation
resolutions belong in a separate `implementations.jsonl` here, keyed by language,
repository, revision, path and case ID, with local tests and validation evidence.
An implementation may resolve several genuinely equivalent upstream decisions;
mere similarity or a matching filename is not sufficient.

Source spans use each record's explicit `line_numbering` when present. `lf`
means splitting raw bytes at LF, preserving CR/Unicode separator bytes as test
data. Legacy records use physical byte `splitlines()` numbering and are checked
against the original source. Snapshots remain outside the repository; inventory
and decision records are retained here.

Finite generated domains may use individual rows or an exact indexed family
with explicit axes, exclusions, per-instance rules and cardinalities. They must
state whether judgments were derived from a read generator or individually read
artifacts. The checker validates known Go families and hashed V8 division-domain
artifacts; unknown families remain counted as unchecked and block completion.
These mathematical consistency checks do not establish source-reading evidence.

## Completion contract for the comprehensive goal

The goal covers all ten pinned language inventories, not a fixed number of new
methods or a fixed-size review batch. Implementation and review must proceed
with exact source decisions and executable evidence. The current implementation
queue is derived by subtracting `implementations.jsonl` keys from decisions whose
`implementation_needed` is true; temporary per-language queues are under
`build/peer-implementation-backlog/`. These queues are snapshots, not authoritative
new ledgers.

Completion requires all of the following:

- Resolve every applicable recorded implementation decision with validated local
  coverage, or correct an erroneous adaptation using specific source and Minyar
  semantic evidence. A difficult implementation is not a reason to reject it.
- Resolve every deferred applicability decision; a false implementation flag
  does not make an unresolved disposition complete.
- Complete source discovery and review, including auxiliary roots, embedded tests,
  wrappers and generated domains. File enumeration never substitutes for reading.
- Integrate all accepted suites and methodologies into maintained test gates and
  preserve independent oracles, negative controls and per-configuration evidence.
- Resolve relevant platform exclusions and required failing checks, or leave them
  explicitly open. A skipped platform case is not a validated implementation.
- Finish all agent assignments and independently review their implementation and
  resolution claims. The exhaustive checker must pass with `--require-complete`.

The 2026-10-05 round-four checkpoint contains 541 peer methods across four suites
and 21,330 resolved upstream case/assertion/methodology keys. Those are different
measures. All 5,882 original implementation decisions were resolved in round three;
round four added 408 mappings. Independent reviews covered the older 4,779
C++/Java/JavaScript keys, all 1,085 new round-three mappings, all 408 round-four
mappings, and the seven adopted parent methodologies. Recorded corrections were
validated, including source trace order, helper return values and link phases.
The [Linux receipt](linux-round4-validation.json) records all 541 optimizer,
540 sanitizer and 93 ownership declarations against frozen sources.

This does not complete source review. At that checkpoint 571,545 inventoried
candidate files and 3,963 applicability decisions remained pending or deferred;
nine languages still had unfinished discovery and case enumeration. Lua had
complete recorded source discovery/review but 42 deferred decisions. The validator
now blocks completion for deferred dispositions and for generated artifact cohorts
without corresponding ledger rows. New source review can add implementation
decisions after this checkpoint. The live ledgers and checker output, rather than
these historical counts, determine what remains. Subagents are resolving deferred
cases and continuing source review.

The round-five implementation stage declares 594 peer methods, 131 ownership
selections, and 23,231 validated implementation mappings. These counts include
new Boolean cell/alias cases and performance aggregation controls. Independent
review also resolved the full Lua deferred queue, checked all 646,728 Zig
integer-log domain identities, and corrected overbroad Go/LLVM methodology
rejections. The [Linux round-five receipt](linux-round5-validation.json) now records all
594 optimizer, 593 sanitizer and 131 ownership declarations passing without
required skips. The [macOS receipt](macos-round5-validation.json) separately
records the Linux-only skips and nine normalization-sensitive filename exclusions.
The [core receipt](linux-round5-core-validation.json) retains the initial missing
LLVM-tool failure and the successful codegen retry after those tools were installed.

The [performance receipt](round5-performance-validation.json) records the
263,145-element literal lowering fix, ASCII-block Unicode indexing and cold
stack-bound initialization. The production compiler passes its unchanged
75-million-instruction ceiling at 68.94 million instructions; every timed and
profiled sample now requires fresh LLVM matching the self-hosted fixed point.
Independent runtime and measurement reviews are linked from that receipt.

At this stage the live audit still reports 571,535 pending candidate files and
1,902 deferred applicability decisions, with no unresolved recorded implementation
mapping. Those outstanding reviews can uncover further applicable tests. Source
review continues in parallel with checkpoint validation, and these counts are
historical once later decisions land.

The round-six integration declares 639 peer methods and 168 ownership selections,
with 23,530 validated implementation mappings. The
[focused maintained receipt](round6-maintained-validation.json) records all 45
new methods, the strengthened shared file-output checks, exact decimal diagnostics,
and existing Boolean coverage: 50 native, 50 sanitizer and 39 ownership selections
passed. Four existing decimal mappings were amended; 299 mappings were added after
independent source and implementation review. The
[publication journal](round6-publication-journal.json) preserves exact before/after
decisions and the 13 newly completed file reviews. The [full round-six Linux receipt](linux-round6-validation.json) records all
639 optimizer, 638 sanitizer and 168 ownership declarations passing without
required skips or exclusions. Its isolated source snapshot matches the maintained
execution inputs, and all 596 frozen source hashes were unchanged after execution.
The [supporting gate receipt](linux-round6-core-validation.json) records successful
evidence-harness, measurement-control, regression and codegen checks.

The round-six post-publication consistency check passes with zero unresolved implementation
mappings. It still records 571,522 pending candidate files and 1,839 deferred
applicability decisions. Further loop, integer-division, grammar and UTF-8 cohorts
remain under independent review; private drafts are not maintained coverage.

The round-seven integration declares 661 peer methods, 188 ownership selections,
and 23,571 validated implementation mappings. Its [macOS focused receipt](round7-maintained-validation.json)
and [Linux focused receipt](linux-round7-focused-validation.json) each record
23 native, 23 sanitizer and 20 ownership selections passing with no required skips.
These cover all 22 new methods and the amended 1,119-cell decimal oracle. The
Linux run verified all 616 frozen source and reused production-artifact hashes;
the production sources match round six. This is focused validation, not a fresh
compiler build or a full 661-method Linux run.

The [round-seven publication journal](round7-publication-journal.json) records
54 decision changes, 41 new mappings, four amended decimal mappings and one
completed file review. Independent reviews cover all adopted Zig loop bodies,
the exact C arithmetic profiles and width boundaries, and all 291 cells of the
mixed Python grammar partition. The consistency check passes with no unresolved
implementation mappings; 571,521 candidate files and 1,824 applicability decisions
remain pending or deferred. The completion audit correctly fails. Unicode and
Java array-fill drafts remain outside that checkpoint's maintained coverage counts.

Round eight integrates 683 peer methods, 203 ownership selections and 24,808
validated implementation mappings. The [macOS focused receipt](round8-maintained-validation.json)
and [Linux focused receipt](linux-round8-focused-validation.json) each record
27 native, 27 sanitizer and 16 ownership selections passing without required skips.
They cover 22 new methods, four strengthened UTF-8 stage oracles, and the existing
concatenation and decoder coverage used by this batch. Linux verified all 628
frozen source and reused production-artifact hashes. Production sources still
match round six; this is focused validation, not a fresh compiler build or a
full 683-method run.

The [round-eight journal](round8-publication-journal.json) preserves 1,275 decision
changes, 1,237 new implementation mappings and 181 existing mapping amendments.
The new domains include the 8,192-invocation Java fill replay and its separate
length/boundary supplements, 1,211 Zig UTF-8 source scopes, and 38 reviewed Python
Unicode scopes. C runtime probes identify their actual compilation and execution
phases; they do not claim Minyar frontend coverage. No additional file review was
marked complete in this batch.

Independent review found that an invalid-UTF-8 diagnostic alone could also pass
if file reading decoded prematurely. Exact raw-ingress checks and byte-length
observations now distinguish the stages. The [oracle review](round8-utf8-stage-oracle-review.json)
retains the old false passes and all 274 corrected eager-reader rejections across
four older methods at O0/O2; [a separate reviewer](round8-utf8-stage-oracle-independent-cjj.json)
confirmed the fix. New Zig and Python malformed-byte counterparts additionally
check successful raw reads and complete byte contents.

The current consistency audit passes with zero unresolved recorded implementation
mappings. It still reports 571,521 pending candidate files and 1,783 deferred
applicability decisions, and the completion audit correctly fails. Remaining
Unicode conversions, byte-equality and JavaScript stress scopes are private work
until independently reviewed, integrated and validated.

The comprehensive goal is active. Its completion contract above is unchanged;
`--require-complete` must continue to fail until all outstanding source scope and
implementation work is actually resolved.
