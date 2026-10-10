.PHONY: all check check-portable check-smoke check-regressions check-diagnostics check-conformance check-coverage check-memory check-runtime-unit check-ownership check-adversarial check-ownership-mutation check-ownership-stress check-budget check-fuzz check-fuzz-coverage check-stack-overflow check-windows-large-file check-modules check-mutation check-mutation-score check-performance check-scaling check-sanitize check-stress doctor emit run clean

.PHONY: check-runtime-cache
check-runtime-cache: build/minyarc
	$(LIMITED) python3 tests/runtime-cache.py

check: check-runtime-cache

.PHONY: check-ownership-policy check-stack-ownership
check-ownership-policy: build/minyarc build/minyarc-modules build/minyar-module-build
	$(LIMITED) python3 tests/ownership-policy.py

check-stack-ownership:
	$(SANITIZER_LIMITED) python3 tests/stack-ownership.py --clang "$(LLVM_CC)"

check: check-ownership-policy check-stack-ownership

check-smoke: build/minyarc build/minyar-runtime.o
	$(LIMITED) sh tests/smoke.sh

.PHONY: check-memory-contracts check-memory-contracts-harness
check-memory-contracts: build/minyarc
	$(LIMITED) python3 tests/memory-contracts.py

check-memory-contracts-harness: build/minyarc
	$(LIMITED) python3 tests/memory-contracts-harness.py

check: check-memory-contracts-harness

.PHONY: check-release-build check-critical-path check-launcher-isolation
check: check-launcher-isolation

check-launcher-isolation: build/minyarc build/minyar-runtime.o build/minyar-runtime-release.ll
	$(LIMITED) python3 tests/launcher-isolation.py

check-release-build: build/minyarc build/minyar-runtime.o build/minyar-runtime-release.ll
	$(LIMITED) python3 tests/release-build.py

check-critical-path: build/minyarc
	$(LIMITED) python3 experiments/memory/critical-path-study.py

check-regressions: build/minyarc build/minyar-runtime.o
	$(LIMITED) python3 tests/regressions.py

check-diagnostics: build/minyarc
	$(LIMITED) python3 tests/diagnostics.py

check: check-diagnostics

check-conformance: build/minyarc build/minyar-runtime.o
	$(LIMITED) python3 tests/conformance.py

check: check-conformance

check-memory: build/minyarc build/minyar-runtime.o
	$(LIMITED) python3 tests/memory.py

check-runtime-unit: build/runtime-unit
	$(LIMITED) ./build/runtime-unit

check-modules: build/minyarc build/minyar-runtime.o
	$(LIMITED) sh tests/run-module-tests.sh

.PHONY: check-json-parser check-json-parser-sanitize
check-json-parser: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/json-parser.py

check-json-parser-sanitize: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/json-parser.py --sanitize

check check-portable: check-json-parser
check-sanitize: check-json-parser-sanitize

.PHONY: check-module-performance
check-module-performance: build/minyarc build/minyar-runtime.o
	$(LIMITED) python3 tests/module-performance.py

check: check-module-performance

check-fuzz: check-fuzz-harness build/minyarc build/minyar-runtime.o
	$(LIMITED) python3 tests/fuzz.py

# Explicit because AFL++ is an optional developer/CI dependency and campaigns
# are duration-based. MINYAR_AFL_SECONDS controls the bounded run length.
check-fuzz-coverage: check-fuzz-afl-harness build/minyarc
	sh scripts/fuzz-afl.sh

check-coverage: check-coverage-harness check-coverage-inlining build/minyarc build/minyarc-modules build/minyar-runtime.o
	MINYAR_MIN_COMPILER_EDGE_COVERAGE=$(MIN_COMPILER_EDGE_COVERAGE) \
	MINYAR_MIN_RUNTIME_LINE_COVERAGE=$(MIN_RUNTIME_LINE_COVERAGE) \
	MINYAR_MIN_RUNTIME_BRANCH_COVERAGE=$(MIN_RUNTIME_BRANCH_COVERAGE) \
	python3 scripts/coverage.py

check-stack-overflow: build/minyarc build/minyar-runtime.o
	$(LIMITED) python3 tests/stack-overflow.py

