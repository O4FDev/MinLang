# Public Float conversion allocation and lifetime baseline

Ten fixed binary64 values passed exact spelling, ASCII metadata, Character,
alias-lifetime and allocation-recovery checks through `minyar_float_text`.
[The final record](evidence/runtime-float-text/run-lbcunlb1/results.json) contains
one native O2 and one C ASan+UBSan O1 execution, preceded by the calibrated
observer red. No generated code, formatting algorithm change, cache policy,
performance measurement or production edit is involved.

The [preregistration](runtime-float-text-preregister.json) fixes the bit patterns
and expected strings before execution: positive/negative zero, 1.25, 0.1,
the minimum positive subnormal, both signs of the largest finite value,
positive/negative infinity and a quiet NaN. These exact strings use the existing
shortest-roundtrip and nonfinite spelling contract. They do not constitute a new
shortest-decimal proof or repeat the larger private formatter algorithm campaign.

| Observed boundary | Exact count or invariant |
| --- | --- |
| One public conversion | One 48-byte managed object and one backing request of spelling length + 9 bytes; total spelling length + 57 bytes. |
| Allocation service | Two helper hooks offering 64 K32 units; the empty pending queue causes no public poll invocation or queued work. |
| Metadata/content queries | Known ASCII count equals byte length; NULL index/backing, exact trailing sentinel and every Character match the independent expected string. |
| Alias and pressure | Retain the result, release its producer token, allocate a separate `Text(42.0)`, verify both strings, then release both remaining owners. |
| Complete lifecycle | Seven helper events offering 222 units; public polls and actual queued work remain zero. Immediate leaf destruction is separate from queued work. |
| Recovery | Object count, requested managed bytes and tracked heap allocations return to zero after every case; no frame or cache is created. |

Each successful control performs twenty public conversions: ten selected values
and ten pressure conversions. Its ten observation rows snapshot the first
conversion's allocation edges independently of the complete alias lifecycle.
The native and sanitized rows are identical. The isolated observer instruments
managed object/data allocation entries, service helpers and public poll entries;
it does not count private `format_float` iterations or libc calls. Therefore its
offered units are opportunities, not actual cleanup work or elapsed-time bounds.

The red observer deliberately suppresses the backing allocation event. It still
finishes the first case's semantic checks and exact recovery, prints one object
and zero observed backing events, and exits 70 on the independently required
two allocation edges. This establishes rejection of that omission, not a runtime
defect or proof against every possible observer fault.

The first [adapter attempt](evidence/runtime-float-text/run-xwqwqf31/results.json)
compiled but could not execute the fixture because its harness used nonexistent
`/usr/bin/taskpolicy`. The [correction](runtime-float-text-adapter-correction.json)
selects the actual `/usr/sbin/taskpolicy`; expected values, fixture bytes and
thresholds stay unchanged. This attempt is retained separately and is not
credited as the red calibration.

All fixtures stayed within the declared 30-second wall/CPU and 128 MiB resource
window. Darwin `time -l` records maximum RSS of 1,343,488 bytes for native and
9,568,256 bytes for sanitized execution. LSan is disabled. The
[durable archive](evidence/runtime-float-text/run-lbcunlb1/archive-index.json)
contains exact sources, observer patch, commands and logs; installed Darwin
Clang/SDK/sanitizer libraries and `time`/`taskpolicy` remain external prerequisites.
Production source hashes match before/after.

Source inspection found no Float-to-Text conversions in the inspected compiler
or examples: Craft converts HUD coordinates to Integer first. This adds a public
ABI allocation/lifetime baseline without claiming an application hot path or a
case for caching. Pending cleanup, fixed/lazy admission and other formatting
distributions remain outside this tiny system/K32 cohort.
