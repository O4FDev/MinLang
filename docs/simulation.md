# Replaying a difficult night

Import `simulation` to run a single-owner model of disk, network delivery and
monotonic time. It performs no host I/O and starts no threads. Production code
needs an I/O boundary that can call this model instead of its real driver.
Importing the module does not intercept ordinary `files`, `net` or clock calls.

```minyar
use "simulation" as sim

let world = sim.create(42)
let file = sim.openFile(world, "/db/log", true)
sim.syncDirectory(world, "/db")
let write = sim.submitWrite(world, file, 0, Bytes("committed"), 10)
let written = sim.next(world)
let flush = sim.submitSync(world, file, 20)
let durable = sim.next(world)
sim.crash(world)
print(Text(sim.read(world, sim.openFile(world, "/db/log", false), 0, 9)))
```

The result is `committed`. Check completion `result` values before acknowledging
real work. A write submission copies its payload. It takes effect only when
`next` completes it; a sync covers writes completed before the sync. Submit a
sync after its required writes have completed. Two operations submitted together
may complete in either order, including a sync and a write to the same file.

`submitRead`, `submitWrite` and `submitSync` return unique operation IDs.
`submitPacket(world, channel, bytes, delayMs, token)` and
`submitTimer(world, delayMs, token)` add delivery and timer events. `next` returns
`Completion { id, token, kind, target, result, data, at }`. The earliest deadline
runs first; the seeded scheduler chooses among equal deadlines. A read returns
its byte count and a copied buffer; writes return their count; a sync or timer
returns zero. Errors are negative codes. `pendingCount` counts outstanding
operations; `cancel` removes one by ID. Calling `next` on an empty queue stops
with a clear message. IDs are not reused after cancellation or a crash.

Use `choose(world, count)` for application scheduling and generated workloads.
The generator is a bounded Park–Miller sequence with rejection sampling.
`choices(world)` returns independent `Decision { options, selected }` values.
Run the same scenario with `replay(seed, decisions)` to reproduce its choices.
Replay rejects a different choice count, an invalid selection or an exhausted
script. Check `finished(world)` afterward to reject an unused suffix too.
`fork(seed, decisions)` replays `decisions` exactly, then continues with fresh
choices from `seed`, as if created by `create(seed)`. Inside the prefix it
rejects mismatches exactly as replay does. The same seed and prefix give the
same run, and different seeds diverge only after the prefix. An explorer can
therefore branch many continuations from the moment a recorded run first
reached a rare state, instead of hoping a new seed reaches it again. The
transcript starts with `fork N`, the prefix length.
The seed alone reproduces a run only when the application and input are the same.
A decision script checks choice counts, not program identity: preserve the
source revision, fault scenario and input with a failing script. `transcript`
returns a copy of the operation log for retained evidence.

## Deterministic functions

A seed reproduces a run only if nothing else can change it. Mark the function
that runs one universe `deterministic`, and the compiler proves it:

```minyar
use "simulation" as sim

deterministic function universe(seed: Integer): Integer {
    let world = sim.create(seed)
    sim.advance(world, sim.choose(world, 10))
    return sim.now(world)
}

print(universe(7) == universe(7)) // true
```

The compiler follows every call the function can make, including calls into
other modules, generic instances, contract helpers, closures and the
initializers of the globals it reads. Nothing reachable may use a host clock,
randomness, files, sockets, process arguments, the environment, threads,
inline assembly, volatile machine access, raw addresses
(`cAddress`, `cAt`, `parallelEntry`) or native code. Safe `parallel for` loops
and their reductions are allowed, and their bodies are checked like any other
call: each iteration writes only its own index or window and partial sums combine in
chunk order, so the result is the same on every schedule and thread count. If
several iterations stop, which one reports first can depend on the schedule;
`minyar sim` runs universes with `MINYAR_PARALLEL_THREADS=1`, so there it is
always the lowest failing iteration. Pure natives are allowed
when they match their standard library declaration exactly: `math`, `unicode`,
`aes`, `securecrypto`, checked Integer overflow and `json` number parsing. A call through a callback value counts
as a call to every function whose address the program takes with that
signature, so a callback built by the caller is checked too. Any reachable Map
operation also reaches the key hash, equality and copy functions of every Map
the program creates, because a Map built by the caller carries them. The error names the
whole path:

