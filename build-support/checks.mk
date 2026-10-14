.PHONY: all check check-portable check-smoke check-regressions check-diagnostics check-conformance check-coverage check-memory check-runtime-unit check-ownership check-adversarial check-ownership-mutation check-ownership-stress check-budget check-fuzz check-fuzz-coverage check-stack-overflow check-windows-large-file check-modules check-mutation check-mutation-score check-performance check-scaling check-sanitize check-stress doctor emit run clean

.PHONY: check-runtime-cache
check-runtime-cache: build/minyarc build/tooling/tests/runtime-cache build/tooling/tools/clang-driver
	$(LIMITED) ./build/tooling/tests/runtime-cache

check: check-runtime-cache

.PHONY: check-ownership-policy check-stack-ownership
check-ownership-policy: build/minyarc build/minyarc-modules build/minyar-module-build build/tooling/tests/ownership-policy
	$(LIMITED) ./build/tooling/tests/ownership-policy

STACK_OWNERSHIP_BOUNDED = $(foreach profile,system fixed lazy,$(foreach budget,1 2 8 9 32 1024,$(foreach mode,native sanitize,check-stack-ownership-$(profile)-$(budget)-$(mode))))
STACK_OWNERSHIP_FALLBACK = $(foreach profile,eager arena,$(foreach mode,native sanitize,check-stack-ownership-$(profile)-32-$(mode)))
.PHONY: $(STACK_OWNERSHIP_BOUNDED) $(STACK_OWNERSHIP_FALLBACK)
check-stack-ownership: $(STACK_OWNERSHIP_BOUNDED) $(STACK_OWNERSHIP_FALLBACK)
$(STACK_OWNERSHIP_BOUNDED) $(STACK_OWNERSHIP_FALLBACK): build/tooling/tests/stack-ownership tests/stack-ownership-runtime.c tests/stack-ownership-fallback.c tests/stack-ownership-runtime-source.h experiments/memory/production-live-oracle.c $(RUNTIME_HEADERS)
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/stack-ownership $(word 4,$(subst -, ,$@)) $(word 5,$(subst -, ,$@)) $(word 6,$(subst -, ,$@))


check: check-ownership-policy check-stack-ownership

check-smoke: build/minyarc build/minyar-runtime.o
	$(LIMITED) sh tests/smoke.sh

.PHONY: check-memory-contracts check-memory-contracts-harness
.PHONY: check-foundation-baseline
check-foundation-baseline: build/minyarc build/testing/cycle-runtime.o build/tooling/tests/compiler-behavior
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/compiler-behavior --compiler build/minyarc --profile errors

check check-portable: check-foundation-baseline

check-memory-contracts: build/minyarc build/tooling/tests/memory-contracts build/tooling/tests/ownership build/tooling/tests/recursive-data build/tooling/tests/production-memory build/tooling/tests/regressions build/tooling/tests/adversarial
	$(LIMITED) ./build/tooling/tests/memory-contracts

build/tooling/tests/memory-contracts-harness: TOOL_RUNTIME = build/testing/cycle-runtime.o
build/tooling/tests/memory-contracts-harness: build/testing/cycle-runtime.o
check-memory-contracts-harness: build/minyarc build/tooling/tests/memory-contracts build/tooling/tests/memory-contracts-harness
	$(LIMITED) ./build/tooling/tests/memory-contracts-harness

check: check-memory-contracts-harness

.PHONY: check-release-build check-critical-path check-launcher-isolation
check: check-launcher-isolation

check-launcher-isolation: build/minyarc build/minyarc-errors-request build/minyar-runtime.o build/minyar-runtime-release.ll build/tooling/tools/clang-driver
	$(LIMITED) python3 tests/launcher-isolation.py

check-release-build: build/minyarc build/minyar-runtime.o build/minyar-runtime-release.ll
	$(LIMITED) python3 tests/release-build.py

build/tooling/experiments/memory/critical-path-study.ll: experiments/memory/study-support.min experiments/memory/measurement-stats.min tests/cpython-random.min
build/tooling/experiments/memory/critical-path-study: TOOL_RUNTIME = build/testing/cycle-runtime.o
build/tooling/experiments/memory/critical-path-study: build/testing/cycle-runtime.o
check-critical-path: build/minyarc build/tooling/experiments/memory/critical-path-study
	$(LIMITED) ./build/tooling/experiments/memory/critical-path-study

build/tooling/tests/regressions: TOOL_RUNTIME = build/testing/cycle-runtime.o
build/tooling/tests/regressions: build/testing/cycle-runtime.o
check-regressions: build/minyarc build/minyar-runtime.o build/tooling/tests/regressions
	$(LIMITED) ./build/tooling/tests/regressions

check-diagnostics: build/minyarc build/tooling/tests/diagnostics
	$(LIMITED) ./build/tooling/tests/diagnostics

check: check-diagnostics

check-conformance: build/minyarc build/minyar-runtime.o build/tooling/tests/conformance
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/conformance

check: check-conformance

check-memory: build/minyarc build/minyar-runtime.o build/tooling/tests/memory
	$(LIMITED) ./build/tooling/tests/memory

check-runtime-unit: build/runtime-unit
	$(LIMITED) ./build/runtime-unit

check-modules: build/minyarc build/minyar-runtime.o build/tooling/tools/clang-driver
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) sh tests/run-module-tests.sh

.PHONY: check-json-parser check-json-parser-sanitize
build/tooling/tests/json-parser-test: TOOL_NATIVE = runtime/native/sha256.c
build/tooling/tests/json-parser-test: TOOL_LIBS = $(TOOL_CRYPTO)
check-json-parser: build/minyarc build/tooling/tests/json-parser-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/json-parser-test

check-json-parser-sanitize: build/minyarc build/tooling/tests/json-parser-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/json-parser-test --sanitize

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

check-coverage: check-coverage-harness check-coverage-inlining build/minyarc build/minyarc-modules build/minyar-runtime.o build/tooling/tests/text-basics-model
	MINYAR_MIN_COMPILER_EDGE_COVERAGE=$(MIN_COMPILER_EDGE_COVERAGE) \
	MINYAR_MIN_RUNTIME_LINE_COVERAGE=$(MIN_RUNTIME_LINE_COVERAGE) \
	MINYAR_MIN_RUNTIME_BRANCH_COVERAGE=$(MIN_RUNTIME_BRANCH_COVERAGE) \
	python3 scripts/coverage.py