.PHONY: check-stack-overflow-sanitize
check-stack-overflow-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o runtime/minyar_runtime.c $(RUNTIME_HEADERS)
	$(SANITIZER_LIMITED) python3 tests/stack-guard-sanitizer.py --clang "$(LLVM_CC)"
	ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/stack-overflow.py

# Cross-platform per-commit gate. Heavier memory-profile and performance
# matrices remain in the Linux evidence runner and the full `make check` gate.
check-windows-large-file:
	python3 tests/windows-large-file.py

check-portable: check-smoke check-regressions check-diagnostics check-conformance check-runtime-unit check-modules check-fuzz check-stack-overflow check-windows-large-file build/compiler-stage3.ll
	cmp build/compiler-stage2.ll build/compiler-stage3.ll

check-mutation: build/stage0 build/minyarc build/minyar-runtime.o
	$(LIMITED) python3 tests/mutation.py

.PHONY: check-mutation-score-harness
check-mutation-score-harness:
	python3 tests/mutation-score-harness.py

check-mutation-score: check-mutation-score-harness build/stage0 build/minyarc build/minyarc-modules build/minyar-compiler-runtime.ll build/minyar-runtime.o
	MINYAR_MIN_MUTATION_SCORE=$(MIN_MUTATION_SCORE) $(LIMITED) python3 tests/mutation-score.py

check-performance: build/minyarc build/minyar-runtime.o build/compiler-stage3.ll
	$(LIMITED) python3 tests/performance.py

check-scaling: build/minyarc
	$(LIMITED) python3 tests/scaling.py

# Run absolute self-compilation checks without background scheduling.
check-budget: build/minyarc build/compiler-stage3.ll
	python3 tests/self-compile-budget.py

.PHONY: check-sanitized-fixed-point check-generated-sanitizer
check-generated-sanitizer:
	$(SANITIZER_LIMITED) python3 tests/generated-stack-sanitizer.py --clang "$(LLVM_CC)"

.PHONY: check-binary-expressions
check-binary-expressions: build/minyarc build/minyarc-sanitize build/minyar-runtime.o build/ownership-runtime.o
	$(LIMITED) python3 tests/binary-expression-ownership.py
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/binary-expression-ownership.py

check: check-binary-expressions

.PHONY: check-integer-text-cache
check-integer-text-cache:
	$(SANITIZER_LIMITED) python3 tests/integer-text-cache.py --clang "$(LLVM_CC)"

check: check-integer-text-cache

.PHONY: check-tokenizer-storage
check-tokenizer-storage: build/minyarc
	$(SANITIZER_LIMITED) python3 tests/tokenizer-storage.py --clang "$(LLVM_CC)"

check: check-tokenizer-storage

.PHONY: check-temporary-owner-admission
check-temporary-owner-admission:
	$(SANITIZER_LIMITED) python3 tests/temporary-owner-admission.py --clang "$(LLVM_CC)"

check: check-temporary-owner-admission
# Verify that sanitizer coverage exercises the same compiler as the native
# fixed point, including when a retained build artifact has misleading times.
check-sanitized-fixed-point: build/minyarc-sanitize build/compiler-stage3.ll
	ASAN_OPTIONS=detect_leaks=0 $(SANITIZER_LIMITED) ./build/minyarc-sanitize compiler/compiler.min build/compiler-sanitized.ll
	cmp build/compiler-stage2.ll build/compiler-sanitized.ll
	cmp build/compiler-stage3.ll build/compiler-sanitized.ll

check-sanitize: check-generated-sanitizer check-sanitized-fixed-point check-stack-overflow-sanitize build/minyar-runtime.o build/minyar-runtime-sanitize.o build/runtime-unit-sanitize
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize $(SANITIZER_LIMITED) sh tests/run-module-tests.sh
	ASAN_OPTIONS=detect_leaks=0 $(SANITIZER_LIMITED) python3 tests/fuzz.py --compiler build/minyarc-sanitize --cases 100 --hostile-timeout 15
	ASAN_OPTIONS=detect_leaks=0 $(SANITIZER_LIMITED) ./build/runtime-unit-sanitize
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/regressions.py
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/ownership.py
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/memory.py Memory.test_shared_returned_and_nested_values

