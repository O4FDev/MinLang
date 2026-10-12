# WS4 files track

Implementation worktree: `ws4-files`, branch `ws4/files`; frozen base `bf9c0e9`.
No rebase, push, merge or downstream project edits. Parent owns Windows admission and independent review.

- `8283581`: bounded ranged reads, including huge requests at EOF, invalid descriptors and sparse offsets above 4 GiB.
- `35c7378`: POSIX preallocate + one-shot durable zero-file preparation. The worker owns a CLOEXEC duplicate, uses
  unmanaged storage, publishes sticky errors and signals a nonblocking completion socket. Typed generation handles
  reject stale/cross-kind use. Stop joins and cleans up deterministically. `library/files.min` declares the API.
- Mandatory native/sanitizer gates are in `build-support/files.mk`; all new host sources have additive catalogue entries.
  `tests/files-eventloop.min` runs the public API through the real readiness loop, including closing the caller descriptor.

Qualification of exact implementation commit `35c7378a1faf04785d3b5033e11766f1b1748b80`:

- Small Mac: `python3 tests/files-focused.py`: 68 O0/O2 controls; `--sanitize`: 34 ASan/UBSan controls.
  Linux-only procfs controls are not counted on Mac. Existing `files-review.c`: 30 O2 cases; `files-sync-failures.c`: pass.
- Linux Boat: only `bx_ppv9fjr7:/home/user/ws4/files-r2`; source/build copied from immutable baseline and overlaid with
  the eight committed files, verified by mode/SHA/source-commit manifest. Baseline compiler SHA256
  `f4f589328d1b53b8cf92c9aa8b0da1f5168bca1b4e8cf9198ff1b542cc59212b`; unchanged runtime source SHA verified.
  Clang 18.1.3, x86_64 Linux. `python3 tests/files-focused.py`: 70 controls; `--sanitize`: 35 ASan/UBSan/LSan controls.
  Retained files review: all 30 cases at O0/O2/sanitize, and stable-storage sync-failure fixture at O0/O2/sanitize passed.
  Boat command `cmd_sgywvx4deafa`, exit 0. Reproduction: `python3 /home/user/ws4/files-r2/qualify.py`.
- `git diff --check`, catalogue validation and actual Make native/sanitizer prerequisite inspection passed.

Exact commands, environment, exits, source/tool provenance and original logs are under `ws4-files-evidence/`.
No active background process. No sandbox lifecycle actions or paid spend.

Remaining blockers: Windows backend/driver routing and Windows platform qualification (not begun this round);
independent parent review; parent performance/crash durability checks and final integration after Phase1 readiness.
The POSIX-stage focused runner deliberately fails on Windows until the backend exists, rather than silently skipping.
