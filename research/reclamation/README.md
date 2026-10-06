# Bounded reclamation research notebook

This directory records the research assessment started on 2026-09-20. Prior
uncommitted work and the initial notebook are preserved in stash
`a4135900360138598cc5772b3d1d6ed537d50432`; only the notebook was restored onto
`research/bounded-reclamation`. Nothing has been pushed. The tentative subject is **bounded reclamation
across heap objects and compiler-managed ownership frames**; novelty remains
unconfirmed.

- [Related work and claim matrix](related-work.md)
- [Formal model, proof sketches, and open obligations](formal-model.md)
- [Comparison protocol and remaining application experiments](protocol.md)
- [Initial pilot measurements and validation](pilot-results.md)
- [Continuing-load protocol](event-protocol.md)
- [Follow-up assessment](followup-assessment.md)
- [Compiled continuing-load measurements](event-results.md)
- [Prospective event/idle acceptance suite and comparison gates](acceptance.md)

The first concrete finding is a counterexample to the documented K=1 public
release bound: final release of a Text view also frees its backing root and
reported two work units. The research branch now queues a newly dead backing
root for a separate work unit. The graph/frame pilot is historical, pre-fix
evidence; the new Text regression checks real destruction, not just counters.

## Reproduce

From the repository root, using Python 3.10+ and Clang:

```sh
make build/minyarc
python3 research/reclamation/check_model.py
python3 research/reclamation/test_event_harness.py
python3 research/reclamation/test_harness.py
python3 experiments/memory/production-contract-model.py

python3 research/reclamation/run_study.py --output build/reclamation-diagnostic-repro
python3 research/reclamation/run_study.py --sanitize --output build/reclamation-sanitize-repro
python3 research/reclamation/run_study.py --mode sampled --nodes 16384 --output build/reclamation-sampled-repro
python3 research/reclamation/run_study.py --mode batch --nodes 16384 --output build/reclamation-batch-repro

python3 research/reclamation/report.py \
  --diagnostic build/reclamation-diagnostic-repro \
  --sanitize build/reclamation-sanitize-repro \
  --sampled build/reclamation-sampled-repro \
  --batch build/reclamation-batch-repro \
  --output build/reclamation-pilot-repro.md

clang -O2 -fsanitize=address,undefined research/reclamation/text_view_bound.c -o build/reclamation-text-bound
build/reclamation-text-bound
```

The last command now exits 0 and reports one unit, one root remaining after
release, and no objects remaining after polling. The original failing evidence
is retained separately under `build/reclamation-text-bound-evidence/`.

```sh
python3 tests/text-view-budget.py
make check-bounded check-memory-profiles check-stack-ownership check-runtime-unit
python3 research/reclamation/check_fairness.py --output build/event-fairness-repro
python3 research/reclamation/event_study.py --output build/event-diagnostic-repro
python3 research/reclamation/event_study.py --sanitize --output build/event-sanitize-repro
python3 research/reclamation/event_study.py --mode timing --output build/event-timing-repro
python3 research/reclamation/event_report.py \
  --diagnostic build/event-diagnostic-repro \
  --sanitize build/event-sanitize-repro \
  --timing build/event-timing-repro \
  --output build/event-report-repro.md
```

Run timing campaigns serially. Each output directory must be new. Results,
source snapshots, transformed runtime variants, commands, binaries and raw traces
are kept under the selected directory. `build/` is ignored and `make clean`
removes it; archive evidence before cleaning. Source hashes include this notebook,
so later wording changes can change snapshot hashes without changing runtime code.

`run_study.py` validates accounting and trace consistency but is not a theorem
prover. The executable abstract model and bounded type-graph enumeration are
finite checks. The formal notes distinguish these from proof obligations.

## Completion criteria for this first stage

The deliverable is a reviewable literature comparison, explicit candidate
claims, a reproducible baseline experiment, and recorded limitations/findings.
It is not a completed paper or a benchmark comparison against Koka. The follow-up
fixes the public-release counterexample, checks continual-arrival fairness in C,
and measures compiled Minyar with independent arrivals and stack-admission
ablations. These remain finite experiments, not a universal space/latency proof.