check-stress: build/minyarc build/minyar-runtime.o
	MINYAR_FUZZ_CASES=2000 $(LIMITED) python3 tests/fuzz.py

check: doctor check-smoke check-release-build check-recursive-data check-compact-ownership check-adversarial check-ownership-mutation check-regressions check-memory check-runtime-unit check-modules check-fuzz check-stack-overflow check-mutation check-performance check-scaling check-budget check-sanitize check-ownership check-examples

.PHONY: check-examples
check-examples: build/stage0 build/minyarc build/compiler-stage3.ll build/hello build/language-tour build/records build/compiler-bootstrap build/hello-self-hosted build/integer-overflow build/divide-by-zero build/text-and-files build/lists build/newlines build/top-level build/top-level-exit build/list-out-of-bounds build/text-indexing build/text-slice-out-of-bounds
	cmp build/compiler-stage2.ll build/compiler-stage3.ll
	test "$$(./build/hello)" = "hello from LLVM-backed Minyar"
	test "$$(./build/language-tour | tr '\n' ' ')" = "The answer is 42 3 2 1 "
	test "$$(./build/records | tr '\n' ' ')" = "Minyar Ada is 36 Grace "
	test "$$(./build/compiler-bootstrap | tr '\n' ' ')" = "Minyar compiler bootstrap is ready true false "
	test "$$(./build/hello-self-hosted)" = "hello from LLVM-backed Minyar"
	! ./build/stage0 tests/errors/type-mismatch.min -o build/invalid.ll 2> build/type-error.txt
	grep -q "declared as Text but receives Integer" build/type-error.txt
	! ./build/stage0 tests/errors/condition-must-be-boolean.min -o build/invalid.ll 2> build/condition-error.txt
	grep -q "if condition needs Boolean" build/condition-error.txt
	! ./build/stage0 tests/errors/integer-too-large.min -o build/invalid.ll 2> build/integer-error.txt
	grep -q "larger than Minyar currently supports" build/integer-error.txt
	! ./build/minyarc tests/errors/integer-too-large.min build/invalid.ll 2> build/integer-self-hosted-error.txt
	grep -q "Integer literal is outside the supported range" build/integer-self-hosted-error.txt
	! ./build/minyarc tests/errors/record-missing-field.min build/invalid.ll 2> build/record-missing-error.txt
	grep -q "record 'Person' is missing field 'age'" build/record-missing-error.txt
	! ./build/minyarc tests/errors/record-wrong-field-type.min build/invalid.ll 2> build/record-type-error.txt
	grep -q "record field 'age' has the wrong type" build/record-type-error.txt
	! ./build/minyarc tests/errors/record-field-assignment.min build/invalid.ll 2> build/record-immutable-error.txt
	grep -q "assigning this field could create a reference cycle" build/record-immutable-error.txt
	! ./build/integer-overflow > /dev/null 2> build/overflow-error.txt
	grep -q "Integer calculation is outside" build/overflow-error.txt
	! ./build/divide-by-zero > /dev/null 2> build/division-error.txt
	grep -q "Integer cannot be divided by zero" build/division-error.txt
	! ./build/list-out-of-bounds > /dev/null 2> build/list-error.txt
	grep -q "List position 1 is outside its length of 1" build/list-error.txt
	test "$$(./build/text-and-files first compiler/compiler.min build/written-text.txt | tr '\n' ' ')" = "6 M 42 3 first true "
	test "$$(cat build/written-text.txt)" = "Minyar"
	test "$$(./build/lists | tr '\n' ' ')" = "42 Minyar "
	test "$$(./build/newlines | tr '\n' ' ')" = "6 42 41 30 continued 6 "
	test "$$(./build/text-indexing | tr '\n' ' ')" = "3 7 A é 🙂 é🙂 "
	! ./build/text-slice-out-of-bounds > /dev/null 2> build/text-slice-error.txt
	grep -q "a Text slice must stay within the Text" build/text-slice-error.txt
	test "$$(./build/top-level | tr '\n' ' ')" = "{ top level 42 "
	./build/top-level-exit > build/top-level-exit-output.txt; test $$? -eq 7
	test "$$(cat build/top-level-exit-output.txt)" = "before exit"
	! ./build/minyarc tests/errors/statements-on-one-line.min build/invalid.ll 2> build/newline-error.txt
	grep -q "start the next statement on a new line" build/newline-error.txt
	! ./build/minyarc tests/errors/mixed-entry-points.min build/invalid.ll 2> build/mixed-entry-error.txt
	grep -q "cannot combine top-level statements with function main" build/mixed-entry-error.txt
	! ./build/minyarc tests/errors/top-level-statement.min build/invalid.ll 2> build/top-level-return-error.txt
	grep -q "use exit(status) to finish a top-level program" build/top-level-return-error.txt
	! ./build/minyarc tests/errors/malformed-expression.min build/invalid.ll 2> build/expression-error.txt
	grep -q "line 2, column 16: expected an expression, found ')'" build/expression-error.txt
	! ./build/minyarc tests/errors/top-level-malformed-expression.min build/invalid.ll 2> build/top-level-expression-error.txt
	grep -q "line 1, column 12: expected an expression, found ')'" build/top-level-expression-error.txt
	! ./build/minyarc tests/errors/duplicate-function.min build/invalid.ll 2> build/duplicate-function-error.txt
	grep -q "module declares 'duplicate' more than once" build/duplicate-function-error.txt
	! ./build/minyarc tests/errors/duplicate-record.min build/invalid.ll 2> build/duplicate-record-error.txt
	grep -q "module declares 'Duplicate' more than once" build/duplicate-record-error.txt
	! ./build/minyarc tests/fuzz-regressions/0001-unbalanced-punctuation.min build/invalid.ll 2> build/text-literal-error.txt
	grep -q "Text literal is missing its closing quote" build/text-literal-error.txt
	! ./build/minyarc tests/fuzz-regressions/0002-unclosed-character.min build/invalid.ll 2> build/character-literal-error.txt
	grep -q "Character literal must contain exactly one character" build/character-literal-error.txt
	! ./build/minyarc tests/fuzz-regressions/0003-unclosed-block-comment.min build/invalid.ll 2> build/comment-error.txt
	grep -q "block comment is missing its closing" build/comment-error.txt
	@echo "Minyar -> LLVM IR -> native executable verified"

