JSONTestSuite parsing fixtures from https://github.com/nst/JSONTestSuite at
commit `1ef36fa01286573e846ac449e8683f8833c5b26a` (MIT; see LICENSE).

All 318 parsing fixtures are retained unchanged. Upstream `y_` inputs must
be accepted and `n_` inputs rejected; `i_` inputs may produce either result
but must finish without a crash. The harness verifies each fixture's SHA-256.
Generated tests additionally use Python's strict UTF-8 decoder and JSON parser
as an independent oracle, with a fixed seed for reproducible mutations.

Minyar limits nesting to 64 levels and replaces unpaired escaped surrogates
with U+FFFD. `parseBytes` rejects malformed UTF-8 before Text conversion.
`parseUnique` is a separate bounded metadata mode that rejects duplicate
decoded names; ordinary `parse` retains its duplicate-name behavior.
