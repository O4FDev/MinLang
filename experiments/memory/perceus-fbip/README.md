# Perceus FBIP evidence

These JSON/Markdown/Python files preserve the isolated reconstruction experiment. The external archive and `.perceus-measurement-transfer` are not versioned. Existing `experiments/memory/frames-instructions.py` is the pinned hardware-counter implementation (same SHA256 recorded in instructions JSON).

The measured feature avoids 10,000 allocations and 320,000 requested record bytes in a unique reconstruction loop, adds 10,000 RC increments through the shared helper, and leaves persistent aliases allocating safely. Zero eligible real compiler/product sites: no workload speedup claim. True eager self-compile 3,258,832,047 -> 3,258,892,625 instructions. Historical 171M is not comparable.

`perceus-fbip-instructions.json` preserves every warmup/sample PMU count and enabled/running time, exact input/runtime/protocol/producer hashes and source/product revisions. `perceus-fbip-comparison.json` contains before/after ratios; counts JSON has all 16 O0/O2/legacy/scope generated-code executions and full cleanup. Timings JSON retains all native paired observations and checksums. Sites JSON proves zero eligible calls in real graphs.

Reproduction uses the frozen assigned-primary artifacts under `build/perceus-measurement-20261020`; exact leased-BX commands and interpretation are in the measurement report. The scripts refuse overwrite of first-run evidence. The external full archive remains SHA256 aafbcc1e65f059ab1edca73a2cef09b3d6f7ba8650db9f185d83fbe4f4ef2654.
