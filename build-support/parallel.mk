# Compile-only ABI rejection and scalar controls on all maintained frontends.
.PHONY: check-parallel check-parallel-sanitize check-parallel-signatures check-parallel-signatures-sanitize
PARALLEL_SIGNATURE_FRONTENDS = minyarc minyarc-callbacks minyarc-errors
PARALLEL_SIGNATURE_SANITIZER_FRONTENDS = minyarc-sanitize minyarc-callbacks-sanitize minyarc-errors-sanitize
PARALLEL_SIGNATURE_FIXTURES = tests/parallel-signatures/managed-after-scalars.min \
    tests/parallel-signatures/managed-implicit-nothing.min \
    tests/parallel-signatures/managed-parameter-65.min \
    tests/parallel-signatures/ordinary-managed.min \
    tests/parallel-signatures/ordinary-native.min \
    tests/parallel-signatures/parallel-native-bytes.min \
    tests/parallel-signatures/return-bytes.min \
    tests/parallel-signatures/return-list.min \
    tests/parallel-signatures/return-record.min \
    tests/parallel-signatures/return-text.min \
    tests/parallel-signatures/scalar-native.min \
    tests/parallel-signatures/scalar-values.min \
    tests/parallel-signatures/unused-bytes-entry.min \
    tests/parallel-signatures/unused-bytes.min \
    tests/parallel-signatures/unused-list-entry.min \
    tests/parallel-signatures/unused-list.min \
    tests/parallel-signatures/unused-record-entry.min \
    tests/parallel-signatures/unused-record.min \
    tests/parallel-signatures/unused-text-entry.min \
    tests/parallel-signatures/unused-text.min
