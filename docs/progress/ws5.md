# WS5 formats and crypto

2026-10-12, `ws5/formats` from frozen `bf9c0e9`. Development and own included-credit
Boat tests are admitted; only integration waits for the integrator. No v2 merge
or push by WS5, and no paid spend. Owned sandbox `bx_ev9fa25q`; all root hosts
remain untouched. No local sudo/admin/keychain/trust/privacy/security changes.

## Completed implementation and evidence

- SHA `dca5d8c` carried as `89e8b2e`: standalone streaming libcrypto SHA256_CTX
  value storage, clone/snapshot/raw-address APIs, no securecrypto. Native and
  generated-code ASan/UBSan passed 3,864 split cases, 64 alignments, 519 guards.
  Pure failed the 1.5 preference even against portable C; native ~0.99 direct C
  at 1 MiB. Small-input ownership overhead is documented.
- Compression `dab7d4c` carried as `5ad3a37`: bounded zstd plus gzip/zlib/raw
  DEFLATE, reusable typed shared contexts, RAW/by-copy dictionaries, explicit
  raw APIs, normal/custom links and differential fuzz. Long prebuilt samples:
  105 matching pairs, native/C 0.953–1.085, CV 0.40–17.19%. No pure candidate or
  percent-scale speedup is claimed.
- Tar `033dbf6` carried as `e6b8a86`: bounded byte metadata/PAX/GNU reader and
  deterministic writer, vendor/binary attrs, exact times and physical spans.
  Native and generated IR/runtime/binding ASan/UBSan/LSan passed 2,073 cases
  each. Pure 3.089–8.479x C; native 2.041–11.048x C. Performance is limited.
- Complete hypothetical neo-vm shim-removal diff recorded in
  `docs/formats/neo-vm-shim-removal.md`; all referenced neo-vm files unchanged.

## Review corrections in flight

- SHA/provider fresh r1 found four P2 provider/test defects: actual loaded image
  identity, foreign secondary headers, POSIX backslash paths and Mac temporary
  path canonicalization. It also challenged a quoted-compiler dry-run claim.
  Isolated provider-fix child is implementing regressions/corrections.
- Compression fresh r1 found two P2 provider defects: renamed DSO accepted as
  static archive and ignored effective compiler flags/header shadows. Fixed in
  `afd0529`: real embedded relocatable archive/static symbols, RAW/by-copy ABI
  probe, effective compile/link flags and actual dependency fingerprints.
  Seven actual provider tests plus native/sanitizer suites passed on own Boat
  at 15:38 UTC; fresh independent r2 is reviewing the correction.
- Tar fresh r1 found three P2s: long absolute path loses slash, empty hardlink
  changes type, and effective PAX limit depends on deletion order. Author is
  implementing focused RED regressions and fixes on `ws5/tar`.
- Combined OCI tar→gzip/zstd→streaming SHA normal/custom-link test and sanitizer
  fixture are being qualified. Additive formats.mk gates are drafted; they
  are not yet committed/reviewed or claimed available in v2.

## Integration and remaining gates

No merge requests offered yet; every correction requires a fresh review.
Integrator `mcp:b814e5f7-fef7-4fcd-8d92-66fa4104f2d1` alone merges/pushes v2.
Rebase when qualified v2/PHASE1_DONE is supplied. WS1/2/4/7 shared-driver owners
were notified; compiler already accepts native package names. No Map/sort
implementation dependency is introduced.

WS7 owns matched UCRT64/CLANG64 dependencies and actual Windows qualification.
Required providers: real libzstd.a, zlib, libcrypto only, libarchive. Reviewed
source delta and exact native/sanitizer commands will follow fresh approvals.
The existing-workload ±1% gate (compiler, Minyarcraft, Atacama GUI, JSON,
neo-db) remains unproven for this combined branch; no module timing substitutes
for it. Gap docs are not marked fixed before actual v2 integration. Large
whole OCI layers need streaming/adaptation beyond the 256 MiB codec cap;
erofs/ext4 writing remains deferred.