check-ownership: build/minyarc build/minyar-runtime.o build/ownership-runtime.o
	$(LIMITED) python3 tests/ownership.py
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/ownership.py
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/memory.py Memory.test_shared_returned_and_nested_values

check-adversarial: build/minyarc build/minyar-runtime.o build/minyarc-sanitize build/ownership-runtime.o
	$(LIMITED) python3 tests/adversarial.py
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/adversarial.py

check-ownership-mutation:
	$(LIMITED) python3 tests/ownership-mutation.py

check-ownership-stress: build/minyarc build/minyarc-sanitize build/minyar-runtime.o build/ownership-runtime.o
	MINYAR_OWNERSHIP_GRAPHS=256 MINYAR_OWNERSHIP_SEEDS=32 $(LIMITED) python3 tests/ownership.py
	ASAN_OPTIONS=detect_leaks=0 MINYAR_OWNERSHIP_GRAPHS=256 MINYAR_OWNERSHIP_SEEDS=32 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/ownership.py

.PHONY: check-recursive-data check-bounded check-compact-ownership

.PHONY: check-scalar-record-storage check-compiler-slice-cache check-readonly-parameters
check: check-scalar-record-storage check-compiler-slice-cache check-readonly-parameters

.PHONY: check-scalar-record-initialization
check: check-scalar-record-initialization

check-scalar-record-initialization: build/minyarc build/minyarc-sanitize build/minyar-runtime.o build/ownership-runtime.o
	$(LIMITED) python3 tests/scalar-record-initialization.py --compiler build/minyarc --runtime build/minyar-runtime.o --clang "$(LLVM_CC)"
	ASAN_OPTIONS=detect_leaks=0 $(SANITIZER_LIMITED) python3 tests/scalar-record-initialization.py --compiler build/minyarc-sanitize --runtime build/ownership-runtime.o --clang "$(LLVM_CC)" --sanitize

