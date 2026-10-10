# Prospective reclamation acceptance suite

These are intentionally failing tests for a stronger runtime/event-loop
contract. They are **not regressions against the current public contract**:
current K bounds a service batch, not all service points in an event.

Passing finite tests cannot establish perfection, superiority over every
language, or absence of all tradeoffs. The targets below establish concrete
requirements, retain failures, and reject missing evidence. They make no
universal performance or hard real-time claim. In particular, the current
system allocator and operating system remain outside a CPU-time bound.

## Run

```sh
# Intentionally RED: real runtime under three heaps and three K values.
make check-reclamation-acceptance
make check-reclamation-acceptance-sanitize

# GREEN: positive controls and mutations of the evidence/acceptance policies.
make check-reclamation-acceptance-harness

# Intentionally RED: revalidate retained studies and assess comparative claims.
make check-reclamation-acceptance-evidence
```

The red targets are not dependencies of `make check`. Each command retains a
fresh result under `build/`. An explicit `--output` must name a new destination;
old evidence is never overwritten. `make clean` removes this ignored evidence.
Runtime acceptance exits 1 for failed requirements and 2 for build/tool errors.
Do not use Python `-O` or `PYTHONOPTIMIZE`: assertions are required and disabling
them is rejected. Sanitizer runs use ASan/UBSan, not LSan; explicit final managed
and backing-allocation accounting checks storage recovery.

For a fast iteration:

```sh
python3 research/reclamation/test_acceptance.py --profiles system --budgets 32
python3 research/reclamation/test_acceptance.py --filter 'scope/*'
python3 research/reclamation/test_acceptance.py --list
```

There are 131 parameterized scenarios, expanded across system/fixed/lazy heaps
and K1/K8/K32: **1,179 executions per native or sanitizer campaign**. These are
not 1,179 independent design requirements or statistical repetitions.

## Deterministic contract

| Requirement | Cases and failure prevented |
| --- | --- |
| Shared queued-work allowance | 13 operation families at event budgets 0, 1, 7, 32; repeated allocations, Text creation, records, List append/growth/replacement, fields, locals, temporary chunks, statement cleanup, heap/stack frames, releases and explicit polls cannot each replenish the allowance. |
| Independent progress accounting | A large old record owns a live sentinel once per field. Actual cursor advancement and reference drops cross-check cumulative poll work. Function results and final storage recovery remain checked. |
| Scope composition | Nested scopes respect an exhausted or partly spent parent and their own tighter cap; a new event gets fresh credit; ending an event restores ordinary polling. Explicit polls must use available credit, ruling out a collector that simply stops working. |
| Interruptible idle service | Caps 0, 1, 7, 32, 97; readiness immediately or after 1, 2, 5 checks. At most one K batch between checks. Zero budget, existing readiness, no debt, or an active event permits no idle work. |
| Finite capacity recovery | 128 cycles per case; widths 1/7/64 and bursts 1/4/16. Each idle opportunity supplies exactly the generated field/finalization work. All storage and sentinel ownership must recover within that opportunity. |
| Safety retained | Live shared aliases, final Text views/backing roots, zero polls, overwritten stack storage, a 16,384-node chain and a shared DAG, each with poll budgets 1/8/32. |

The event allowance counts **queued** work. Mandatory synchronous owner visits
and immediate leaf release remain separate costs. An event's full cleanup cost
is not bounded by this allowance alone. The performance/resource gates and
existing stack/ownership suites remain necessary. No test asserts that required
stack cleanup may leave pointers to expired stack storage queued for later.

Finite recovery cases deliberately leave no debt between cycles when passing.
If one fails, the fixture drains outside the measured opportunity to avoid
turning the remaining diagnostics into OOM. The failure is retained, and the
test explicitly requires the full amount of cleanup to occur **inside** the
declared opportunities. This cleanup cannot turn a failed window green.
These cases do not prove stability under unlimited arrivals or arbitrary graphs.

## Connecting an implementation

`acceptance_adapter.h` represents today's missing event/idle integration:
boundaries do nothing and idle opportunities perform no cleanup. Capability
checks explicitly fail. Other event tests still execute the actual runtime
and show its budget overrun. These defaults are not a proposed fix.

Supply a self-contained adapter header to map the test interface to a candidate:

```sh
python3 research/reclamation/test_acceptance.py --adapter /absolute/path/candidate.h
```

The header is included after the runtime in the fixture. It defines:

```c
#define ACCEPTANCE_HAS_EVENT_SCOPE 1
#define ACCEPTANCE_HAS_IDLE 1
static void acceptance_event_begin(size_t queued_budget);
static void acceptance_event_end(void);
static size_t acceptance_idle(size_t max_work,
                             int (*ready)(void *), void *context);
```

These names are a **test seam**, not a frozen production ABI. Begin/end scopes
nest. Work consumes credit from every enclosing scope; inner credit cannot
refill outer credit. Idle returns actual queued units completed, checks readiness
before service and between batches, and does no work inside an event scope.
The callback is a deterministic stand-in for the host's event/deadline check;
it does not simulate a wall-clock deadline or promise allocator preemption.

The runner freezes runtime sources and adds one cumulative poll observer to the
copy. It does not change runtime scheduling. Changed instrumentation sites cause
an error requiring review. The source, observer, adapter hashes, commands, raw
outputs and per-case reasons are retained. A header with relative dependencies
must arrange for those dependencies to exist in the snapshot; prefer a
self-contained adapter for reproducibility.

