# python source review batch 300d

This batch fully read 57 standalone test-source files. Other source roles: {}. These are counted separately; shared bindings do not claim imported assertions, and upstream placeholders have no behavioral body. Across Python and Ruby the batch contains exactly 300 standalone files.

The machine-readable manifest is `batch-300d-source-review.jsonl`; it records source hashes, roles and current per-file decision counts. This batch records 2295 source-level decisions: {'reject': 2182, 'defer': 51, 'adapt': 36, 'covered': 26}. Decisions are assertion/example/setup/generator-domain units, not a claim that each row is a unique runtime test execution. Explicit finite source variants were split where useful; external helpers and generated values remain pending when not inspected. No upstream suites were executed.

Current cumulative scope is 330/3413 files reviewed, 7545 decisions, with 3083 candidate files still pending. Discovery remains open; source-read status does not mean implementation complete. Every adaptation remains implementation_needed until separately resolved by the parent's central ledger.

This batch includes substantial iterator, hashing/GC, graphlib, resource/filecmp, Unicode literal/file, subprocess harness, rich comparison/numeric, and container wrapper bodies, plus smaller library tests. Python-only GC, buffer protocols, keyword binding, hash/set APIs, exception objects and dynamic imports are rejected or deferred with per-oracle rationale rather than proposed as Minyar features. Existing static modules, incremental cache tests and subprocess evidence tests are credited narrowly.

New concrete proposals include five cycle graphs, seven Unicode literal payloads, U+23456, nineteen Unicode filenames, suite catalogue/discovery agreement, and compile-only declaration of 300 positional parameters (existing width test uses41). Unicode filename normalization/platform guards must remain explicit. Candidate artifacts contain exact source identities. Source generation, helper invocation and external fixtures remain distinct from tested generated values.