check-scalar-record-storage: build/minyarc build/minyarc-sanitize build/minyar-runtime.o build/ownership-runtime.o
	$(LIMITED) python3 tests/scalar-lookahead-budget.py
	$(LIMITED) python3 tests/scalar-record-storage.py
	$(LIMITED) python3 tests/production-scalar-storage.py
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/scalar-record-storage.py
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/production-scalar-storage.py
	$(LIMITED) python3 tests/scalar-record-mutation.py

check-readonly-parameters: build/minyarc build/minyarc-sanitize build/minyar-runtime.o build/ownership-runtime.o
	$(LIMITED) python3 tests/readonly-parameters.py
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/readonly-parameters.py
	$(LIMITED) python3 tests/production-readonly-parameters.py
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/production-readonly-parameters.py

check-compiler-slice-cache:
	$(LIMITED) python3 tests/compiler-slice-cache.py

check-compact-ownership: build/minyarc build/minyarc-sanitize build/ownership-runtime.o build/minyar-compiler-runtime.ll
	$(LIMITED) python3 tests/compact-ownership.py
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/compact-ownership.py

.PHONY: check-text-view-budget
check-text-view-budget:
	$(SANITIZER_LIMITED) python3 tests/text-view-budget.py --clang "$(LLVM_CC)"

check: check-text-view-budget

# These matrices compile many sanitizer variants and reserve large virtual
# heaps. Keep them explicitly requested, outside the ordinary check target.
.PHONY: check-memory-profiles check-unary-pairs check-fused-unary
check-fused-unary:
	$(SANITIZER_LIMITED) python3 tests/fused-unary-regressions.py --clang "$(LLVM_CC)"
	$(SANITIZER_LIMITED) python3 tests/fused-work-regressions.py --clang "$(LLVM_CC)"

check-unary-pairs: check-fused-unary
	$(SANITIZER_LIMITED) python3 tests/unary-pair-regressions.py --clang "$(LLVM_CC)"

check-memory-profiles: build/minyar-runtime-system.o check-unary-pairs check-text-view-budget
	$(SANITIZER_LIMITED) python3 tests/memory-profile-regressions.py --runtime-source runtime/minyar_runtime.c --suite focused --clang "$(LLVM_CC)"
	$(SANITIZER_LIMITED) python3 tests/system-configurations.py
	$(SANITIZER_LIMITED) python3 tests/lazy-configurations.py --clang "$(LLVM_CC)"

check-recursive-data: build/minyarc build/minyarc-sanitize build/minyar-runtime.o build/ownership-runtime.o
	$(LIMITED) python3 tests/recursive-data.py
	$(LIMITED) python3 tests/production-memory.py
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/recursive-data.py
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/production-memory.py
	$(LIMITED) python3 experiments/memory/production-contract-model.py
	$(SANITIZER_LIMITED) python3 tests/recursive-mutation.py

check-bounded: build/minyarc build/minyar-runtime-bounded.o build/bounded-runtime build/bounded-runtime-sanitize build/bounded-ownership-runtime.o build/production-live-oracle build/production-frame-oracle build/bounded-list-capacity build/bounded-list-capacity-sanitize
	$(LIMITED) ./build/bounded-runtime
	ASAN_OPTIONS=detect_leaks=0 $(SANITIZER_LIMITED) ./build/bounded-runtime-sanitize
	ASAN_OPTIONS=detect_leaks=0 $(SANITIZER_LIMITED) ./build/production-live-oracle
	ASAN_OPTIONS=detect_leaks=0 $(SANITIZER_LIMITED) ./build/production-frame-oracle
	$(LIMITED) ./build/bounded-list-capacity
	ASAN_OPTIONS=detect_leaks=0 $(SANITIZER_LIMITED) ./build/bounded-list-capacity-sanitize
	$(LIMITED) python3 tests/bounded-configurations.py
	MINYAR_TEST_RUNTIME=./build/minyar-runtime-bounded.o $(LIMITED) python3 tests/recursive-data.py
	MINYAR_TEST_RUNTIME=./build/minyar-runtime-bounded.o $(LIMITED) python3 tests/production-memory.py
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_RUNTIME=./build/bounded-ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/recursive-data.py
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_RUNTIME=./build/bounded-ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/production-memory.py