check-stack-overflow: build/minyarc build/minyar-runtime.o build/tooling/tests/stack-overflow
	$(LIMITED) ./build/tooling/tests/stack-overflow

.PHONY: check-stack-overflow-sanitize
check-stack-overflow-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o runtime/minyar_runtime.c $(RUNTIME_HEADERS) build/tooling/tests/stack-guard-sanitizer build/tooling/tests/stack-overflow
	$(SANITIZER_LIMITED) ./build/tooling/tests/stack-guard-sanitizer --clang "$(LLVM_CC)"
	ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/stack-overflow

# Cross-platform per-commit gate. Heavier memory-profile and performance
# matrices remain in the Linux evidence runner and the full `make check` gate.
check-windows-large-file:
	python3 tests/windows-large-file.py

check-portable: check-smoke check-regressions check-diagnostics check-conformance check-runtime-unit check-modules check-fuzz check-stack-overflow check-windows-large-file build/compiler-stage3.ll build/minyar-runtime.o build/tooling/tests/compiler-behavior
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/compiler-behavior --profile core --ir build/compiler-stage3.ll

check-mutation: build/stage0 build/minyarc build/minyar-runtime.o build/tooling/tests/list-access build/tooling/tests/checked-arithmetic build/tooling/tools/clang-driver build/tooling/tests/mutation
	$(LIMITED) ./build/tooling/tests/mutation

.PHONY: check-mutation-score-harness
check-mutation-score-harness: build/tooling/tests/mutation-score-harness build/tooling/tests/mutation-score
	$(LIMITED) ./build/tooling/tests/mutation-score-harness "$(CURDIR)/build/tooling/tests/mutation-score"

check-mutation-score: check-mutation-score-harness build/tooling/tools/clang-driver build/tooling/tests/regressions build/tooling/tests/list-literals build/tooling/tests/linkage build/tooling/tests/mutation-score build/tooling/tests/mutation-coverage build/stage0 build/minyarc build/minyarc-modules build/minyar-compiler-runtime.ll build/minyar-runtime.o build/tooling/tests/diagnostics build/tooling/tests/conformance build/tooling/tests/list-access build/tooling/tests/readonly-parameters build/tooling/tests/symbol-order build/tooling/tools/test-clang build/tooling/tools/clang-cache build/tooling/tests/compiler-contracts build/tooling/tests/compiler-hardening build/tooling/tests/binary-expression-ownership build/tooling/tests/source-map
	MINYAR_MIN_MUTATION_SCORE=$(MIN_MUTATION_SCORE) $(LIMITED) ./build/tooling/tests/mutation-score


build/tooling/tests/performance-test build/tooling/tests/scaling-test: TOOL_NATIVE = tests/performance-resources.c
build/tooling/tests/performance-test build/tooling/tests/scaling-test: tests/performance-resources.c
check-performance: build/minyarc build/minyar-runtime.o build/compiler-stage3.ll build/minyar-compiler-runtime.ll build/tooling/tests/compiler-behavior build/tooling/tests/performance-test
	$(LIMITED) ./build/tooling/tests/performance-test

check-scaling: build/minyarc build/tooling/tests/scaling-test
	$(LIMITED) ./build/tooling/tests/scaling-test

build/tooling/tests/self-compile-budget: TOOL_RUNTIME = build/testing/cycle-runtime.o
build/tooling/tests/self-compile-budget: TOOL_NATIVE = tests/performance-resources.c
build/tooling/tests/self-compile-budget: build/testing/cycle-runtime.o tests/performance-resources.c
# Run absolute self-compilation checks without background scheduling.
check-budget: build/minyarc build/compiler-stage3.ll build/tooling/tests/self-compile-budget
	./build/tooling/tests/self-compile-budget

build/minyarc-budget-previous: build/compiler-budget-previous.ll build/minyar-compiler-runtime.ll
	"$(LLVM_CC)" $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $(filter %.ll %.o,$^) $(LDLIBS) -o $@

.PHONY: check-sanitized-fixed-point check-generated-sanitizer
check-generated-sanitizer: build/tooling/tests/generated-stack-sanitizer build/tooling/tools/sanitize-llvm
	$(SANITIZER_LIMITED) ./build/tooling/tests/generated-stack-sanitizer --clang "$(LLVM_CC)"

.PHONY: check-binary-expressions
check-binary-expressions: build/minyarc build/minyarc-sanitize build/minyar-runtime.o build/ownership-runtime.o build/tooling/tests/binary-expression-ownership
	$(LIMITED) ./build/tooling/tests/binary-expression-ownership
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/binary-expression-ownership

check: check-binary-expressions

.PHONY: check-integer-text-cache
check-integer-text-cache: build/tooling/tests/integer-text-cache
	$(SANITIZER_LIMITED) ./build/tooling/tests/integer-text-cache --clang "$(LLVM_CC)"

check: check-integer-text-cache

.PHONY: check-tokenizer-storage
check-tokenizer-storage: build/minyarc build/tooling/tests/tokenizer-storage
	$(SANITIZER_LIMITED) ./build/tooling/tests/tokenizer-storage --clang "$(LLVM_CC)"

check: check-tokenizer-storage

.PHONY: check-temporary-owner-admission
check-temporary-owner-admission: build/tooling/tests/temporary-owner-admission
	$(SANITIZER_LIMITED) ./build/tooling/tests/temporary-owner-admission --clang "$(LLVM_CC)"

check: check-temporary-owner-admission
# Verify that sanitizer coverage exercises the same compiler as the native
# fixed point, including when a retained build artifact has misleading times.
check-sanitized-fixed-point: build/minyarc-sanitize build/compiler-stage3.ll build/minyar-runtime.o build/tooling/tests/compiler-behavior
	ASAN_OPTIONS=detect_leaks=0 $(SANITIZER_LIMITED) ./build/minyarc-sanitize build/compiler.min build/compiler-sanitized.ll
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/compiler-behavior --ir build/compiler-sanitized.ll --ir build/compiler-stage3.ll

.PHONY: check-sanitize-core
check-sanitize: check-generated-sanitizer check-sanitized-fixed-point check-stack-overflow-sanitize check-sanitize-core