`test_acceptance_harness.py` installs a small reference implementation only into
temporary snapshots. It passes the scenario matrix at K1/K8/K32. That establishes
that the assertions are satisfiable; it is not performance evidence or a shipped
runtime change. Policy mutations test budget overruns, underreported work,
stalled reclamation, lost/reset credit, ignored readiness, hidden teardown work,
leaks, malformed evidence, edited artifacts and incomplete phase accounting.

## Comparative acceptance

```sh
python3 research/reclamation/test_acceptance_evidence.py \
  --timing build/event-load-timing \
  --diagnostic build/event-load-diagnostic \
  --external /path/to/external-comparisons.json
```

The default candidate is `current-k32-heap`. Internal baselines are
`fifo-k32-heap` and `eager-k0-heap`; eager changes owner representation and remains
a whole-profile comparison. C, Rust and Zig form an explicitly declared initial
external reference set, configurable with `--competitors`. No external baseline
has been implemented or measured by this test addition. Missing external data
fails coverage rather than being silently skipped.

Before comparison, the checker replays every independent event oracle and
validates source, compiler, LLVM, binary, scheduler and raw trace hashes using
the existing study validator. Timing and diagnostic implementations must match.
Every seed/arrival/size is compared separately. Required arrival coverage is
10/50 microseconds, steady/16-event bursts, with at least three distinct seeds.
Diagnostics must cover the event counts, widths and seeds used in timing.

No measured metric may regress against any selected matched baseline:

- Ordinary response p99 and p99.9, plus maximum response across all events.
- Mean service of the first two events after a rebuild, which ordinary service
  p99 can hide because these events comprise less than 1% of ordinary traffic.
- Event plus quiet-recovery service, lifecycle duration, and complete active
  lifecycle service when its required phase ledger exists.
- Boundary dead/combined managed-owner bytes, transient managed/owner peaks,
  peak RSS, allocation count and cumulative allocated bytes.

At least one strict response-p99 win per baseline is also required; equality
everywhere is not superiority. Faster latency cannot compensate for more memory
or work in another column. Zero baselines are handled without division or
discarding positive regressions. Every recovery window must succeed.

These are intentionally stringent **observational gates**, not significance
tests or timing assertions suitable for arbitrary shared CI machines. A noisy
max or a small ratio can fail them; investigate and collect another complete,
predeclared campaign rather than deleting samples or declaring a code defect.
Three seeds cannot establish a rare-tail guarantee. Passing on this one workload
would still require controlled replications and additional workload families
before a broader claim. The suite deliberately reports its finite scope.

## Closing the measurement gaps

Timing run records can add `phases: {"path": "phases.json", "sha256": "..."}`.
This JSON array covers the entire interval from setup through teardown without
gaps or overlap. Entries have `kind`, `start_ns`, `end_ns`, with `event` for event
entries and `cycle` for recovery entries. Kinds are `setup`, `event`, `idle`,
`recovery`, `teardown`, `wait`, `overhead`. The event trace supplies time origin;
setup can start at a negative timestamp. The first phase is setup, the last is
teardown ending at `summary.lifecycle_ns`. All event/recovery intervals must
exactly match their raw traces. Every duration except `wait` contributes to
active service, including idle reclamation and harness overhead.

Diagnostic run records can add a `resources` object with
`scope: "setup-through-teardown"`, `peak_rss_bytes`, `peak_managed_bytes`,
`peak_owner_bytes`, `allocation_count`, and `allocated_bytes`. Counts must be
nonnegative integers, RSS positive, and peaks at least the observed boundary
values. These measurements include intra-event peaks that boundary traversal
alone misses. Their instrumentation must be independently reviewed; validating
a manifest does not prove that a program truthfully measured what it reports.

The existing studies lack both the full phase ledger and these resource
counters. They therefore cannot pass the full no-regression evidence gate even
if their existing percentile columns improve. Do not fill missing fields with
invented zeros or label cleanup as waiting to pass a test.

## External evidence format

External adapters must execute the same `event_workload_v1` semantics and produce
the existing event/recovery CSV schemas, including every expected output and
independent live/dead accounting in diagnostic runs. The checker executes no
supplied shell commands. A manifest has:

```json
{
  "schema": 1,
  "workload": "event_workload_v1",
  "host": "exact native campaign host value",
  "hardware": "exact native campaign hardware value",
  "allocator": "system",
  "lto": false,
  "runs": [{
    "implementation": "rust",
    "mode": "timing",
    "toolchain": "recorded compiler version",
    "build_command": ["compiler", "recorded arguments"],
    "run_command": ["binary", "recorded arguments"],
    "sources": [{"path": "source", "sha256": "actual digest"}],
    "binary": {"path": "binary", "sha256": "actual digest"},
    "events": {"path": "events.csv", "sha256": "actual digest"},
    "recovery": {"path": "recovery.csv", "sha256": "actual digest"},
    "phases": {"path": "phases.json", "sha256": "actual digest"},
    "summary": {}
  }]
}
```

`summary` uses the existing `event_study.analyze` schema, not an empty object;
the schematic example omits the fields for readability. Diagnostic runs add the
resource object above. Paths resolve relative to the external manifest. Every
candidate seed/arrival/size requires a matched external run in the same mode.
Duplicate runs, missing provenance, changed artifacts, mismatched outputs,
different host/allocation/LTO settings and failed recovery are rejected.

Passing requires actual comparable implementations. Faster code that changes
snapshot visibility, omits output computation, leaks the old graph, changes
sharing semantics, or excludes final cleanup is not an admissible baseline or
candidate. Source/provenance review remains necessary alongside executable
oracles. These tests address reclamation; they do not certify the whole language,
its compiler, libraries, platform support, or ergonomics.