.PHONY: check-incremental-modules
check-incremental-modules: build/minyarc-modules build/module-compiler-stage3.ll build/minyar-module-build build/minyar-runtime.o build/minyar-runtime-release.ll
	cmp build/module-compiler-stage2.ll build/module-compiler-stage3.ll
	$(LIMITED) python3 tests/incremental-modules.py
	$(LIMITED) python3 tests/incremental-module-driver.py
	$(LIMITED) python3 tests/incremental-module-delta.py
	$(LIMITED) python3 tests/incremental-module-artifacts.py
	$(LIMITED) python3 tests/incremental-launcher.py
	$(LIMITED) python3 tests/incremental-module-regressions.py

check: check-incremental-modules

.PHONY: check-incremental-module-performance
check-incremental-module-performance: build/minyarc-modules build/minyar-module-build build/minyar-runtime.o
	$(LIMITED) python3 tests/incremental-module-performance.py --enforce

check: check-incremental-module-performance

.PHONY: check-incremental-modules-sanitize
check-incremental-modules-sanitize: build/minyarc-modules-sanitize build/minyar-module-build-sanitize build/minyarc-modules build/minyar-module-build build/minyar-runtime.o build/minyar-runtime-sanitize.o build/ownership-runtime.o
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-modules-sanitize $(SANITIZER_LIMITED) python3 tests/incremental-modules.py
	ASAN_OPTIONS=detect_leaks=0 MINYAR_MODULE_DRIVER=./build/minyar-module-build-sanitize $(SANITIZER_LIMITED) python3 tests/incremental-module-driver.py
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-modules-sanitize MINYAR_MODULE_DRIVER=./build/minyar-module-build-sanitize $(SANITIZER_LIMITED) python3 tests/incremental-module-delta.py
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-modules-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/incremental-module-artifacts.py
	$(SANITIZER_LIMITED) python3 tests/incremental-module-regressions.py --sanitize

.PHONY: check-incremental-module-mutation
check-incremental-module-mutation: build/minyarc-modules build/module-compiler.min
	$(LIMITED) python3 tests/incremental-module-mutation.py

.PHONY: check-toolchain-stamp check-toolchain-portability check-fuzz-harness check-coverage-harness check-runtime-bytes check-runtime-bytes-sanitize check-compiler-hardening check-incremental-language-hardening check-module-driver-options check-native-graphics
check-toolchain-stamp:
	python3 tests/toolchain-stamp.py

check-toolchain-portability:
	python3 tests/toolchain-portability.py

.PHONY: check-cold-bootstrap
check-cold-bootstrap:
	MINYAR_TEST_CLANG="$(LLVM_CC)" python3 tests/toolchain-bootstrap.py

check-module-driver-options:
	python3 tests/module-driver-options.py

check-native-graphics:
	python3 tests/native-graphics.py

check-fuzz-harness:
	python3 tests/fuzz-harness.py

check-coverage-harness:
	python3 tests/coverage-harness.py

.PHONY: check-coverage-inlining
check-coverage-inlining:
	MINYAR_TEST_CLANG="$${MINYAR_TEST_CLANG:-$(LLVM_CC)}" python3 tests/coverage-inlining.py

check-runtime-bytes:
	MINYAR_TEST_CLANG="$(LLVM_CC)" python3 tests/runtime-random.py
	$(LIMITED) python3 tests/runtime-bytes.py --clang "$(LLVM_CC)"

check-runtime-bytes-sanitize:
	$(SANITIZER_LIMITED) python3 tests/runtime-bytes.py --clang "$(LLVM_CC)" --sanitize

.PHONY: check-runtime-traps check-runtime-traps-sanitize
check-runtime-traps:
	$(LIMITED) python3 tests/runtime-traps.py --clang "$(LLVM_CC)"

check-runtime-traps-sanitize:
	$(SANITIZER_LIMITED) python3 tests/runtime-traps.py --clang "$(LLVM_CC)" --sanitize

check-compiler-hardening: build/minyarc build/minyarc-modules build/minyar-runtime.o
	$(LIMITED) python3 tests/compiler-hardening.py