check-sanitize-core: build/tooling/tests/memory build/minyarc-sanitize build/minyar-runtime.o build/minyar-runtime-sanitize.o build/runtime-unit-sanitize build/tooling/tests/regressions build/tooling/tools/clang-driver build/tooling/tests/ownership
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize $(SANITIZER_LIMITED) sh tests/run-module-tests.sh
	ASAN_OPTIONS=detect_leaks=0 $(SANITIZER_LIMITED) python3 tests/fuzz.py --compiler build/minyarc-sanitize --cases 100 --hostile-timeout 15
	ASAN_OPTIONS=detect_leaks=0 $(SANITIZER_LIMITED) ./build/runtime-unit-sanitize
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/regressions
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/ownership
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/memory --shared

check-stress: build/minyarc build/minyar-runtime.o
	MINYAR_FUZZ_CASES=2000 $(LIMITED) python3 tests/fuzz.py

check: doctor check-smoke check-release-build check-recursive-data check-compact-ownership check-adversarial check-ownership-mutation check-regressions check-memory check-runtime-unit check-modules check-fuzz check-stack-overflow check-mutation check-performance check-scaling check-budget check-sanitize check-ownership check-examples

.PHONY: check-examples
check-examples: build/stage0 build/minyarc build/compiler-stage3.ll build/hello build/language-tour build/records build/compiler-bootstrap build/hello-self-hosted build/integer-overflow build/divide-by-zero build/text-and-files build/lists build/newlines build/top-level build/top-level-exit build/list-out-of-bounds build/text-indexing build/text-slice-out-of-bounds build/minyar-runtime.o build/tooling/tests/compiler-behavior
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/compiler-behavior --profile core --ir build/compiler-stage3.ll
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
	grep -q "record field 'values' needs List<Text>, not Integer" build/record-immutable-error.txt
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

build/tooling/tests/ownership: TOOL_NATIVE = tests/sha256-test-native.c
build/tooling/tests/ownership: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/ownership: tests/sha256-test-native.c
check-ownership: build/minyarc build/minyar-runtime.o build/ownership-runtime.o build/tooling/tests/memory build/tooling/tests/ownership
	$(LIMITED) ./build/tooling/tests/ownership
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/ownership
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/memory --shared

build/tooling/tests/adversarial: TOOL_NATIVE = tests/sha256-test-native.c
build/tooling/tests/adversarial: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/adversarial: tests/sha256-test-native.c
check-adversarial: build/minyarc build/minyar-runtime.o build/minyarc-sanitize build/ownership-runtime.o build/tooling/tests/adversarial
	$(LIMITED) ./build/tooling/tests/adversarial
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/adversarial

check-ownership-mutation: build/tooling/tests/ownership-mutation
	$(LIMITED) ./build/tooling/tests/ownership-mutation

check-ownership-stress: build/minyarc build/minyarc-sanitize build/minyar-runtime.o build/ownership-runtime.o build/tooling/tests/ownership
	MINYAR_OWNERSHIP_GRAPHS=256 MINYAR_OWNERSHIP_SEEDS=32 $(LIMITED) ./build/tooling/tests/ownership
	ASAN_OPTIONS=detect_leaks=0 MINYAR_OWNERSHIP_GRAPHS=256 MINYAR_OWNERSHIP_SEEDS=32 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/ownership

.PHONY: check-recursive-data check-bounded check-compact-ownership

.PHONY: check-scalar-record-storage check-compiler-slice-cache check-readonly-parameters
check: check-scalar-record-storage check-compiler-slice-cache check-readonly-parameters

.PHONY: check-scalar-record-initialization
check: check-scalar-record-initialization

check-scalar-record-initialization: build/minyarc build/minyarc-sanitize build/minyar-runtime.o build/ownership-runtime.o build/tooling/tests/scalar-record-initialization
	$(LIMITED) ./build/tooling/tests/scalar-record-initialization --compiler build/minyarc --runtime build/minyar-runtime.o --clang "$(LLVM_CC)"
	ASAN_OPTIONS=detect_leaks=0 $(SANITIZER_LIMITED) ./build/tooling/tests/scalar-record-initialization --compiler build/minyarc-sanitize --runtime build/ownership-runtime.o --clang "$(LLVM_CC)" --sanitize

check-scalar-record-storage: build/minyarc build/minyarc-sanitize build/minyar-runtime.o build/ownership-runtime.o build/tooling/tests/scalar-lookahead-budget build/tooling/tests/scalar-record-storage build/tooling/tests/production-scalar-storage build/tooling/tests/scalar-record-mutation
	$(LIMITED) ./build/tooling/tests/scalar-lookahead-budget
	$(LIMITED) ./build/tooling/tests/scalar-record-storage
	$(LIMITED) ./build/tooling/tests/production-scalar-storage
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/scalar-record-storage
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/production-scalar-storage
	$(SANITIZER_LIMITED) ./build/tooling/tests/scalar-record-mutation

check-readonly-parameters: build/minyarc build/minyarc-sanitize build/minyar-runtime.o build/ownership-runtime.o build/tooling/tests/readonly-parameters build/tooling/tests/production-readonly-parameters
	$(LIMITED) ./build/tooling/tests/readonly-parameters
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/readonly-parameters
	$(LIMITED) ./build/tooling/tests/production-readonly-parameters
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/production-readonly-parameters

check-compiler-slice-cache: build/tooling/tests/compiler-slice-cache
	$(LIMITED) ./build/tooling/tests/compiler-slice-cache

check-compact-ownership: build/minyarc build/minyarc-sanitize build/ownership-runtime.o build/minyar-compiler-runtime.ll build/tooling/tests/compact-ownership
	$(LIMITED) ./build/tooling/tests/compact-ownership
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/compact-ownership

.PHONY: check-text-view-budget
check-text-view-budget: build/tooling/tests/text-view-budget
	$(SANITIZER_LIMITED) ./build/tooling/tests/text-view-budget --clang "$(LLVM_CC)"

check: check-text-view-budget

# These matrices compile many sanitizer variants and reserve large virtual
# heaps. Keep them explicitly requested, outside the ordinary check target.
.PHONY: check-memory-profiles check-unary-pairs check-fused-unary
check-fused-unary: build/tooling/tests/fused-unary-regressions build/tooling/tests/fused-work-regressions
	$(SANITIZER_LIMITED) ./build/tooling/tests/fused-unary-regressions --clang "$(LLVM_CC)"
	$(SANITIZER_LIMITED) ./build/tooling/tests/fused-work-regressions --clang "$(LLVM_CC)"

