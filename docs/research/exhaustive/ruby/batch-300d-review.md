# ruby source review batch 300d

This batch fully read 243 standalone test-source files. Other source roles: {'shared_test_body': 1, 'shared_binding_wrapper': 20, 'upstream_placeholder': 4}. These are counted separately; shared bindings do not claim imported assertions, and upstream placeholders have no behavioral body. Across Python and Ruby the batch contains exactly 300 standalone files.

The machine-readable manifest is `batch-300d-source-review.jsonl`; it records source hashes, roles and current per-file decision counts. This batch records 5312 source-level decisions: {'reject': 4753, 'defer': 514, 'adapt': 15, 'covered': 30}. Decisions are assertion/example/setup/generator-domain units, not a claim that each row is a unique runtime test execution. Explicit finite source variants were split where useful; external helpers and generated values remain pending when not inspected. No upstream suites were executed.

Current cumulative scope is 899/9760 files reviewed, 8487 decisions, with 8861 candidate files still pending. Discovery remains open; source-read status does not mean implementation complete. Every adaptation remains implementation_needed until separately resolved by the parent's central ledger.

This batch includes String byte/case/transformation tests, exact Integer/Numeric cases, Array iteration, Range/Symbol/Encoding/Struct/Exception families. Unsupported Ruby mutable String, reflection, exception hierarchy, hash/symbol, float/bigint and stream APIs are rejected individually. Minyar record fields are immutable; no record-equality or Character(Integer) API is assumed.

Proposals include four additional compatible division/remainder pairs, negation at ±100 and ±2147483648, and malformed UTF-8 F1 61 62 63 64 (primitive_errinfo oracle31/51/58; converter recovery itself rejected). Two dynamic-length Array iteration adaptations have inspected resolution candidates in resolution-dynamic-length-iteration.jsonl, with parent-reported four optimization-level and ownership sanitizer passes. Linux /dev/full failure tests remain partial because local macOS validation skipped them.
