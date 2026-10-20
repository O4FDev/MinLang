# Postfix campaign independent data audit

Source/data-only audit; no builds, tests, workloads, bx/box access or changes to
production/tests/parent report. Parent owns frozen gates and landing.

Inputs: `measurements/perfcs/postfix-self/{instructions,manifest}.json` and
`postfix-products/{results,manifest}.json`. Control runtime is landed
`ce077582403c4806a925a826593d6031f6a9ae4a`; candidate is frozen
`b7e605a81211a509bd8cae1440af1a39efa08dea`.

## Individual observations verified

Every recorded instruction array, median, minimum and maximum was recomputed
from individual retained observations. Each role group contains exactly eight
observations, sample IDs -1,0..6, one warmup and seven retained samples.

| Workload | Control median | Candidate median | Recomputed change |
| --- | ---: | ---: | ---: |
| Self default | 15,278,646,435 | 14,690,629,119 | -3.84862179% |
| Self eager | 4,559,020,146 | 4,559,018,219 | -0.00004227% |
| JS default | 169,369,200 | 164,776,858 | -2.71143868% |
| jsmn16 default | 11,149,279,269 | 10,796,870,639 | -3.16081983% |
| jsmn1024 default | 6,459,141,996 | 6,021,821,391 | -6.77056806% |
| jsmn16384 default | 10,535,613,370 | 9,814,721,247 | -6.84243145% |
| JPEG default, instrumented | 12,707,542,102 | 12,524,071,846 | -1.44379027% |

All expected headline values and rounded percentages match. Other eagers and
PNG/zlib are effectively unchanged; their largest absolute change is JS eager
at +0.00026565%, not exactly identical instruction counts.

There are 32 self executions and 272 product executions. All have positive
hardware instruction counts, positive enabled/running time with exact equality,
counter_scaled=false and exit0. All self stdout/stderr are empty; all product
stderr hashes are empty. Self outputs all have 17,171,630 bytes and SHA-256
`0df92ae214e773ae0fdf8ae01ed7de3871b77c4f82c5aaf9a20de3c9045e64c9`,
identical to the prior campaign. Product observations have 34 warmups and 238
retained samples in 34 role groups; actual interleaving exactly follows the
maintained alternating-order helper. Its 14 workloads include six jsmn C-reference
roles in addition to baseline/candidate.

All product semantic records agree per workload. Independent jsmn token/byte/
iteration/checksum formulas match; JS is exactly `3980\n`. Four separate JS
ownership checks hash the same stdout in shipping/instrumented links. All 48
jsmn qualification cells and 176 zero-exit build/check commands are present.
The 12 full codec-oracle hashes agree across both roles/profiles for each codec,
and match prior-campaign hashes. JPEG retains tolerance3 versus its independent
reference while requiring exact baseline/candidate bytes.

All 103 baseline and 104 candidate runtime files in **each** build manifest
match the declared Git commit blobs by SHA-256, with no missing files or mismatch.
The product result's manifest hash matches the archived manifest exactly. Both
manifests are ready and product results complete; both select the same clang
SHA-256, with explicit LLVM23.1.3 version/path. Self input/library hashes are
unchanged from the prior audit.

## Isolation, links and accounting verified

Self baseline/candidate retain identical per-profile frozen LLVM hashes and
matched ThinLTO flags; both profile LLVM hashes are unchanged from the previous
audit. Product input snapshots (103 files), library snapshot (78 files), and
frozen compiler binary hash are also unchanged. This supports the stated
runtime-only comparison, not cumulative compiler/product-HEAD improvements.

All 14 product baseline/candidate recorded link pairs differ only in runtime
object and output; common program/native object identities match immutable
hashes. No product link contains LTO. Runtime object/wrapper hashes match their
accounting records. All 20 accounting records have the expected split: measured
JS/jsmn disabled, separate JS/jsmn ownership proofs enabled, safelibs measurements
enabled. Self is accounting-disabled. Maintained products.py,
measure-products.py, relink-self.py and frames-instructions.py hashes match
their recorded frozen copies; the self runner hash matches too.

## Audited input identities

| File | SHA-256 |
| --- | --- |
| postfix-self/instructions.json | 949b9f646e070e70ffe986b91e89f4e417319100eaf00fc09919796971ea64d7 |
| postfix-self/manifest.json | b06a16d0b795a390ec3d9f695cc34fa7cc43c6560ae7e698e1d98e2b85a23188 |
| postfix-products/results.json | c0d0236afdfe2cdada0add7449f5868c5a3ccc313ea2f1a24b06cc8c90e87607 |
| postfix-products/manifest.json | 2b43bc58db2ef9d75c69f19dbbf54fa1bfd529cdca2d2261ac8dbebbb5369f2f |

Completed: no discrepancy found in the supplied headline medians, percentages,
individual sample/output/counter records, accounting labels, shared-link/input
isolation or runtime Git identities. This is a source/data audit, not a workload
rerun, archive-binary rehash or gate/landing receipt. No new landing condition or
production/test/report edit was introduced. Scoped audit stopped; parent
continues frozen gates and landing.
