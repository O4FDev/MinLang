# Depth TLS R2 follow-up

Independent R2 did not approve `ab185b2`: the POSIX fixture guard used
`os.name == 'nt'`, which misses MSYS Python. This follow-up uses the existing
`windows_host()` predicate and reloads the actual decorator under simulated
Linux, Darwin, Windows, MSYS, MINGW and CYGWIN host names. The native depth TLS
annotations and fixture behavior are unchanged. A fresh review is still required.

Validation ran on owned Boat `bx_8pvzt8f7`, in isolated
`/home/user/ws2-depth-tls-r2-input`, not the dirty recovery checkout. The source
is exactly `ab185b295cb34718bfe3a13973f51961076ddddf` plus
`tests/thread-config.py`; all 65 input files were hashed locally before export
and matched byte for byte before the Boat run. This includes the depth fixture,
test harness, platform helper, graph renderer, runtime and every runtime header.
No recovery header/source was present. The five tests passed, including actual
O0/O2 pthread concurrency and simulated platform selection. Local selection
controls also passed. This is focused TLS evidence, not full platform or app
performance qualification.

Boat command `cmd_wn1fqxxsn2um` executed `python3 /tmp/ws2-tls-r2-run.py`.
The report records 38 exact compiler/execution commands, stdin source hashes,
Clang tool identity/version, stdout/stderr and native binary hashes. Inputs,
stdin bodies, fixture/harness source and binaries are preserved in
`evidence/ws2-call-depth/tls-r2-followup-evidence.tar.gz`.
Its SHA256 is `2a40481551f7fc6a1ac0993a4d9a90ef23c7d87dd974306dd2cbc9d93dcce271`.
The JSON input and result manifests are beside that archive. The older
`depth-tls-evidence.tar.gz` remains preserved for the original R2 audit.

Only test selection and this isolated evidence belong to the follow-up commit.
Full recovery files remain separate. No merge request, push or approval claim.