.PHONY: check-compiler-hardening-sanitize
check-compiler-hardening-sanitize: build/minyarc-sanitize build/minyarc-modules-sanitize build/minyar-runtime-sanitize.o
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_MODULE_COMPILER=./build/minyarc-modules-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/compiler-hardening.py

.PHONY: check-list-access check-list-access-sanitize
check-list-access: build/minyarc build/minyar-runtime.o
	$(LIMITED) python3 tests/list-access.py

check-list-access-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/list-access.py

.PHONY: check-checked-arithmetic check-checked-arithmetic-sanitize
check-checked-arithmetic: build/minyarc build/minyar-runtime.o
	$(LIMITED) python3 tests/checked-arithmetic.py

check-checked-arithmetic-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/checked-arithmetic.py

check-portable check: check-checked-arithmetic
check-sanitize: check-checked-arithmetic-sanitize

.PHONY: check-checked-scalars check-checked-scalars-sanitize
check-checked-scalars: build/minyarc build/minyar-runtime.o
	$(LIMITED) python3 tests/checked-scalars.py

check-checked-scalars-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/checked-scalars.py

check-portable check: check-checked-scalars
check-sanitize: check-checked-scalars-sanitize

check-incremental-language-hardening: build/minyarc-modules build/minyar-module-build build/minyar-runtime.o
	$(LIMITED) python3 tests/incremental-language-hardening.py

check-portable: check-toolchain-stamp check-toolchain-portability check-cold-bootstrap check-runtime-bytes check-runtime-traps check-compiler-hardening check-list-access
check-incremental-modules: check-incremental-language-hardening check-module-driver-options
check-sanitize: check-runtime-bytes-sanitize check-runtime-traps-sanitize check-compiler-hardening-sanitize check-list-access-sanitize
check: check-toolchain-stamp check-toolchain-portability check-cold-bootstrap check-runtime-bytes check-runtime-traps check-compiler-hardening check-list-access

.PHONY: check-format format
check-format:
	python3 scripts/format.py

format:
	python3 scripts/format.py --write

.PHONY: check-runtime-numeric check-runtime-numeric-sanitize
check-runtime-numeric: build/minyarc
	$(LIMITED) python3 tests/runtime-numeric.py --mode native

check-runtime-numeric-sanitize: build/minyarc
	$(SANITIZER_LIMITED) python3 tests/runtime-numeric.py --mode sanitize

check-portable: check-runtime-numeric
check: check-runtime-numeric
check-sanitize: check-runtime-numeric-sanitize

.PHONY: check-fuzz-afl-harness
check-fuzz-afl-harness:
	python3 tests/fuzz-afl-harness.py

.PHONY: check-bootstrap-portability
check-bootstrap-portability:
	python3 tests/bootstrap-portability.py

check-portable: check-bootstrap-portability
check: check-bootstrap-portability

.PHONY: check-bootstrap-records
check-bootstrap-records: build/stage0
	MINYAR_TEST_CLANG="$(LLVM_CC)" python3 tests/bootstrap-records.py

check-portable check: check-bootstrap-records

.PHONY: check-measurement-stats
check-measurement-stats:
	python3 tests/measurement-stats.py

check-portable check: check-measurement-stats

.PHONY: check-budget-harness
check-budget-harness:
	python3 tests/self-compile-budget-harness.py

check-portable check: check-budget-harness
check-budget: check-budget-harness

.PHONY: check-source-map check-source-map-sanitize
check-source-map: build/minyarc build/minyarc-modules build/minyar-runtime.o
	$(LIMITED) python3 tests/source-map.py

check-source-map-sanitize: build/minyarc-sanitize build/minyarc-modules-sanitize build/minyar-runtime-sanitize.o
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_MODULE_COMPILER=./build/minyarc-modules-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/source-map.py

check-portable check: check-source-map
check-sanitize: check-source-map-sanitize

.PHONY: check-scalar-path check-scalar-study-harness
check-scalar-study-harness:
	python3 tests/scalar-study-harness.py

check-scalar-path: check-scalar-study-harness build/minyarc
	$(LIMITED) python3 experiments/memory/checked-scalars-study.py