build/tooling/tests/unary-pair-regressions: TOOL_NATIVE = runtime/native/sha256.c
build/tooling/tests/unary-pair-regressions: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/unary-pair-regressions: runtime/native/sha256.c
check-unary-pairs: check-fused-unary build/tooling/tests/unary-pair-regressions
	$(SANITIZER_LIMITED) ./build/tooling/tests/unary-pair-regressions --clang "$(LLVM_CC)"

check-memory-profiles: build/minyar-runtime-system.o check-unary-pairs check-text-view-budget build/tooling/tests/system-configurations build/tooling/tests/lazy-configurations build/tooling/tests/memory-profile-regressions
	$(SANITIZER_LIMITED) ./build/tooling/tests/memory-profile-regressions --runtime-source runtime/minyar_runtime.c --suite focused --clang "$(LLVM_CC)"
	$(SANITIZER_LIMITED) ./build/tooling/tests/system-configurations
	$(SANITIZER_LIMITED) ./build/tooling/tests/lazy-configurations --clang "$(LLVM_CC)"

build/tooling/tests/production-memory: TOOL_NATIVE = tests/sha256-test-native.c
build/tooling/tests/production-memory: TOOL_LIBS = $(TOOL_CRYPTO)
build/tooling/tests/production-memory: tests/sha256-test-native.c
check-recursive-data: build/minyarc build/minyarc-sanitize build/minyar-runtime.o build/ownership-runtime.o build/tooling/tests/recursive-data build/tooling/experiments/memory/production-contract-model build/tooling/tests/recursive-mutation build/tooling/tests/production-memory
	$(LIMITED) ./build/tooling/tests/recursive-data
	$(LIMITED) ./build/tooling/tests/production-memory
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/recursive-data
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/production-memory
	$(LIMITED) ./build/tooling/experiments/memory/production-contract-model
	$(SANITIZER_LIMITED) ./build/tooling/tests/recursive-mutation

check-bounded: build/minyarc build/minyar-runtime-bounded.o build/bounded-runtime build/bounded-runtime-sanitize build/bounded-ownership-runtime.o build/production-live-oracle build/production-frame-oracle build/bounded-list-capacity build/bounded-list-capacity-sanitize build/tooling/tests/recursive-data build/tooling/tests/bounded-configurations build/tooling/tests/production-memory
	$(LIMITED) ./build/bounded-runtime
	ASAN_OPTIONS=detect_leaks=0 $(SANITIZER_LIMITED) ./build/bounded-runtime-sanitize
	ASAN_OPTIONS=detect_leaks=0 $(SANITIZER_LIMITED) ./build/production-live-oracle
	ASAN_OPTIONS=detect_leaks=0 $(SANITIZER_LIMITED) ./build/production-frame-oracle
	$(LIMITED) ./build/bounded-list-capacity
	ASAN_OPTIONS=detect_leaks=0 $(SANITIZER_LIMITED) ./build/bounded-list-capacity-sanitize
	$(LIMITED) ./build/tooling/tests/bounded-configurations
	MINYAR_TEST_RUNTIME=./build/minyar-runtime-bounded.o $(LIMITED) ./build/tooling/tests/recursive-data
	MINYAR_TEST_RUNTIME=./build/minyar-runtime-bounded.o $(LIMITED) ./build/tooling/tests/production-memory
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_RUNTIME=./build/bounded-ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/recursive-data
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_RUNTIME=./build/bounded-ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/production-memory

.PHONY: check-incremental-modules
check-incremental-modules: build/minyarc-errors-request build/minyarc-modules build/module-compiler-stage2.ll build/module-compiler-stage3.ll build/minyar-module-build build/minyar-runtime.o build/minyar-runtime-release.ll build/minyarc-callbacks build/tooling/tests/recursive-data build/tooling/tools/clang-driver build/tooling/tests/compiler-behavior build/tooling/tests/ownership
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/compiler-behavior --profile core --ir build/module-compiler-stage3.ll
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
check-incremental-modules-sanitize: build/minyarc-modules-sanitize build/minyar-module-build-sanitize build/minyarc-modules build/minyar-module-build build/minyar-runtime.o build/minyar-runtime-sanitize.o build/ownership-runtime.o build/minyarc-callbacks-sanitize build/module-compiler-stage2.ll build/minyar-compiler-runtime.ll build/tooling/tests/recursive-data build/tooling/tests/ownership
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-modules-sanitize MINYAR_MODULE_CALLBACK_COMPILER=./build/minyarc-callbacks-sanitize $(SANITIZER_LIMITED) python3 tests/incremental-modules.py
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

check-toolchain-portability: build/tooling/tools/clang-driver
	python3 tests/toolchain-portability.py

.PHONY: check-cold-bootstrap
check-cold-bootstrap:
	MINYAR_TEST_CLANG="$(LLVM_CC)" python3 tests/toolchain-bootstrap.py

check-module-driver-options: build/tooling/tests/module-driver-options
	./build/tooling/tests/module-driver-options

check-native-graphics: build/tooling/tests/native-graphics
	./build/tooling/tests/native-graphics

check-fuzz-harness:
	python3 tests/fuzz-harness.py

check-coverage-harness:
	python3 tests/coverage-harness.py

.PHONY: check-coverage-inlining
check-coverage-inlining:
	MINYAR_TEST_CLANG="$${MINYAR_TEST_CLANG:-$(LLVM_CC)}" python3 tests/coverage-inlining.py

check-runtime-bytes: build/tooling/tests/runtime-bytes
	$(LIMITED) ./build/tooling/tests/runtime-bytes --clang "$(LLVM_CC)"

check-runtime-bytes-sanitize: build/tooling/tests/runtime-bytes
	$(SANITIZER_LIMITED) ./build/tooling/tests/runtime-bytes --clang "$(LLVM_CC)" --sanitize

.PHONY: check-runtime-traps check-runtime-traps-sanitize
check-runtime-traps: build/tooling/tests/runtime-traps
	$(LIMITED) ./build/tooling/tests/runtime-traps --clang "$(LLVM_CC)"

check-runtime-traps-sanitize: build/tooling/tests/runtime-traps
	$(SANITIZER_LIMITED) ./build/tooling/tests/runtime-traps --clang "$(LLVM_CC)" --sanitize

check-compiler-hardening: build/minyarc build/minyarc-modules build/minyar-runtime.o build/tooling/tests/compiler-hardening
	$(LIMITED) ./build/tooling/tests/compiler-hardening

