# Generated LLVM sanitizer linking

Clang's address sanitizer link flags supply the pass/runtime. Generated LLVM
function definitions also require sanitize_address for their loads/stores.
tools/sanitizer_llvm.py is the canonical generated-program annotator; the
existing tests/llvm_sanitizer.py API/CLI forwards to it. Sanitized frontend
Make rules depend on both files. Existing CompilerTestCase annotation continues
to use the same helper.

The public tools/clang-driver.py link command annotates a separate program
copy when the effective ordered flags enable address sanitization. It leaves
the original program IR and the runtime/native objects untouched. C runtime
code is already instrumented during its object compilation and is never sent
to the program annotator. Ordinary and effectively disabled links keep their
original LLVM argument and bytes. Program annotation is recomputed each
invocation, without a program IR cache. Native object content keys continue
to depend on their own sources/headers/toolchain/flags.

Set MINYAR_LINK_ARTIFACTS to a fresh directory to retain original/annotated
program LLVM, exact runtime/native objects, linker/compiler argv and version,
compiler/tool bytes and hashes, and the linked binary. Reusing that directory
fails. Invalid generated headers fail before link/publication, retaining the
raw LLVM and a failed-annotation manifest. Quoted LLVM names/attributes and
attribute groups are handled without confusing identifiers with sanitizer
attributes. Unsupported header changes fail closed.

The mandatory check-generated-llvm-sanitizer control compiles the maintained
tests/generated-llvm-sanitizer.min, then injects one isolated volatile
freed-byte store into that actual generated program. Before the hook,
compiler/runtime-compile/public-link all returned 0 and execution returned 0
with 42 and empty stderr, despite sanitizer flags. With the hook, compilation
and linking still return 0 and the unsafe access produces an ASan
heap-use-after-free report. This proves generated-access instrumentation
through the public link driver; it is not a production source mutation.
Additional controls cover effective disable/enable ordering, valid ordinary
execution and IR identity, idempotency, quoted/header validation, artifact
collision/failure retention, and native object reuse/header invalidation.

Actual evidence for this implementation is retained remotely under
/home/user/minyar-overnight/ci/generated-ir-sanitizer-focused. The initial
runner-argv setup failure and failed malformed-header JSON manifest are kept
separately. Linux ASan/UBSan/LSan checks do not certify Windows/macOS execution,
the unresolved Windows 1s/2% idle recurrence, the full matrix, or QUIC peers.
Earlier public-driver generated LLVM without annotation is not retrospectively
certified. Already annotated CompilerTestCase/frontend proofs retain their
original scope.