```text
error: deterministic function 'simulate' can reach the host clock: simulate -> onCrash -> cover -> monotonicNanoseconds (native "system")
  ...
  = help: called from cover (raftkv.min:230, column 10); use the simulation World's virtual time (simulation.now or simulation.wallTime) and pass the World in
```

The marked function must be a named Minyar function or record method. A
generic one is proved once per instance, with that instance's types, so
`deterministic function biggest<Item: Ordered>` fails for an `Item` whose
`compare` reads the clock and passes for every other. Its callers keep ordinary host effects,
so a driver can read arguments, time a run or write reports around the
proved part. The check reads the final LLVM module, adds no instructions or
runtime calls, and runs only when a program uses the modifier. Programs that
use it compile with the complete frontend instead of reusing incremental
module state.

### Deterministic callbacks

A plugin interface can require proved bodies with the callable type
`deterministic (A) -> B`. A parameter, field or List element of that type
accepts a function by name or an anonymous function, and the compiler proves
it where it is passed, exactly as for `deterministic function`. A call through
such a value is then known to be deterministic: it does not stand for every
function of its signature, so a host can call registered extensions from its
own deterministic code while other parts of the program take the address of
clock readers with the same signature.

```minyar
record Call { value: Integer }
record Registry { bodies: List<deterministic (Call) -> Integer> }
function Registry.define(body: deterministic (Call) -> Integer) { self.bodies.add(body) }
function twice(call: Call): Integer { return call.value * 2 }

deterministic function run(registry: Registry, value: Integer): Integer {
    let total = 0
    for body in registry.bodies { total = total + body(Call { value: value }) }
    return total
}

let registry = Registry { bodies: [] }
registry.define(twice)
registry.define(function(call) { return call.value + 1 })
print(run(registry, 10)) // 31
```

A deterministic callable value can be used wherever the plain `(A) -> B` is
expected. The reverse needs proof, so a plain value is rejected:

```text
error: this place needs a deterministic (Call) -> Integer, but this (Call) -> Integer is not known to be deterministic
error: function 'clocked', passed as deterministic (Call) -> Integer, can reach the host clock: clocked -> stamp -> wallClockMicroseconds (native "system")
```

The type has the same representation and call cost as `(A) -> B`; the proof
runs at compile time.

The proof covers effects, not every input. It does not track the contents
of a List, record or Map global that code outside the function changes, and it does
not make out-of-memory or stack exhaustion reproducible. Floating-point
`math` results are fixed for one build on one platform. `deterministic` is an
ordinary identifier everywhere except directly before `function` or a
callable type `(A) -> B`.

## Running many universes

In a project, put each scenario in `sim/NAME.min`. A scenario receives its
World and returns `""` for a correct run or a description of what went wrong:

```minyar
use "simulation" as sim

public function universe(world: sim.World): Text {
    sim.advance(world, sim.choose(world, 10))
    if sim.choose(world, 50) == 7 { sim.reached(world, "rare tide") }
    if sim.now(world) > 9 { return "the tide came in late" }
    return ""
}
```

`minyar sim` builds each scenario in the release profile and runs one World
per seed, `0..9999` by default (`--first`, `--seeds`); `--jobs` shares the
seeds between processes. The generated driver calls `universe` through a
`deterministic function`, so the command refuses a scenario that can reach the
host, and every reported run reproduces. A failure prints the lowest failing
seed with its message, replays its recorded decisions twice, saves them, and
exits with status 1. It also shrinks the failure within 2,000 replays: it
shortens the decision list, deletes runs of decisions and lowers selections,
following each candidate with `guide(seed, decisions)` (which reuses a recorded
selection even when the number of options has changed, modulo the new count),
and keeps any simpler list that still fails. It saves the shrunk run's World
`transcript`, one line per choice, operation, completion and crash. kvlog's planted failure shrank
from 9 to 3 decisions; a neo-db early acknowledgement from 23 to 10; a Raft
double-leader run from 2,540 to 1,117. `minyar sim NAME --seed SEED` reruns a seed and
`minyar sim NAME --replay FILE` reruns saved decisions. Because the proof does not cover
List, record or Map globals that universes change, `minyar sim` also reruns
the last seed of its first process alone and reports the scenario if that run
differs from the same seed after the earlier universes.