check: check-scalar-path
check-portable: check-scalar-study-harness

.PHONY: check-stack-limits
check-stack-limits:
	MINYAR_TEST_CLANG="$(LLVM_CC)" python3 tests/stack-limits.py

check-portable check: check-stack-limits

.PHONY: check-linkage check-linkage-sanitize
check-linkage: build/stage0 build/minyarc build/minyarc-modules build/minyar-runtime.o
	$(LIMITED) python3 tests/linkage.py

check-linkage-sanitize: build/stage0 build/minyarc-sanitize build/minyarc-modules-sanitize build/minyar-runtime-sanitize.o
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_MODULE_COMPILER=./build/minyarc-modules-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/linkage.py

check-portable check: check-linkage
check-sanitize: check-linkage-sanitize

.PHONY: check-symbol-order check-symbol-order-sanitize
check-symbol-order: build/minyarc build/minyar-runtime.o
	$(LIMITED) python3 tests/symbol-order.py

check-symbol-order-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/symbol-order.py

check-portable check: check-symbol-order
check-sanitize: check-symbol-order-sanitize

# Focused original adaptations and runtime invariants; no upstream corpus or
# archived research baseline is required by these maintained regressions.
.PHONY: check-peer-semantics check-peer-semantics-sanitize check-memory-regressions check-memory-regressions-sanitize check-bootstrap-policy
PEER_SEMANTIC_SUITES = peer-research-semantics peer-research-reachability peer-memory-nim-koka-lean peer-memory-nim-koka-followups memory-research-peer-projections

check-peer-semantics: build/minyarc build/minyar-runtime.o
	@set -e; for suite in $(PEER_SEMANTIC_SUITES); do $(LIMITED) python3 "tests/$$suite.py"; done

check-peer-semantics-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o
	@set -e; for suite in $(PEER_SEMANTIC_SUITES); do ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 "tests/$$suite.py"; done

check-memory-regressions:
	$(LIMITED) python3 tests/memory-research-regressions.py --clang "$(LLVM_CC)"

check-memory-regressions-sanitize:
	$(SANITIZER_LIMITED) python3 tests/memory-research-regressions.py --clang "$(LLVM_CC)" --sanitize

check-bootstrap-policy:
	python3 tests/launcher-bootstrap-policy.py

check-portable check: check-peer-semantics check-memory-regressions check-bootstrap-policy
check-sanitize: check-peer-semantics-sanitize check-memory-regressions-sanitize

# TLS 1.3 against a local OpenSSL server, through the hosted http, tls, crypto and net packages.
.PHONY: check-tls check-tls-sanitize
check-tls: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/tls-local.py

check-tls-sanitize: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/tls-local.py --sanitize

check check-portable: check-tls

.PHONY: check-quic check-quic-sanitize
check-quic: build/minyarc
	MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/quic-suite.py --artifacts build/quic-native-O0
	MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/quic-suite.py --optimization 2 --artifacts build/quic-native-O2

check-quic-sanitize: build/minyarc
	MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/quic-suite.py --sanitize --artifacts build/quic-sanitize

check: check-quic
check-sanitize: check-quic-sanitize

.PHONY: check-native-cache
check-native-cache:
	$(LIMITED) python3 tests/native-object-cache.py

check: check-native-cache
check-portable: check-native-cache

.PHONY: check-half-float
check-half-float: | build
	$(LIMITED) "$(LLVM_CC)" -O2 -Wall -Wextra -Werror tests/half-float.c -o build/half-float
	$(LIMITED) ./build/half-float

check: check-half-float
check-portable: check-half-float

# The native header's inline Bytes append, linked with the program runtime.
.PHONY: check-native-bytes
check-native-bytes: build/minyar-runtime.o | build
	$(LIMITED) "$(LLVM_CC)" -std=c11 -O2 -Wall -Wextra -Werror tests/native-bytes.c build/minyar-runtime.o -lm -o build/native-bytes
	$(LIMITED) ./build/native-bytes
	$(LIMITED) ./build/native-bytes negative 2>&1 | grep -q "Bytes cannot shrink by a negative amount"

check: check-native-bytes
check-portable: check-native-bytes