.PHONY: check-compiler-hardening-sanitize
check-compiler-hardening-sanitize: build/minyarc-sanitize build/minyarc-modules-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/compiler-hardening
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_MODULE_COMPILER=./build/minyarc-modules-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/compiler-hardening

.PHONY: check-list-access check-list-access-sanitize
check-list-access: build/minyarc build/minyar-runtime.o build/tooling/tests/list-access
	$(LIMITED) ./build/tooling/tests/list-access

check-list-access-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/list-access
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/list-access

.PHONY: check-checked-arithmetic check-checked-arithmetic-sanitize check-checked-results check-checked-results-sanitize check-checked-results-frontends check-checked-results-frontends-sanitize
check-checked-arithmetic: build/minyarc build/minyar-runtime.o build/tooling/tests/checked-arithmetic
	$(LIMITED) ./build/tooling/tests/checked-arithmetic

check-checked-arithmetic-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/checked-arithmetic
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/checked-arithmetic

check-checked-results: build/minyarc build/minyar-runtime.o build/tooling/tests/checked-results
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/checked-results

check-checked-results-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/checked-results
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/checked-results

check-checked-results-frontends: build/minyarc-modules build/minyarc-callbacks build/minyarc-errors build/minyar-runtime.o build/tooling/tests/checked-results-frontends
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/checked-results-frontends

check-checked-results-frontends-sanitize: build/minyarc-modules-sanitize build/minyarc-callbacks-sanitize build/minyarc-errors-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/checked-results-frontends
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/checked-results-frontends

check-portable check: check-checked-arithmetic check-checked-results check-checked-results-frontends
check-sanitize: check-checked-arithmetic-sanitize check-checked-results-sanitize check-checked-results-frontends-sanitize

.PHONY: check-checked-scalars check-checked-scalars-sanitize
check-checked-scalars: build/minyarc build/minyar-runtime.o build/tooling/tests/checked-scalars
	$(LIMITED) ./build/tooling/tests/checked-scalars

check-checked-scalars-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/checked-scalars
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/checked-scalars

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
check-bootstrap-portability: build/compiler.min build/tooling/tests/bootstrap-portability
	MINYAR_TEST_CLANG="$(LLVM_CC)" ./build/tooling/tests/bootstrap-portability

check-portable: check-bootstrap-portability
check: check-bootstrap-portability

.PHONY: check-bootstrap-records
check-bootstrap-records: build/stage0 build/tooling/tests/bootstrap-records
	MINYAR_TEST_CLANG="$(LLVM_CC)" ./build/tooling/tests/bootstrap-records

check-portable check: check-bootstrap-records

.PHONY: check-measurement-stats
build/tooling/tests/measurement-stats: TOOL_RUNTIME = build/testing/cycle-runtime.o
build/tooling/tests/measurement-stats: build/testing/cycle-runtime.o
check-measurement-stats: build/tooling/tests/measurement-stats
	./build/tooling/tests/measurement-stats

check-portable check: check-measurement-stats

.PHONY: check-budget-harness
build/tooling/tests/self-compile-budget-harness: TOOL_RUNTIME = build/testing/cycle-runtime.o
build/tooling/tests/self-compile-budget-harness: TOOL_NATIVE = tests/performance-resources.c
build/tooling/tests/self-compile-budget-harness: build/testing/cycle-runtime.o tests/performance-resources.c
check-budget-harness: build/tooling/tests/self-compile-budget-harness
	./build/tooling/tests/self-compile-budget-harness

check-portable check: check-budget-harness
check-budget: check-budget-harness

.PHONY: check-source-map check-source-map-sanitize
check-source-map: build/minyarc build/minyarc-modules build/minyar-runtime.o build/tooling/tests/source-map
	$(LIMITED) ./build/tooling/tests/source-map

check-source-map-sanitize: build/minyarc-sanitize build/minyarc-modules-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/source-map
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_MODULE_COMPILER=./build/minyarc-modules-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/source-map

check-portable check: check-source-map
check-sanitize: check-source-map-sanitize

.PHONY: check-scalar-path check-scalar-study-harness
build/tooling/experiments/memory/checked-scalars-study.ll: experiments/memory/study-support.min experiments/memory/measurement-stats.min tests/cpython-random.min
build/tooling/experiments/memory/checked-scalars-study: TOOL_RUNTIME = build/testing/cycle-runtime.o
build/tooling/experiments/memory/checked-scalars-study: build/testing/cycle-runtime.o
build/tooling/tests/scalar-study-harness.ll: experiments/memory/study-support.min
build/tooling/tests/scalar-study-harness: TOOL_RUNTIME = build/testing/cycle-runtime.o
build/tooling/tests/scalar-study-harness: build/testing/cycle-runtime.o
check-scalar-study-harness: build/tooling/tests/scalar-study-harness build/tooling/experiments/memory/checked-scalars-study
	./build/tooling/tests/scalar-study-harness "$(CURDIR)/build/tooling/tests/scalar-study-harness" "$(CURDIR)/build/tooling/experiments/memory/checked-scalars-study"

check-scalar-path: check-scalar-study-harness build/minyarc build/tooling/experiments/memory/checked-scalars-study
	$(LIMITED) ./build/tooling/experiments/memory/checked-scalars-study

check: check-scalar-path
check-portable: check-scalar-study-harness

.PHONY: check-stack-limits
check-stack-limits: build/tooling/tests/stack-limits tests/stack-limits.c
	MINYAR_TEST_CLANG="$(LLVM_CC)" ./build/tooling/tests/stack-limits

check-portable check: check-stack-limits

.PHONY: check-linkage check-linkage-sanitize
check-linkage: build/stage0 build/minyarc build/minyarc-modules build/minyar-runtime.o build/tooling/tests/linkage
	$(LIMITED) ./build/tooling/tests/linkage

check-linkage-sanitize: build/stage0 build/minyarc-sanitize build/minyarc-modules-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/linkage
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_MODULE_COMPILER=./build/minyarc-modules-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/linkage

check-portable check: check-linkage
check-sanitize: check-linkage-sanitize

.PHONY: check-symbol-order check-symbol-order-sanitize
check-symbol-order: build/minyarc build/minyar-runtime.o build/tooling/tests/symbol-order
	$(LIMITED) ./build/tooling/tests/symbol-order

check-symbol-order-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/symbol-order
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/symbol-order

check-portable check: check-symbol-order
check-sanitize: check-symbol-order-sanitize