`reached(world, label)` marks a moment worth exploring from, such as a rare
state; `moments(world)` lists the labels a run reached, with the number of
decisions made before each. `minyar sim` reports every moment reached. With
`--explore`, half of the runs fork from a recorded moment instead of starting
fresh: they replay the decisions that first reached it, then continue with
the run's own seed. Exploration stops at the first failure and saves its
decisions. In the test suite's three-tumbler vault, plain seeds failed 48 times
in 1,000,000 runs; exploration failed within a median of about 610 runs over
ten starting seeds. Exploration helps when failures lie behind rare
intermediate states that the scenario labels; it cannot help with states it
never reaches or labels.

A scenario with timed faults can declare them as fault windows instead of
drawing each number itself. `windows(world, WindowLimits { most, kinds, nodes,
horizon, shortest, longest })` draws up to `most` values
`Window { kind, node, other, at, length }`: a scenario-defined kind, the node
it hits, a different node for faults between two nodes, a start before
`horizon` and a length from `shortest` to `longest`. A universe declares its
windows once, and `schedule(world)` returns them with the decision count at
which they were drawn. With `--explore`, a scenario that declares windows is
explored by changing them, as the 10-20 guided explorer did for raftkv. After
plain seeds (a tenth of each process's runs, at most 1,000), half of the runs
take a kept run and apply one to three changes: shift, resize or retarget one
window, change its kind, add a short window near another, remove one, splice
one from another kept run, or continue with a new random state. Kept runs are
those that reached a moment no earlier run reached, plus one run in a hundred,
and runs with rarely reached moments are picked more often. Every change stays
within the declared limits. `plan(stream, prefix, windows)` builds such a run:
it replays `prefix`, takes `windows` and continues from the random state
`stream`. A `Schedule`'s stream continues exactly like the run it came from.
The windows are recorded as the decisions that would have drawn them, so a
failure's saved decisions replay without the explorer.

On raftkv's planted forget-vote mistake (minyar-sim, up to four isolation,
cut and crash windows of 1–600 ms; 8-vCPU Linux box), plain seeds failed 12
times in 6,400,000 universes, about one in 530,000. In 64 independent
explorers of at most 100,000 universes each, 23 failed, after 5,215,606
universes in total: 4.4 failures per million, 2.35 times the plain rate
(one-sided p ≈ 0.01). Each explored universe cost about 8% more CPU time.
The 10-20 explorer looked stronger because it let a schedule grow to 12
windows while its random runs had at most 4. When the scenario declares up to
12 windows, plain seeds fail once in about 12,200 universes (523 in
6,400,000), and exploration is only modestly faster: 64 explorers took a
median of 5,200 and a mean of 9,700 universes to the first failure, against
8,500 and 12,200 expected from plain seeds (one-sided p ≈ 0.05). Scenarios whose planted mistakes fail most seeds gain nothing: kvlog's
fails 63% of seeds and neo-db early acknowledgement 98%, so both are found in
one or two universes either way.

`tests/neodb-sim` is such a project for the pinned production neo-db engine.
It sets `memory = "eager"`, which ran these universes about 1.5 times faster
than the default profile.
Each universe runs random autocommit statements, acknowledging each only once
its commit is durable, leaves one statement in flight, crashes keeping a random
prefix of every file, and checks the recovered rows against the acknowledged
history. `minyar sim --manifest-path tests/neodb-sim durable --seeds 5000 --jobs 4`
passed 5,000 universes in 243 ms on a 4-vCPU Linux box; the planted `early-ack`
scenario, which acknowledges before durability, fails most seeds with an exact
replay. `two-crashes` adds random checkpoints and a second power loss after
recovery, and tears every file in 512-byte sectors with `persistSectors`;
`transactions` also groups two to four statements in BEGIN/COMMIT, which must
recover all or nothing. Before each crash the live engine must hold the
acknowledged state, with or without the in-flight unit, and recovery is
compared row count and weight for every id. 100,000 `transactions` universes
passed in 17 s on 4 processes. In `group-commit`, up to three sessions each
leave a commit in flight; recovery must keep a prefix of them in commit order.

## A disk with explicit durability

`openFile(world, path, create)` returns a positive file identity, or negative
`ENOENT` (`-2`). The synchronous `read`, `write`, `resize`, `size`, `syncFile`,
`rename`, `remove`, `names` and `syncDirectory` calls let existing I/O facades
use the same model. Reads return empty Bytes on error; inspect `lastError`
immediately. Names are exact lexical paths; directories and aliases such as
`..` are not resolved. File identities belong to their world and remain attached
to the same file through rename or unlink. Restart application handles after a
crash. This module is a simulation boundary, not an operating system handle API.

