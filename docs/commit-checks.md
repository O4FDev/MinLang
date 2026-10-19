# Local commit checks

Run `make install-check-hook` once in a checkout to enable the pre-commit hook.
Each commit runs a focused core language gate and the existing checks for changed
library modules, including their transitive dependents. Push and pull request CI
continues to run the complete suite, including sanitizers, reference corpora,
platform checks and optimization matrices. `tools/land.min` retains its full
pre-push matrix.

Use `make check-commit-plan` to print the selected targets and reasons without
running them. `make check-commit` runs the same checks as the hook.
`make check-core` runs the local core gate against the current working tree.

The local core gate includes smoke, diagnostics, conformance, runtime units,
module loading, core standard modules, and the core compiler behavior profile.
It also includes the language ergonomics and nitpick language checks when
present. The compiler behavior profile preserves its existing O0 and O2 cases
and rejection assertions. Large compiler corpora and model matrices remain in
the full remote gates. Compiler, bootstrap and core runtime edits use this
bounded local profile.

Module selection uses the union of imports in HEAD and the staged tree, including
platform and architecture variants. Native implementations select their declared
module owners. Every affected module has an explicit mapping to complete existing
check targets. New modules, unknown paths, shared tooling/build changes, unmapped
test changes and missing coverage mappings fall back to `check-portable` plus
core. The preview explains every fallback. Some foundational modules affect much
of the library and consequently select many checks.
Changes to this local workflow run its selector, snapshot and hook regression
checks alongside core.

The hook checks a private snapshot of Git's active index, including temporary
indexes used by `git commit -a` and `git commit --only`. Unstaged edits stay in the
working tree. Private snapshots and incremental build artifacts live under
Git's `minyar-commit-check` directory; no stash or reset touches the working tree.
The planner and build rules also come from the staged snapshot. When the planner
is deleted, its HEAD version supplies the policy. For historical revisions that
predate this workflow, the working-tree planner supplies a bootstrap policy and
the hook reports that fallback.

The first run needs a compiler build. Later runs reuse unchanged build artifacts.
On macOS, local commit checks use the existing interactive scheduling mode while
retaining CPU, memory and output limits and the low nice priority.
An index change during checks rejects the result so a different staged tree
cannot accidentally inherit it. Failed checks block the commit and retain logs
and JSON results under the snapshot's `build/commit-checks/` directory.

The installer preserves existing hooks: if a different hooks directory, existing
pre-commit hook or another active default hook is configured, it stops and tells
you to invoke `sh tools/check-commit.sh` from that hook instead.