# Focused original adaptations and runtime invariants; no upstream corpus or
# archived research baseline is required by these maintained regressions.
.PHONY: check-peer-semantics check-peer-semantics-sanitize check-memory-regressions check-memory-regressions-sanitize check-bootstrap-policy
PEER_SEMANTIC_SUITES = peer-memory-nim-koka-lean peer-memory-nim-koka-followups
PEER_SEMANTIC_TOOLS = build/tooling/tests/peer-research-semantics build/tooling/tests/peer-research-reachability build/tooling/tests/memory-research-peer-projections
$(PEER_SEMANTIC_TOOLS): TOOL_NATIVE = tests/sha256-test-native.c
$(PEER_SEMANTIC_TOOLS): TOOL_LIBS = $(TOOL_CRYPTO)
$(PEER_SEMANTIC_TOOLS): tests/sha256-test-native.c

check-peer-semantics: build/minyarc build/minyar-runtime.o $(PEER_SEMANTIC_TOOLS)
	@set -e; for suite in $(PEER_SEMANTIC_SUITES); do $(LIMITED) python3 "tests/$$suite.py"; done
	@set -e; for tool in $(PEER_SEMANTIC_TOOLS); do $(LIMITED) "./$$tool"; done

check-peer-semantics-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o $(PEER_SEMANTIC_TOOLS)
	@set -e; for suite in $(PEER_SEMANTIC_SUITES); do ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 "tests/$$suite.py"; done
	@set -e; for tool in $(PEER_SEMANTIC_TOOLS); do ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) "./$$tool"; done

check-memory-regressions: build/tooling/tests/memory-research-regressions
	$(LIMITED) ./build/tooling/tests/memory-research-regressions --clang "$(LLVM_CC)"

check-memory-regressions-sanitize: build/tooling/tests/memory-research-regressions
	$(SANITIZER_LIMITED) ./build/tooling/tests/memory-research-regressions --clang "$(LLVM_CC)" --sanitize

check-bootstrap-policy:
	python3 tests/launcher-bootstrap-policy.py

check-portable check: check-peer-semantics check-memory-regressions check-bootstrap-policy
check-sanitize: check-peer-semantics-sanitize check-memory-regressions-sanitize

# TLS 1.3 against a local OpenSSL server, through the hosted http, tls, crypto and net packages.
.PHONY: check-tls check-tls-sanitize
check-tls: build/minyarc build/tooling/tests/tls-local-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/tls-local-test

check-tls-sanitize: build/minyarc build/tooling/tests/tls-local-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/tls-local-test --sanitize

check check-portable: check-tls

QUIC_TEST_TOOLS = quic-ack-test quic-pto-test quic-suite-test quic-crypto-test quic-wire-test quic-dispatch-test \
    quic-transport-test quic-migration-cids-test quic-cipher-policy-test
$(QUIC_TEST_TOOLS:%=build/tooling/tests/%.ll): tests/quic-test-support.min
build/tooling/tests/quic-migration-cids-test.ll build/tooling/tests/quic-cipher-policy-test.ll: tests/quic-protocol-support.min
build/tooling/tests/quic-wire-test.ll: tests/cpython-random.min

# ACK scheduling gates retain both native and sanitizer optimizations.
.PHONY: check-quic-ack check-quic-ack-sanitize
check-quic-ack: build/minyarc tests/quic-ack.min build/tooling/tests/quic-ack-test | build
	@set -e; artifacts=$$(mktemp -d "$(abspath build)/quic-ack-native.XXXXXXXX"); MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/quic-ack-test --optimization both --artifacts "$$artifacts"

check-quic-ack-sanitize: build/minyarc tests/quic-ack.min build/tooling/tests/quic-ack-test | build
	@set -e; artifacts=$$(mktemp -d "$(abspath build)/quic-ack-sanitize.XXXXXXXX"); MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/quic-ack-test --optimization both --sanitize --artifacts "$$artifacts"

check check-portable check-quic: check-quic-ack
check-sanitize check-quic-sanitize: check-quic-ack-sanitize

# Handshake PTO virtual-clock modes use fresh absolute evidence directories.
.PHONY: check-quic-pto check-quic-pto-sanitize
check-quic-pto: build/minyarc tests/quic-pto.min build/tooling/tests/quic-pto-test | build
	@set -e; artifacts=$$(mktemp -d "$(abspath build)/quic-pto-native-O0.XXXXXXXX"); MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/quic-pto-test --optimization 0 --artifacts "$$artifacts"
	@set -e; artifacts=$$(mktemp -d "$(abspath build)/quic-pto-native-O2.XXXXXXXX"); MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/quic-pto-test --optimization 2 --artifacts "$$artifacts"

check-quic-pto-sanitize: build/minyarc tests/quic-pto.min build/tooling/tests/quic-pto-test | build
	@set -e; artifacts=$$(mktemp -d "$(abspath build)/quic-pto-sanitize-O1.XXXXXXXX"); MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/quic-pto-test --optimization 1 --sanitize --artifacts "$$artifacts"

check check-portable check-quic: check-quic-pto
check-sanitize check-quic-sanitize: check-quic-pto-sanitize

# Pure controller regression; no privileged runner, Docker, or peer provisioning.
.PHONY: check-quic-interop-results
check-quic-interop-results:
	python3 tests/quic-interop-results.py

check check-portable check-quic check-quic-sanitize: check-quic-interop-results

# Native suite levels are independent children so a parallel runner overlaps them.
.PHONY: check-quic check-quic-sanitize check-quic-native-O0 check-quic-native-O2 check-quic-native-sanitize
QUIC_SUITE_TOOLS = build/tooling/tests/quic-suite-test build/tooling/tests/quic-crypto-test build/tooling/tests/quic-wire-test \
    build/tooling/tests/quic-dispatch-test build/tooling/tests/quic-transport-test build/tooling/tests/quic-migration-cids-test \
    build/tooling/tests/securecrypto-test build/tooling/tests/tls-server-test build/tooling/tests/tls-keyshare-test \
    build/tooling/tests/tls-signing-usage-test build/tooling/tests/tls-validity-test build/tooling/tests/yamux-churn-test \
    build/tooling/tests/transport-cancel-test build/tooling/tests/tls-resumption-expiry-test \
    build/tooling/tests/tls-handshake-validity-test build/tooling/tests/transport-go-test

