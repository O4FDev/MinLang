# Testing-disabled scalar fixture validation

This is a configuration/correctness result, with no new paired CPU acquisition.
[The preserved initial record](evidence/runtime-list-bulk-production-validation/run-423km4w0/results.json)
contains six builds: baseline/candidate system and fixed K32 O2, plus baseline/candidate
system K32 native C ASan+UBSan O1. Each runs the eight declared one-iteration cases:
32 plain and 16 sanitizer executions. Checks preserve full checksum, source/result
values, alias and mutation independence, pending-zero and absent active/cached frames;
fixed builds also assert pool charge zero. System quiescence alone does not independently
prove physical allocation-count recovery. LSan is disabled.

The original archived fixture defines `MINYAR_RC_TESTING=1`: its expected absence
oracle rejects that configuration while preprocessing succeeds. This is a configuration
red, not a runtime correctness red. The new six macro/body records show testing and
research observers absent, semantic asserts enabled, and the actual executed binary
symbol/disassembly records omit seven testing telemetry globals. Ordinary production
allocator state remains. Each exact fixture, runtime, object and binary hash is recorded;
the separate opaque checksum call and value loads remain.

The initial record omitted completed peak RSS; taskpolicy supplies a pressure hint,
not an RSS cap. A [separate same-binary resource replay](evidence/runtime-list-bulk-production-validation/run-423km4w0/resource-replay.json)
preserves 48 new one-iteration executions, actual time logs, CPU30/file32MiB/wall30 bounds
and post-exit 128MiB peak rejection. Maximum completed peak RSS was 18,644,992 bytes.
[Identity reconciliation](evidence/runtime-list-bulk-production-validation/run-423km4w0/resource-identity-reconciliation.json)
compares post-replay binaries to their original compile hashes; the first resource replay
did not separately save per-child before/after hash observations. The reusable helper
was prepared afterward and is not claimed as the exact executed inline script.
The original result is unchanged. These two execution scopes are separate.

[The production CPU proposal](runtime-list-bulk-production-cpu-proposal.json) remains
held until explicit coordinator release after the system soak final drain. It requires
fresh actual-build macro/body, sanitizer feature, symbol/disassembly and identity checks
on measured binaries. The previous 192 pairs remain test-accounted evidence and cannot
establish production-config ratios by cancelling bookkeeping.
