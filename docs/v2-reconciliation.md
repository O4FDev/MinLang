# v2 reconciliation (2026-10-10)

`v2` brings together every line of work that was spread across branches and
worktrees. This page says what each branch held, how they overlapped, and what
was left out.

## Step 1: nothing uncommitted was lost

Every dirty worktree was committed onto its own branch before anything was
merged. Each snapshot is one commit named `wip: snapshot <branch> before v2`:

| Worktree | Branch | Snapshot |
| --- | --- | --- |
| `~/Projects/Minyar-Lang` | `minecraft` | `f0c0ffa` (302 paths, ~590 MB, mostly `research/` and `evidence/`) |
| `~/.t3/worktrees/Minyar-Lang/t3code-45fe5b4e` | `t3code/review-peer-language-tests` | `fd0857a` (peer-language tests) |
| `~/.t3/worktrees/Minyar-Lang/t3code-d518f238` | `feat/native-macos-apps` | `67376de` |
| `~/Projects/minyar-bakeoff/leaky` | `wip/bakeoff-leaky` (new, was detached) | `9956a0a` |
| `~/Projects/Minyar-Lang-appkit` | `feat/appkit-app-apis` | `f2f06cb` |
| `~/Projects/Minyar-OS` | `feat/minyar-os` | `bfc6f8c` |

The `.gitattributes` rule `* text=auto eol=lf` made git store a few
`research/.../*.png` files (which are not real PNG images) with LF line endings.
The files on disk were not changed.

## Step 2: the branch map

Three of the new snapshots turned out to have exactly the same tree as commits
already preserved on `integrate/desktop-tests-minecraft` on 2026-10-06:

- `minecraft` snapshot `f0c0ffa` = `0cae542` ("preserve current minecraft work")
- `feat/native-macos-apps` snapshot `67376de` = `600736c` ("preserve current desktop work")
- `t3code/review-peer-language-tests` snapshot `fd0857a` = `495c0bc` ("preserve current tests work")

So `integrate/desktop-tests-minecraft` (`0be01e7`) already contained the
Minyarcraft, native desktop and peer-language test work, plus 13 commits of CI
and Windows fixes. It passed all 17 CI jobs on 2026-10-06. It became the base of
`v2`.

| Branch | Status | Notes |
| --- | --- | --- |
| `integrate/desktop-tests-minecraft` = `feat/desktop-canvas` (`0be01e7`) | **Base of v2** | minecraft + desktop + peer tests + CI fixes |
| `minecraft` (`f0c0ffa`) | Contained | tree identical to `0cae542` |
| `feat/native-macos-apps` (`67376de`) | Contained | tree identical to `600736c` |
| `t3code/review-peer-language-tests` (`fd0857a`) | Contained | tree identical to `495c0bc` |
| `feat/appkit-app-apis` (`f2f06cb`) | **Merged** | AppKit layout/styling/controls/app APIs, NSURLSession `http`, `json`, `--icon/--resources`, character-literal module fix, `check-http` |
| `feat/minyar-os` (`bfc6f8c`) | **Merged** | Minyar OS (`os/`), freestanding runtime, `machine`/`device`/`net`/`tls`/`crypto`/`json`, private fields, `parallel function`, `Bytes(Text)`/`Text(Bytes)`, `randomBytes`, repeatable `--library`, `--freestanding`, `check-tls` |
| `bakeoff/astra-cycles` (`2905dcc`) | **Ported by hand** (see below) | won the cycle-collection bake-off |
| `bakeoff/sol-cycles` (`73c0749`) | Left out | see below |
| `wip/bakeoff-leaky` (`9956a0a`) | Left out | the bake-off's deliberately leaky control |
| `fix/ci-runner-portability` (+ origin) | Superseded | every hunk is in `0be01e7` (`.gitattributes`, core pattern, `_O_BINARY`, `CommandLineToArgvW`, MSYS2 toolchain lookup in `ci.yml:107-139`) |
| `codex/ci-runner-portability` (`5baa102`) | Contained | ancestor of `0be01e7` |
| `fix/ci-coverage-gaps` (+ origin) | Contained | ancestor |
| `research/bounded-reclamation`, `main` (`8e52316`) | Contained | ancestor |
| `t3code/recent-research-update`, `t3code/minyar-macos-desktop-apis`, `origin/minecraft` (`c2c9eff`) | Contained | parent of `0cae542` |

## Step 3: how the merges were resolved

`feat/appkit-app-apis` and `feat/minyar-os` both fork from `0be01e7`. They share
ten files:

- `library/json.min` and `tests/modules/character-literals/*` are identical on both.
- `compiler/compiler.min`: appkit's only change (character literals in module
  export) is also in minyar-os, hunk for hunk. Git merged it cleanly.
