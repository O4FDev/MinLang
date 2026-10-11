The maintained compiler now rejects managed parallel parameters and returns regardless of whether the body uses them. The core combines its existing body-ownership flag with the return type and every declared parameter. This applies to declarations, parallelEntry targets, and native machine signatures. Ordinary managed functions and ordinary native Text/Bytes signatures retain their generated LLVM.

The isolated Boat bx_y worktree is based on `09959964381164ad8bbcf8cc08dbe63b00150da3`. The maintained source change is six added guard lines in compiler/compiler.min. The Result builder validates that complete inherited guard exactly once. Its assembled source is byte-identical to the previous builder's output; closure and request assembly each inherit one guard.

Before the core edit, the frozen maintained binary accepted 12 unsafe signatures with compiler status 0 and emitted LLVM: unused Text, Bytes, List<Integer>, and scalar-only record parameters, each as a declaration and a parallelEntry target; a managed parameter after scalars; a 65th managed parameter after 64 scalars; an unused managed parameter with implicit Nothing return; and a parallel native machine Bytes parameter. The four managed-return controls already failed with status 1 and no LLVM. Text previously used the runtime-retain diagnostic, so its additional unittest failure was diagnostic alignment rather than a new signature acceptance.

The first baseline run also found a test extraction error for module-qualified positive function names. That test was corrected while the core remained untouched, and a fresh baseline retained all 20 raw outcomes. The corrected red phase had 12 acceptance failures plus the existing Text diagnostic mismatch. A scalar native machine fence control and the existing reference-body, forbidden-call, and invalid parallelEntry controls were recorded separately against the frozen binary.

Final dedicated coverage is 24 cases on each of the maintained, closure, and Result compilers: 16 managed-signature rejects, three existing safety rejects, and five accepted programs. Every reject returns status 1 with its expected diagnostic and no LLVM. The accepted ordinary managed/native, scalar Integer/Float/Boolean/Character/implicit Nothing, scalar machine, and existing imported parallel programs have byte-identical LLVM to their frozen frontend controls. Parallel bodies retain no ownership or call-depth runtime calls. Native ABI fixtures are compile-only; their synthetic external package is not linked.

The existing Result ABI review method also passes all 15 compiler rejection cases, including nested Result/List/Callback parameters, parallelEntry targets, a managed Result return, and ordinary native Result rejection. Its first single-method launcher used runpy without registering the test module and failed in unittest source introspection before any compiler execution. A registered importlib launcher corrected that setup failure; both phase statuses and raw logs remain retained.

Result adapter controls with a weakened return-reference check and a duplicated signature guard both fail closed. Maintained, closure, and Result self-host stage2/stage3 outputs match exactly:

- closure-compiler: `7fe1652d66e0ec0d970baa951b1e62ae385fb680a4a3af2884b6ca1b01f6bda0`.
- compiler: `9f01be6db405b2d32235f16d247d733d8bc124a7b2b0c00c86c47a42b117488d`.
- errors-compiler: `5521db15d9ef2dd2eb7782a7dd8092a456793e7c0f3ce403f7b6940a95f9d434`.

The 73 frozen runtime/header, closure/request adapter, and original native-object inputs remain unchanged. The original checkout remains clean at the base commit, and its seeded compiler binaries remain unchanged. The isolated ordinary/runtime objects and compiler-runtime LLVM retain their pre-edit bytes:

- build/minyar-compiler-runtime.ll: `ecd38b5816065abc5f5ef3d5ead6ebe11d1c124089481e8f8706f1f17ec8f07a`.
- build/minyar-default-runtime.o: `effee3192380318446fa53efc9d223dfb98aa04a37bb0c236889bf1131ff306a`.
- build/minyar-runtime.o: `12e6db7840e93959f942182ae13abae99672d0bc731170d9115bb6b93dd85fad`.

All compiler/build/test phases ran sequentially on the existing Boat bx_y host, through the 75% all-host CPU/RAM guard, with taskset CPUs 0–6, make -j1, MAKEFLAGS=-j1, GOMAXPROCS=1, GOFLAGS=-p=1, and LLD threads=1. No guard aborted. Raw phase statuses are retained below; nonzero rows are classified above.

| Phase | Status | Seconds | Maximum CPU % | Maximum RAM % |
| --- | ---: | ---: | ---: | ---: |
| red | 1 | 1.001 | 1.377 | 7.412 |
| red-corrected | 1 | 1.002 | 1.375 | 6.922 |
| runtime-control-build | 0 | 2.002 | 9.863 | 7.180 |
| scalar-native-control | 0 | 1.001 | 0.501 | 7.069 |
| core-build | 0 | 7.004 | 13.000 | 7.535 |
| core-green | 0 | 1.001 | 1.877 | 7.119 |
| closure-control | 0 | 1.001 | 0.875 | 6.940 |
| adapted-build | 0 | 17.009 | 13.358 | 8.195 |
| closure-green | 0 | 1.001 | 1.125 | 7.345 |
| result-green | 0 | 1.001 | 1.126 | 7.225 |
| legacy-control | 0 | 1.001 | 0.501 | 7.204 |
| core-final | 0 | 1.001 | 1.502 | 7.132 |
| closure-final | 0 | 1.001 | 1.373 | 7.187 |
| result-final | 0 | 1.001 | 1.253 | 7.144 |
| contract-verification | 0 | 1.001 | 2.622 | 7.224 |
| result-abi-review | 1 | 1.001 | 0.625 | 7.261 |
| result-abi-review-corrected | 0 | 1.001 | 0.876 | 7.201 |

Immutable raw evidence, baseline source/binaries, per-fixture source/LLVM/stdout/stderr and command/hash records, adapter controls, and verification.json are under `/home/user/minyar-overnight/parallel-signatures-20261011`. The guard protocol SHA is `87cb4494f047ce209b216c95c715adb8e9a99744c04d2f841f12c8dc04836de8`.

Run the dedicated source suite with `python3 tests/parallel-signatures.py -v`. MINYAR_TEST_COMPILER selects the closure or Result compiler. MINYAR_PARALLEL_IR_RECORD records accepted LLVM once; MINYAR_PARALLEL_IR_CONTROL checks an immutable baseline; MINYAR_PARALLEL_OBSERVATIONS retains every raw outcome. These cases remain independent of the shared catalogue and launcher.
