# Frozen foundation comparator

`foundation-baseline.min` is the exact output of
`python3 scripts/build-closure-compiler.py --baseline OUTPUT` on unchanged
`bf9c0e9bb6ced1f40d8d7c51bedca769b05909c0` before the pinned-source change.
The prior builder removed callback dispatch and reversed the later parallel
signature check before validating this same hash:

`a5f30a7954381231fbe04a712b72bd9663d1bd7082c667fef851b739ec63c3cf`

The hash remains embedded in the builder and is checked over raw bytes before
output publication. Missing/modified frozen input fails; there is no fallback
to current source. The output preserves those bytes on all platforms.

This file is used only by the historical performance/identity comparator.
The current ordinary compiler and optional module/callback/Result frontends
continue compiling maintained sources. New language features belong there,
not in this frozen source. The snapshot avoids composing inverse adapters for
new workstream changes without redefining the original comparison baseline.