File contents and directory names have separate durable copies. `syncFile`
preserves contents; `syncDirectory` preserves only that directory's direct-child
names. Durable publication is write → sync file → rename → sync directory.
`crash` restores durable copies, discards pending completions and clears armed
one-shot I/O faults. A queued operation never runs after that crash. Network
partitions and virtual clock state remain under scenario control.

By default unsynced writes are lost. To model a torn write, call
`persistPrefix(world, file, count)` before crashing: exactly that volatile prefix
overlays the durable contents, extending their length when needed. The existing
durable suffix remains. Sweep every prefix of a new WAL record, and include
zero and full length. `persistSectors(world, file, sectorBytes)` models a
power loss that persists unsynced sectors independently: the durable length
becomes its old value or the current one, and each sector whose volatile bytes
differ is kept or lost by its own World decision, so a seed replays the same
tearing. These are deliberately bounded models of persistence; they do not
model filesystem journals or hardware that lies about completed syncs.

`injectError(world, kind, negativeCode)` fails the next matching `READ`, `WRITE`,
`SYNC` or `PACKET` operation without its ordinary side effect. Different kinds
leave it armed; faults of one kind are consumed in order. `partition(world,
channel, true)` drops that channel's deliveries with `-110` until healed.
`jumpClock(world, deltaMs)` changes wall time while timers continue to use
monotonic `now`. `advance` accepts only a nonnegative monotonic delta. Checked
Integer arithmetic also bounds the virtual clock.

The model copies buffers and durable images and searches lists linearly. Files
are bounded to 16 MiB each; they are not sparse. The queue, history and transcript
consume memory proportional to the scenario. Keep worlds bounded and create
fresh worlds for independent seeds. These are explicit testing costs, with no
runtime cost in applications that do not call the simulator.

## One storage engine, two disks

Import `disk` to write storage code once and run it on either disk. `Disk` is
a capability with `open`, `size`, `read`, `write`, `resize`, `sync`, `close`,
`rename`, `remove`, `exists`, `syncDirectory` and `createDirectory`, each
returning a `Result` with an `errors.Error`. `disk.host()` implements it with
`files`; `disk.simulated(world)` implements it with this module's World, so
unsynced writes and unsynced names are lost in `crash`, and
`persistSectors` tears them. Make the engine generic over the disk:

```minyar
use "disk" as disk
use "errors" as errors
use "simulation" as sim

function save<D: disk.Disk>(storage: D, path: Text, data: Bytes): Result<Nothing, errors.Error> {
    let file = try storage.open(path, true)
    try storage.write(file, 0, data)
    try storage.sync(file)
    return storage.syncDirectory("/db")
}

let world = sim.create(7)
let storage = disk.simulated(world)
save(storage, "/db/state", Bytes("kept")).unwrap()
sim.crash(world)
print(storage.exists("/db/state"))   // true: the file and its name were synced
```

Each generic call is specialized for its disk, so the simulated build reaches
no host I/O and passes the `minyar sim` determinism proof, while production
calls `files` directly. File handles are Integers; after `crash`, open files
again as a restarted process would. The simulated disk's directories are
lexical, so `createDirectory` succeeds without recording anything.
[examples/kvstore](../examples/kvstore) is a complete write-ahead-logged
store on this interface, with a `minyar sim` universe that tears its log and
a SIGKILL test on the real file system; `make check-example-kvstore` also
checks that the simulation catches a planted missing directory sync.

## The database proof

`make check-simulation` checks replay, ordering, faults, durability and the
[harbour gallery](../examples/gallery/the-harbour-remembers.min) at O0/O2 with
ownership cleanup assertions. `make check-simulation-neodb` runs neo-db's actual
WAL, CRC and storage utility modules unchanged against a simulated `dbio` facade.
The pinned sources and provenance live under `tests/fixtures/neodb-simulation`.
The separate [manifest proof](simulation-manifests.md) checks real checkpoint
encoding, publication and recovery. These proofs do not qualify SQL transactions
or VM devices. The simulator is cooperative and explicit;
it neither explores arbitrary native thread interleavings nor replaces a real
kernel completion backend such as io_uring.