- `tests/run-module-tests.sh` and `tests/packages/json.min`: minyar-os's
  versions are strict supersets, so they were taken.
- `tools/clang-driver.py`: both add an `elif` for their native library
  (`http` → `runtime/native/http.m`; `machine`, `net` → `runtime/native/net.c`).
  Both were kept.
- `library/http.min`: **the two competing `http` packages.** They share the
  blocking API (`Response`, `get`, `post`, `request`), but:
  - appkit's version runs on NSURLSession, validates certificates and adds the
    streaming handle API (`start`, `wait`, `finished`, `read`, `close`, ...)
    that the Atacama desktop app depends on. It only works on macOS.
  - minyar-os's version is portable HTTP/1.1 in Minyar over `net` and `tls`.
    It blocks, does not validate certificates and has no chunked decoding.

  Both are kept as one package with two backends, chosen by the package
  search path in the same way `library/arch/arm64` replaces `machine`.
  minyar-os's portable client is `library/http.min`, and appkit's NSURLSession
  client is `library/platform/macos/http.min`, which `./minyar` searches first
  on macOS. Programs write `use "http"` everywhere. `./minyar --library library`
  selects the portable client on macOS, which `tests/tls-local.py` does. Only
  the macOS backend can stream: packages cannot hold state, so a portable
  `start` would need a request record instead of an integer handle.

## The cycle-collection bake-off

On 2026-09-29/30, two agents (Astra and Sol) were given the same task: lift
Minyar's rule that rejects programs that can form reference cycles, and reclaim
cycles within a bounded amount of work.

- On the hidden holdout suite in `~/Projects/minyar-bakeoff/holdout/`, both
  scored 55/56 correctness, 16/16 ASan and 8/8 memory, and both passed 39/39
  oracle fuzz runs.
- A blind research review scored Astra 48 and Sol 43. Astra's per-batch work
  bound holds and its methodology is reported more honestly. Sol's
  per-operation bound is broken.
- On programs without cycles, Sol costs far more. On `chain_8_100000_release`
  it retired 15.46G instructions, against Astra's 2.85G and the baseline's
  2.51G.

**Astra is ported, but not merged into v2.** The compiler moved from `src/`
to `compiler/` and the runtime was rewritten after the bake-off, so the port
was done by hand on branch `port/astra-cycles` (recorded as a merge of
`2905dcc`). On v2 it made programs that never form a cycle slower: up to +23%
instructions and +76% peak memory at first. After two rounds of work (cycle
metadata only for types that can reach themselves, and a smaller header) the
remaining cost is in v2-performance.md. Merging means accepting that cost in
exchange for supporting cyclic data, so it is left as a decision.

**Left out:**
- `bakeoff/sol-cycles`, for the broken work bound and the 3.8-12x cost on
  allocation-heavy acyclic programs. Its local trial-deletion design is worth
  revisiting later as a way to make Astra's global scan local.
- `wip/bakeoff-leaky`, which turns both cycle errors into `return` so that
  cycles compile and leak. It exists to show the holdout's memory tests catch
  leaks (it scores 2/8 on memory) and was never meant to ship.

## Large research data

`0cae542` and `495c0bc` commit about 600 MB of research evidence (`research/`,
`evidence/`, `docs/research/exhaustive/`). Tests under `tests/` read some of it,
and it was already pushed to origin on `integrate/desktop-tests-minecraft`, so
v2 keeps it. Moving it to Git LFS or a separate repository would be a separate
decision.

## Phase 2 branches (made tonight)

All three are merged into v2; their worktrees can be removed once v2 is reviewed.

| Branch | Worktree | Contents |
| --- | --- | --- |
| `perf/macos-list` | `~/Projects/Minyar-Lang-list` | changes 1-12, 15, 16, 18 and 19 in `docs/v2-performance.md`, the review fixes, and the merge of the two below |
| `perf/craft-frames` | `~/Projects/Minyar-Lang-craft` | Minyarcraft `--benchmark`, cached GL draw state (change 13), the two-comparison guard (change 14) |
| `perf/text-stream` | `~/Projects/Minyar-Lang-stream` | `macos.textView` and `appendText`, `http` without URL cache, button redraws (change 17) |
| `port/astra-cycles` | `~/Projects/Minyar-Lang-astra` | the Astra cycle collector on v2 as measured earlier. Not merged |
| `port/astra-cycles-v2` | `~/Projects/Minyar-Lang-astra-v2` | the same, brought up to v2 a836412 (in-place appended for traced Lists). Not merged: see `research/cycles/README.md` on that branch |

The Atacama app (`~/Projects/Atacama-desktop-app`, made a git repository
tonight) has `v2-list` (History in `macos.list`) and `v2-stream` (streamed
answers in `macos.textView`; needs this v2).