check-quic-native-O0: build/minyarc $(QUIC_SUITE_TOOLS)
	MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/quic-suite-test --artifacts build/quic-native-O0

check-quic-native-O2: build/minyarc $(QUIC_SUITE_TOOLS)
	MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/quic-suite-test --optimization 2 --artifacts build/quic-native-O2

check-quic: build/minyarc check-quic-native-O0 check-quic-native-O2

check-quic-native-sanitize: build/minyarc $(QUIC_SUITE_TOOLS)
	MINYAR_CLANG="$(LLVM_CC)" MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/quic-suite-test --sanitize --artifacts build/quic-sanitize

check-quic-sanitize: build/minyarc check-quic-native-sanitize

check: check-quic
check-sanitize: check-quic-sanitize

# Pinned Quinn peer in every CI mode. Modes that build the same Minyar endpoint
# reuse it: ten endpoint builds become four within one recipe.
.PHONY: check-quic-quinn
check-quic-quinn: build/minyarc | build
	@set -e; cache=$$(mktemp -d "$(abspath build)/quic-quinn-programs.XXXXXXXX"); trap 'rm -rf "$$cache"' EXIT; export MINYAR_TEST_PROGRAM_CACHE="$$cache"; \
	$(LIMITED) python3 tests/quic-quinn.py; \
	MINYAR_QUINN_KEY_UPDATE=1 $(LIMITED) python3 tests/quic-quinn.py; \
	$(LIMITED) python3 tests/quic-quinn.py --migration; \
	$(LIMITED) python3 tests/quic-quinn.py --resumption; \
	$(LIMITED) python3 tests/quic-quinn.py --early

.PHONY: check-redis-protocol check-redis-protocol-sanitize check-redis-pipeline check-redis-pipeline-sanitize
check-redis-protocol: build/minyarc build/minyar-runtime.o build/tooling/tests/redis-protocol-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/redis-protocol-test

check-redis-protocol-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/redis-protocol-test
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/redis-protocol-test

check-redis-pipeline: build/minyarc build/minyar-runtime.o build/tooling/tests/redis-pipeline-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/redis-pipeline-test

check-redis-pipeline-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/redis-pipeline-test
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/redis-pipeline-test

check check-portable: check-redis-protocol check-redis-pipeline
check-sanitize: check-redis-protocol-sanitize check-redis-pipeline-sanitize

.PHONY: check-native-cache
check-native-cache: build/tooling/tools/clang-driver
	$(LIMITED) python3 tests/native-object-cache.py

.PHONY: check-package-native-inputs
check-package-native-inputs: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/package-native-inputs.py

check check-portable: check-package-native-inputs

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


.PHONY: check-module-test-driver check-build-wiring
build/tooling/tests/module-test-driver: build/tooling/tools/clang-driver
check-module-test-driver: build/minyarc build/minyar-runtime.o build/tooling/tests/module-test-driver build/tooling/tools/clang-driver
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/module-test-driver

check-build-wiring: build/tooling/tests/suite-catalogue
	python3 tests/build-wiring.py

check check-portable: check-module-test-driver check-build-wiring

.PHONY: check-tls-validity check-tls-validity-sanitize check-tls-resumption-expiry check-tls-resumption-expiry-sanitize
check-tls-validity: build/minyarc build/tooling/tests/tls-validity-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/tls-validity-test

check-tls-validity-sanitize: build/minyarc build/tooling/tests/tls-validity-test
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/tls-validity-test --sanitize

check-tls-resumption-expiry: build/minyarc build/tooling/tests/tls-resumption-expiry-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/tls-resumption-expiry-test

check-tls-resumption-expiry-sanitize: build/minyarc build/tooling/tests/tls-resumption-expiry-test
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/tls-resumption-expiry-test --sanitize

check-tls: check-tls-validity check-tls-resumption-expiry
check-tls-sanitize: check-tls-validity-sanitize check-tls-resumption-expiry-sanitize

.PHONY: check-tls-keyshare check-tls-keyshare-sanitize check-tls-server check-tls-server-sanitize
check-tls-keyshare: build/minyarc build/tooling/tests/tls-keyshare-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/tls-keyshare-test

check-tls-keyshare-sanitize: build/minyarc build/tooling/tests/tls-keyshare-test
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/tls-keyshare-test --sanitize

check-tls-server: build/minyarc build/tooling/tests/tls-server-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/tls-server-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/tls-server-test --curve prime256v1

check-tls-server-sanitize: build/minyarc build/tooling/tests/tls-server-test
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/tls-server-test --sanitize
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/tls-server-test --sanitize --curve prime256v1

check-tls: check-tls-keyshare check-tls-server
check-tls-sanitize: check-tls-keyshare-sanitize check-tls-server-sanitize
check-sanitize: check-tls-sanitize

.PHONY: check-yamux-churn check-yamux-churn-sanitize check-transport-cancel check-transport-cancel-sanitize check-transport-go check-transport-go-sanitize
check-yamux-churn: build/minyarc build/tooling/tests/yamux-churn-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/yamux-churn-test

check-yamux-churn-sanitize: build/minyarc build/tooling/tests/yamux-churn-test
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/yamux-churn-test --sanitize

check-transport-cancel: build/minyarc build/tooling/tests/transport-cancel-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/transport-cancel-test

check-transport-cancel-sanitize: build/minyarc build/tooling/tests/transport-cancel-test
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/transport-cancel-test --sanitize

build/yamux-peer: tests/interop/yamux/main.go tests/interop/yamux/go.mod tests/interop/yamux/go.sum | build
	cd tests/interop/yamux && GOMAXPROCS=2 go build -mod=readonly -o "$(abspath $@)" .

# The ordinary and FIN-schedule runs share one compiled Minyar peer per recipe.
check-transport-go: build/minyarc build/yamux-peer build/tooling/tests/transport-go-test | build
	@set -e; cache=$$(mktemp -d "$(abspath build)/transport-go-programs.XXXXXXXX"); trap 'rm -rf "$$cache"' EXIT; export MINYAR_TEST_PROGRAM_CACHE="$$cache"; \
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/transport-go-test --peer-binary build/yamux-peer; \
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/transport-go-test --peer-binary build/yamux-peer --streams 1536; \
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/transport-go-test --fin-schedule