PARALLEL_SIGNATURE_INPUTS = build/tooling/tests/parallel-signatures $(PARALLEL_SIGNATURE_FIXTURES) $(wildcard tests/parallel/*.min tests/parallel/errors/*.min)
build/tooling/tests/parallel-signatures.ll: tests/evidence-support.min
build/tooling/tests/parallel-signatures: TOOL_NATIVE = tests/evidence-support-native.c runtime/native/sha256.c
build/tooling/tests/parallel-signatures: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/parallel-signatures: tests/evidence-support-native.c runtime/native/sha256.c

# One target per process: one per scalar-control profile, then one per frontend. Each
# piece keeps its own evidence tree and only removes its own stale evidence directories.
PARALLEL_SIGNATURE_PREREQUISITES = $(addprefix build/,$(PARALLEL_SIGNATURE_FRONTENDS)) build/minyar-runtime.o build/compiler-stage3.ll build/closure-compiler-stage3.ll build/errors-compiler-stage3.ll $(PARALLEL_SIGNATURE_INPUTS) build/testing/cycle-runtime.o build/tooling/tests/compiler-behavior
PARALLEL_SIGNATURE_SANITIZER_PREREQUISITES = $(addprefix build/,$(PARALLEL_SIGNATURE_SANITIZER_FRONTENDS)) build/minyar-runtime.o $(PARALLEL_SIGNATURE_INPUTS)
PARALLEL_SIGNATURE_PARTS = check-parallel-signatures-part1 check-parallel-signatures-part2 check-parallel-signatures-part3 check-parallel-signatures-part4 check-parallel-signatures-part5 check-parallel-signatures-part6
PARALLEL_SIGNATURE_SANITIZE_PARTS = check-parallel-signatures-sanitize-part1 check-parallel-signatures-sanitize-part2 check-parallel-signatures-sanitize-part3
.PHONY: $(PARALLEL_SIGNATURE_PARTS) $(PARALLEL_SIGNATURE_SANITIZE_PARTS)
check-parallel-signatures: $(PARALLEL_SIGNATURE_PARTS)
check-parallel-signatures-sanitize: $(PARALLEL_SIGNATURE_SANITIZE_PARTS)
$(PARALLEL_SIGNATURE_PARTS): $(PARALLEL_SIGNATURE_PREREQUISITES) | build
$(PARALLEL_SIGNATURE_SANITIZE_PARTS): $(PARALLEL_SIGNATURE_SANITIZER_PREREQUISITES) | build
check-parallel-signatures-part1:
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/compiler-behavior --profile core --ir build/compiler-stage3.ll
check-parallel-signatures-part2:
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/compiler-behavior --profile callbacks --ir build/closure-compiler-stage3.ll
check-parallel-signatures-part3:
	MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/compiler-behavior --profile errors --ir build/errors-compiler-stage3.ll
check-parallel-signatures-part4:
	@set -e; rm -rf -- build/parallel-signatures-native-minyarc-*; evidence=$$(mktemp -d "$(abspath build)/parallel-signatures-native-minyarc-XXXXXX"); \
	MINYAR_TEST_COMPILER="./build/minyarc" MINYAR_PARALLEL_OBSERVATIONS="$$evidence/minyarc" MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/parallel-signatures
check-parallel-signatures-part5:
	@set -e; rm -rf -- build/parallel-signatures-native-minyarc-callbacks-*; evidence=$$(mktemp -d "$(abspath build)/parallel-signatures-native-minyarc-callbacks-XXXXXX"); \
	MINYAR_TEST_COMPILER="./build/minyarc-callbacks" MINYAR_PARALLEL_OBSERVATIONS="$$evidence/minyarc-callbacks" MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/parallel-signatures
check-parallel-signatures-part6:
	@set -e; rm -rf -- build/parallel-signatures-native-minyarc-errors-*; evidence=$$(mktemp -d "$(abspath build)/parallel-signatures-native-minyarc-errors-XXXXXX"); \
	MINYAR_TEST_COMPILER="./build/minyarc-errors" MINYAR_PARALLEL_OBSERVATIONS="$$evidence/minyarc-errors" MINYAR_TEST_CLANG="$(TEST_CLANG)" $(LIMITED) ./build/tooling/tests/parallel-signatures

# The driver emits LLVM but never links its synthetic native-package controls.
check-parallel-signatures-sanitize-part1:
	@set -e; rm -rf -- build/parallel-signatures-sanitize-minyarc-sanitize-*; evidence=$$(mktemp -d "$(abspath build)/parallel-signatures-sanitize-minyarc-sanitize-XXXXXX"); \
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_COMPILER="./build/minyarc-sanitize" MINYAR_PARALLEL_OBSERVATIONS="$$evidence/minyarc-sanitize" MINYAR_TEST_CLANG="$(TEST_CLANG)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/parallel-signatures
check-parallel-signatures-sanitize-part2:
	@set -e; rm -rf -- build/parallel-signatures-sanitize-minyarc-callbacks-sanitize-*; evidence=$$(mktemp -d "$(abspath build)/parallel-signatures-sanitize-minyarc-callbacks-sanitize-XXXXXX"); \
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_COMPILER="./build/minyarc-callbacks-sanitize" MINYAR_PARALLEL_OBSERVATIONS="$$evidence/minyarc-callbacks-sanitize" MINYAR_TEST_CLANG="$(TEST_CLANG)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/parallel-signatures
check-parallel-signatures-sanitize-part3:
	@set -e; rm -rf -- build/parallel-signatures-sanitize-minyarc-errors-sanitize-*; evidence=$$(mktemp -d "$(abspath build)/parallel-signatures-sanitize-minyarc-errors-sanitize-XXXXXX"); \
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_COMPILER="./build/minyarc-errors-sanitize" MINYAR_PARALLEL_OBSERVATIONS="$$evidence/minyarc-errors-sanitize" MINYAR_TEST_CLANG="$(TEST_CLANG)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/parallel-signatures

check check-portable check-parallel check-callbacks check-errors-language: check-parallel-signatures
check-sanitize check-parallel-sanitize check-callbacks-sanitize check-errors-language-sanitize: check-parallel-signatures-sanitize
