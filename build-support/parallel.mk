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
PARALLEL_SIGNATURE_INPUTS = tests/parallel-signatures.py tests/regressions.py tests/test_evidence.py tests/clang_helpers.py tests/llvm_sanitizer.py tools/sanitizer_llvm.py $(PARALLEL_SIGNATURE_FIXTURES) $(wildcard tests/parallel/*.min tests/parallel/errors/*.min)

check-parallel-signatures: $(addprefix build/,$(PARALLEL_SIGNATURE_FRONTENDS)) build/minyar-runtime.o build/compiler-stage3.ll build/closure-compiler-stage3.ll build/errors-compiler-stage3.ll $(PARALLEL_SIGNATURE_INPUTS) build/testing/cycle-runtime.o build/tooling/tests/compiler-behavior | build
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/compiler-behavior --profile core --ir build/compiler-stage3.ll
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/compiler-behavior --profile callbacks --ir build/closure-compiler-stage3.ll
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/compiler-behavior --profile errors --ir build/errors-compiler-stage3.ll
	@set -e; evidence=$$(mktemp -d "$(abspath build)/parallel-signatures-native-XXXXXX"); \
	for frontend in $(PARALLEL_SIGNATURE_FRONTENDS); do \
	    MINYAR_TEST_COMPILER="./build/$$frontend" MINYAR_PARALLEL_OBSERVATIONS="$$evidence/$$frontend" MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/parallel-signatures.py; \
	done

# The driver emits LLVM but never links its synthetic native-package controls.
check-parallel-signatures-sanitize: $(addprefix build/,$(PARALLEL_SIGNATURE_SANITIZER_FRONTENDS)) build/minyar-runtime.o $(PARALLEL_SIGNATURE_INPUTS) | build
	@set -e; evidence=$$(mktemp -d "$(abspath build)/parallel-signatures-sanitize-XXXXXX"); \
	for frontend in $(PARALLEL_SIGNATURE_SANITIZER_FRONTENDS); do \
	    $(NATIVE_SANITIZER_ENV) MINYAR_TEST_COMPILER="./build/$$frontend" MINYAR_PARALLEL_OBSERVATIONS="$$evidence/$$frontend" MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/parallel-signatures.py; \
	done

check check-portable check-parallel check-callbacks check-errors-language: check-parallel-signatures
check-sanitize check-parallel-sanitize check-callbacks-sanitize check-errors-language-sanitize: check-parallel-signatures-sanitize