check-transport-go-sanitize: build/minyarc build/yamux-peer build/tooling/tests/transport-go-test | build
	@set -e; cache=$$(mktemp -d "$(abspath build)/transport-go-sanitize-programs.XXXXXXXX"); trap 'rm -rf "$$cache"' EXIT; export MINYAR_TEST_PROGRAM_CACHE="$$cache"; \
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/transport-go-test --peer-binary build/yamux-peer --sanitize; \
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/transport-go-test --peer-binary build/yamux-peer --streams 1536 --sanitize; \
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/transport-go-test --fin-schedule --sanitize

check check-portable: check-yamux-churn check-transport-cancel
check: check-transport-go
check-sanitize: check-yamux-churn-sanitize check-transport-cancel-sanitize check-transport-go-sanitize

.PHONY: check-tls-handshake-validity check-tls-handshake-validity-sanitize
check-tls-handshake-validity: build/minyarc build/tooling/tests/tls-handshake-validity-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/tls-handshake-validity-test

check-tls-handshake-validity-sanitize: build/minyarc build/tooling/tests/tls-handshake-validity-test
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/tls-handshake-validity-test --sanitize

check-tls: check-tls-handshake-validity
check-tls-sanitize: check-tls-handshake-validity-sanitize

.PHONY: check-tls-signing-usage check-tls-signing-usage-sanitize
check-tls-signing-usage: build/minyarc build/tooling/tests/tls-signing-usage-test
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/tls-signing-usage-test

check-tls-signing-usage-sanitize: build/minyarc build/tooling/tests/tls-signing-usage-test
	$(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) ./build/tooling/tests/tls-signing-usage-test --sanitize

check-tls: check-tls-signing-usage
check-tls-sanitize: check-tls-signing-usage-sanitize

# Real unsafe generated-program accesses must fail after the public link driver.
.PHONY: check-generated-llvm-sanitizer
# Keep the override one shell argument and translate native Windows spellings.
GENERATED_SANITIZER_QUOTE = '$(subst ','"'"',$(1))'
GENERATED_SANITIZER_CLANG = $(if $(MINYAR_SANITIZER_CLANG),$(shell sh tools/toolchain.sh host-path $(call GENERATED_SANITIZER_QUOTE,$(MINYAR_SANITIZER_CLANG))),$(LLVM_CC))
GENERATED_SANITIZER_PATH = $(if $(MINYAR_SANITIZER_CLANG),$(shell sh tools/toolchain.sh host-directory $(call GENERATED_SANITIZER_QUOTE,$(GENERATED_SANITIZER_CLANG))):$(PATH),$(PATH))
GENERATED_SANITIZER_INPUTS = tests/generated-llvm-sanitizer.py tests/generated-llvm-sanitizer.min tests/llvm_sanitizer.py tests/clang_helpers.py tests/test_evidence.py build/tooling/tools/clang-driver tools/sanitizer_llvm.py tools/toolchain.sh runtime/minyar_runtime.c $(RUNTIME_HEADERS)
check-generated-llvm-sanitizer: build/minyarc $(GENERATED_SANITIZER_INPUTS) | build
	@set -e; artifacts=$$(mktemp -d "$(abspath build)/generated-llvm-sanitizer-XXXXXXXX"); PATH="$(GENERATED_SANITIZER_PATH)" MINYAR_TEST_CLANG=$(call GENERATED_SANITIZER_QUOTE,$(GENERATED_SANITIZER_CLANG)) $(SANITIZER_LIMITED) python3 tests/generated-llvm-sanitizer.py --artifacts "$$artifacts/run"
check check-portable check-sanitize: check-generated-llvm-sanitizer

# Actual UDP blackholes before/mid-session, then independent TCP mTLS/yamux.
.PHONY: check-transport-udp-fallback check-transport-udp-fallback-sanitize
check-transport-udp-fallback: build/minyarc build/yamux-peer | build
	@set -e; evidence=$$(mktemp -d "$(abspath build)/transport-udp-fallback-native.XXXXXXXX"); MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/transport-udp-fallback.py --go-binary build/yamux-peer --evidence "$$evidence"
check-transport-udp-fallback-sanitize: build/minyarc build/yamux-peer | build
	@set -e; evidence=$$(mktemp -d "$(abspath build)/transport-udp-fallback-sanitize.XXXXXXXX"); $(NATIVE_SANITIZER_ENV) MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/transport-udp-fallback.py --go-binary build/yamux-peer --sanitize --evidence "$$evidence"
check: check-transport-udp-fallback
check-sanitize: check-transport-udp-fallback-sanitize

.PHONY: check-raw-syscall check-raw-syscall-linux-native check-raw-syscall-sanitize check-raw-syscall-abi check-raw-syscall-frontends
.PHONY: check-raw-syscall-arm64
check-raw-syscall-arm64: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/raw-syscall-arm64.py

check-raw-syscall: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/raw-syscall.py

# Explicit: fails on other hosts, so a portability pass cannot stand in for
# native Linux kernel execution. Cross ABI checks are compile proof only.
check-raw-syscall-linux-native: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/raw-syscall.py --linux-native

check-raw-syscall-sanitize: build/minyarc-sanitize
	MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize $(SANITIZER_LIMITED) python3 tests/raw-syscall.py --sanitize

check-raw-syscall-abi: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/raw-syscall.py --abi

check-raw-syscall-frontends: build/minyarc-modules build/minyarc-callbacks build/minyarc-errors
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/raw-syscall.py --frontends

check check-portable: check-raw-syscall
check-sanitize: check-raw-syscall-sanitize

.PHONY: check-list-basics check-list-basics-sanitize check-map-basics check-map-basics-sanitize
check-list-basics: build/minyarc build/minyar-runtime.o build/tooling/tests/list-basics tests/list-basics.c $(RUNTIME_HEADERS)
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/list-basics
check-list-basics-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/list-basics tests/list-basics.c $(RUNTIME_HEADERS)
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/list-basics
check-map-basics: build/minyarc build/minyar-runtime.o build/tooling/tests/map-basics tests/memory-contracts-runtime.c $(RUNTIME_HEADERS)
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/map-basics
check-map-basics-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/map-basics tests/memory-contracts-runtime.c $(RUNTIME_HEADERS)
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/map-basics
check check-portable: check-list-basics check-map-basics
check-sanitize: check-list-basics-sanitize check-map-basics-sanitize

.PHONY: check-mutation-coverage
check-mutation-coverage: build/minyarc build/minyar-runtime.o build/tooling/tests/mutation-coverage
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/mutation-coverage
check check-portable: check-mutation-coverage
