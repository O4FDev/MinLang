# Explicit aggregate memory for Linux tests

`tools/test-memory-budget.py` is an experimental, explicitly selected Linux test
launcher. Ordinary Make checks continue to use `scripts/with-limits.sh` and its
768 MiB per-process virtual-address limit. Merely building this helper does not
select a different policy. The Go dependency update remains separate from this
launcher and requires real protocol qualification.

The `aggregate-v1` profile bounds kernel-charged memory for one command and all
its descendants, with swap disabled and group OOM killing enabled. This includes
the controller's anonymous, file-cache and kernel charges. It is a different
accounting scope from virtual address space or summed RSS. Sparse virtual
reservations need not consume the charged budget; descendants share one budget.
The native guardian remains outside that budget.

Build and run the focused acceptance cases on a provisioned Linux runner:

```sh
make check-test-memory
```

The target is optional and is not a dependency of ordinary `check` or
`check-portable`. It deliberately fails when the required facilities are absent.
Do not run these fixtures on an unapproved shared build host.

To wrap one already-built test executable, retain the existing limiter outside
the launcher:

```sh
mkdir -p build/test-memory-results
zsh scripts/with-limits.sh python3 tools/test-memory-budget.py \
  --profile aggregate-v1 --memory-bytes 805306368 --wall-seconds 900 \
  --helper "$PWD/build/test-memory-budget" \
  --evidence-root "$PWD/build/test-memory-results" \
  -- ./build/tooling/tests/http2-test
```

Each invocation creates a unique transient user service and private evidence
directory. Its empty delegated unit root contains the guardian in `control` and
the command in `job`. The helper configures and reads back `memory.max`,
`memory.swap.max=0` and `memory.oom.group=1` before native `clone3` admission.
Only the admitted child replaces its captured soft address-space limit with
the captured hard limit. An inherited finite hard limit remains finite. All
other resource limits, actual niceness, umask, affinity, groups, working directory,
environment and standard streams are preserved or checked before exec. The
command requires an explicit path; there is no PATH lookup or shell parsing.

The backend requires Linux LP64 with its sixteen-resource ABI, usable clone3
and pidfds, cgroup v2 memory/swap/OOM/kill interfaces, systemd 255 user delegation
and a private owned `XDG_RUNTIME_DIR`. Python 3.11 or newer must provide byte
environments, pidfd support and `hashlib.file_digest`. Control/helper/evidence paths currently
accept only absolute ASCII letters, digits, `/`, `.`, `_` and `-`; target argv,
environment and cwd remain literal non-NUL byte strings. Only descriptors 0–2
are passed to exec. The manager must support the caller's hard resource ceilings
and supplementary groups. Denied setup, admission or state restoration fails
before payload exec; no alternate backend or unbounded fallback runs.

A running user manager can retain stale supplementary groups after account
membership changes. Qualification observed an SSH caller with groups 986, 988
and 1000, while its existing manager lacked group 986 (`ascii-streaming-audio`).
The exact credential check rejected the launch before admission or exec. The
runner owner reconciled the dedicated box's manager after confirming its work
was idle; restarting that user manager refreshed its group set and the same
launch passed. Reconcile this provisioning mismatch at the runner boundary.
Keep the group check; the launcher never silently drops groups or changes them.

This is containment for cooperating same-UID repository tests. The same UID can
deliberately change its delegated controls, just as a payload can raise the old
soft AS limit to its inherited hard ceiling. It is not a hostile-code sandbox
and does not set a general HugeTLB policy.

The guardian owns target deadlines, a two-second TERM grace and recursive cgroup
kill/empty/removal. It cleans remaining descendants even after a normal leader
exit. Client lifetime is monitored by pidfd and a private socket; systemd owns
whole-unit teardown after guardian death and an independent runtime lease.
Uninterruptible kernel tasks can still prevent timely cleanup. Incomplete
cleanup or evidence fails the run and retains artifacts for lease-owner review.

Private retained evidence includes the caller snapshot, exact binary request,
guardian result, stop-post manager result, client verdict and manager logs.
The request contains the environment; do not publish it wholesale. Leader raw
wait status, pre-exec error, target deadline, cancellation, OOM counters and
manager outcomes are separate facts. Literal target exits 124/125/137 are not
classified as timeouts merely from their numbers. `oom_kill` alone can include
ancestor/global OOM; local `oom` and `max` counters supply separate evidence.

`memory.peak` is charged memory, not RSS. Native leader rusage excludes other
descendants; optional cgroup CPU statistics have their own scope. Timing the
Python client with `/usr/bin/time` does not measure the manager-spawned workload.
The shared check runner needs its own metadata/accounting adapter before broad
integration. Do not clear `LIMITED` globally or reapply its AS cap inside an
admitted aggregate command.
