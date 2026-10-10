# Proposed scalar List CPU observation

**Proposal only; no timing process has been launched.** The exact scope and
thresholds are in the [machine-readable proposal](runtime-list-bulk-cpu-proposal.json).
Completed pressure/error and supplemental controls support further observation,
while independent review and the coordinator's timing release remain required.

The job would compare six idle scalar lengths (0, 2, 31, 32, 1,024 and 8,193),
plus object-debt and reference fallbacks at length31, on system/K32 and
fixed16MiB/K32. Twelve randomized adjacent fresh-process pairs per case give
192 pairs/384 measured children. A retained baseline pilot determines a common
repeat count before acquisition; all pilot and paired rows remain visible.

Counters and sanitizers are disabled. Every result goes to a separately compiled
opaque full-value checksum function with LTO disabled; expected checksums are
computed independently, final slots are inspected and saved machine code must
show the actual copy/value-reading work. The measured process CPU interval
includes append, checksum, release and quiescent drain, excluding source setup
and output. This is a primitive workload, not application hot-path evidence.

Large idle cases must each exceed a 1.05 geometric ratio with lower pointwise
95% bound above parity to justify adoption from these CPU observations. A small
or fallback case below0.97 by geometric or median ratio blocks automatic
acceptance; any retained paired slowdown above10% requires explicit review.
Estimator-sensitive results, paced-soak interference and external load stay in
the report. There is no quiet-host, tail-latency or overall speed claim.

If selected, final-source checks must exercise scalar and aggregate Text patches
together, with generated List/source-lifetime coverage and Text metadata controls.
Existing isolated timing or correctness results do not establish that combination.
