CC ?= cc
CPPFLAGS ?= -isystem vendor
CFLAGS ?= -std=c11 -O2 -Wall -Wextra -Werror
LLVM_CC ?= clang
LLVM_FLAGS ?= -O2 -Wno-override-module
SANITIZER_FLAGS ?= -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module
COMPILER_RUNTIME_FLAGS ?= -DMINYAR_COMPILER_ARENA
COMPILER_LTO_FLAGS ?= -flto
BOUNDED_FLAGS ?= -DMINYAR_BOUNDED_HEAP=1
RUNTIME_HEADERS = runtime/minyar_heap.h runtime/minyar_rc.h runtime/minyar_pool.h runtime/minyar_bounded_rc.h
LIMITED ?= zsh scripts/with-limits.sh
SANITIZER_LIMITED ?= zsh scripts/with-sanitizer-limits.sh

.NOTPARALLEL:

.PHONY: all check check-smoke check-regressions check-memory check-runtime-unit check-ownership check-adversarial check-ownership-mutation check-ownership-stress check-budget check-fuzz check-modules check-mutation check-performance check-scaling check-sanitize check-stress doctor emit run clean

all: build/minyarc

build:
	mkdir -p build

build/stage0: bootstrap/stage0.c vendor/stb_ds.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $< -o $@

build/minyar-runtime.o: runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(LIMITED) $(LLVM_CC) $(LLVM_FLAGS) -c $< -o $@

# Ordinary program runtime, including automatic reclamation. Generic target
# attributes allow its checked hot paths to inline into Minyar's generated IR.
build/minyar-runtime-release.ll: runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(LIMITED) $(LLVM_CC) $(LLVM_FLAGS) -S -emit-llvm $< -o $@.tmp
	sed -E 's/"(target-cpu|target-features|tune-cpu)"="[^"]*" ?//g' $@.tmp > $@
	rm -f $@.tmp

# The compiler links its runtime as LLVM IR. Clang stamps C functions with the
# host's target-cpu and target-features, and LLVM refuses to inline a function
# into a caller whose features differ, so those attributes are stripped to let
# the runtime's small operations inline into generated code.
build/minyar-compiler-runtime.ll: runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(LIMITED) $(LLVM_CC) $(LLVM_FLAGS) $(COMPILER_RUNTIME_FLAGS) -S -emit-llvm $< -o $@.tmp
	sed -E 's/"(target-cpu|target-features|tune-cpu)"="[^"]*" ?//g' $@.tmp > $@
	rm -f $@.tmp

build/minyar-compiler-runtime-sanitize.o: runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(SANITIZER_LIMITED) $(LLVM_CC) $(SANITIZER_FLAGS) $(COMPILER_RUNTIME_FLAGS) -c $< -o $@

build/compiler-stage1.ll: src/compiler.min build/stage0
	$(LIMITED) ./build/stage0 $< -o $@

build/compiler-stage1: build/compiler-stage1.ll build/minyar-compiler-runtime.ll
	$(LIMITED) $(LLVM_CC) $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $^ -o $@

build/compiler-stage1-sanitize.ll: build/compiler-stage1.ll tests/llvm_sanitizer.py
	$(SANITIZER_LIMITED) python3 tests/llvm_sanitizer.py $< $@

build/minyarc-sanitize: build/compiler-stage1-sanitize.ll build/minyar-compiler-runtime-sanitize.o
	$(SANITIZER_LIMITED) $(LLVM_CC) $(SANITIZER_FLAGS) $^ -o $@

build/compiler-stage2.ll: src/compiler.min build/compiler-stage1
	$(LIMITED) ./build/compiler-stage1 $< $@

build/minyarc: build/compiler-stage2.ll build/minyar-compiler-runtime.ll
	$(LIMITED) $(LLVM_CC) $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $^ -o $@

build/compiler-stage3.ll: src/compiler.min build/minyarc
	$(LIMITED) ./build/minyarc $< $@

build/hello.ll: examples/hello.min build/minyarc
	./build/minyarc $< $@

build/hello: build/hello.ll build/minyar-runtime.o
	$(LLVM_CC) $(LLVM_FLAGS) $^ -o $@

build/language-tour.ll: examples/language-tour.min build/minyarc
	./build/minyarc $< $@

build/language-tour: build/language-tour.ll build/minyar-runtime.o
	$(LLVM_CC) $(LLVM_FLAGS) $^ -o $@

build/records.ll: examples/records.min build/minyarc
	./build/minyarc $< $@

build/records: build/records.ll build/minyar-runtime.o
	$(LLVM_CC) $(LLVM_FLAGS) $^ -o $@

build/compiler-bootstrap.ll: build/compiler-stage1.ll
	cp $< $@

build/compiler-bootstrap: build/compiler-bootstrap.ll build/minyar-compiler-runtime.ll
	$(LLVM_CC) $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $^ -o $@

build/hello-self-hosted.ll: examples/hello.min build/compiler-bootstrap
	./build/compiler-bootstrap $< $@

build/hello-self-hosted: build/hello-self-hosted.ll build/minyar-runtime.o
	$(LLVM_CC) $(LLVM_FLAGS) $^ -o $@

build/integer-overflow.ll: tests/runtime/integer-overflow.min build/minyarc
	./build/minyarc $< $@

build/integer-overflow: build/integer-overflow.ll build/minyar-runtime.o
	$(LLVM_CC) $(LLVM_FLAGS) $^ -o $@

build/divide-by-zero.ll: tests/runtime/divide-by-zero.min build/minyarc
	./build/minyarc $< $@

build/divide-by-zero: build/divide-by-zero.ll build/minyar-runtime.o
	$(LLVM_CC) $(LLVM_FLAGS) $^ -o $@

build/text-and-files.ll: tests/runtime/text-and-files.min build/minyarc
	./build/minyarc $< $@

build/text-and-files: build/text-and-files.ll build/minyar-runtime.o
	$(LLVM_CC) $(LLVM_FLAGS) $^ -o $@

build/lists.ll: tests/runtime/lists.min build/minyarc
	./build/minyarc $< $@

build/lists: build/lists.ll build/minyar-runtime.o
	$(LLVM_CC) $(LLVM_FLAGS) $^ -o $@

build/newlines.ll: tests/runtime/newlines.min build/minyarc
	./build/minyarc $< $@

build/newlines: build/newlines.ll build/minyar-runtime.o
	$(LLVM_CC) $(LLVM_FLAGS) $^ -o $@

build/top-level.ll: tests/runtime/top-level.min build/minyarc
	./build/minyarc $< $@

build/top-level: build/top-level.ll build/minyar-runtime.o
	$(LLVM_CC) $(LLVM_FLAGS) $^ -o $@

build/top-level-exit.ll: tests/runtime/top-level-exit.min build/minyarc
	./build/minyarc $< $@

build/top-level-exit: build/top-level-exit.ll build/minyar-runtime.o
	$(LLVM_CC) $(LLVM_FLAGS) $^ -o $@

build/list-out-of-bounds.ll: tests/runtime/list-out-of-bounds.min build/minyarc
	./build/minyarc $< $@

build/list-out-of-bounds: build/list-out-of-bounds.ll build/minyar-runtime.o
	$(LLVM_CC) $(LLVM_FLAGS) $^ -o $@

build/text-indexing.ll: tests/runtime/text-indexing.min build/minyarc
	./build/minyarc $< $@

build/text-indexing: build/text-indexing.ll build/minyar-runtime.o
	$(LLVM_CC) $(LLVM_FLAGS) $^ -o $@

build/text-slice-out-of-bounds.ll: tests/runtime/text-slice-out-of-bounds.min build/minyarc
	./build/minyarc $< $@

build/text-slice-out-of-bounds: build/text-slice-out-of-bounds.ll build/minyar-runtime.o
	$(LLVM_CC) $(LLVM_FLAGS) $^ -o $@

doctor:
	@command -v $(LLVM_CC)
	@$(LLVM_CC) --version | sed -n '1,3p'
	@echo "LLVM IR backend ready"

check-smoke: build/minyarc build/minyar-runtime.o
	$(LIMITED) sh tests/smoke.sh

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

check-memory: build/minyarc build/minyar-runtime.o
	$(LIMITED) python3 tests/memory.py

build/runtime-unit: tests/runtime-unit.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(LIMITED) $(LLVM_CC) $(CFLAGS) $< -o $@

check-runtime-unit: build/runtime-unit
	$(LIMITED) ./build/runtime-unit

build/minyar-runtime-sanitize.o: runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(SANITIZER_LIMITED) $(LLVM_CC) $(SANITIZER_FLAGS) -c $< -o $@

build/runtime-unit-sanitize: tests/runtime-unit.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(SANITIZER_LIMITED) $(LLVM_CC) $(SANITIZER_FLAGS) $< -o $@

check-modules: build/minyarc build/minyar-runtime.o
	$(LIMITED) sh tests/run-module-tests.sh

.PHONY: check-module-performance
check-module-performance: build/minyarc build/minyar-runtime.o
	$(LIMITED) python3 tests/module-performance.py

check: check-module-performance

check-fuzz: build/minyarc build/minyar-runtime.o
	$(LIMITED) python3 tests/fuzz.py

check-mutation: build/stage0 build/minyarc build/minyar-runtime.o
	$(LIMITED) python3 tests/mutation.py

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
	ASAN_OPTIONS=detect_leaks=0 $(SANITIZER_LIMITED) ./build/minyarc-sanitize src/compiler.min build/compiler-sanitized.ll
	cmp build/compiler-stage2.ll build/compiler-sanitized.ll
	cmp build/compiler-stage3.ll build/compiler-sanitized.ll

check-sanitize: check-generated-sanitizer check-sanitized-fixed-point build/minyar-runtime.o build/minyar-runtime-sanitize.o build/runtime-unit-sanitize
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize $(SANITIZER_LIMITED) sh tests/run-module-tests.sh
	ASAN_OPTIONS=detect_leaks=0 $(SANITIZER_LIMITED) python3 tests/fuzz.py --compiler build/minyarc-sanitize --cases 100 --hostile-timeout 15
	ASAN_OPTIONS=detect_leaks=0 $(SANITIZER_LIMITED) ./build/runtime-unit-sanitize
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/regressions.py
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/ownership.py
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_RUNTIME=./build/minyar-runtime-sanitize.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/memory.py Memory.test_shared_returned_and_nested_values

check-stress: build/minyarc build/minyar-runtime.o
	MINYAR_FUZZ_CASES=2000 $(LIMITED) python3 tests/fuzz.py

emit: build/hello.ll
	@echo "wrote build/hello.ll"

run: build/hello
	./build/hello

check: doctor check-smoke check-release-build check-recursive-data check-compact-ownership check-adversarial check-ownership-mutation check-regressions check-memory check-runtime-unit check-modules check-fuzz check-mutation check-performance check-scaling check-budget check-sanitize check-ownership build/compiler-stage3.ll build/hello build/language-tour build/records build/compiler-bootstrap build/hello-self-hosted build/integer-overflow build/divide-by-zero build/text-and-files build/lists build/newlines build/top-level build/top-level-exit build/list-out-of-bounds build/text-indexing build/text-slice-out-of-bounds
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
	grep -q "record fields are immutable" build/record-immutable-error.txt
	! ./build/integer-overflow > /dev/null 2> build/overflow-error.txt
	grep -q "Integer calculation is outside" build/overflow-error.txt
	! ./build/divide-by-zero > /dev/null 2> build/division-error.txt
	grep -q "Integer cannot be divided by zero" build/division-error.txt
	! ./build/list-out-of-bounds > /dev/null 2> build/list-error.txt
	grep -q "List position 1 is outside its length of 1" build/list-error.txt
	test "$$(./build/text-and-files first src/compiler.min build/written-text.txt | tr '\n' ' ')" = "6 M 42 3 first true "
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
	grep -q "line 2: expected an expression, found ')'" build/expression-error.txt
	! ./build/minyarc tests/errors/top-level-malformed-expression.min build/invalid.ll 2> build/top-level-expression-error.txt
	grep -q "line 1: expected an expression, found ')'" build/top-level-expression-error.txt
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

clean:
	rm -rf build

build/ownership-runtime.o: tests/ownership-runtime.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(SANITIZER_LIMITED) $(LLVM_CC) $(SANITIZER_FLAGS) -c $< -o $@

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

# Explicit allocator profile; this does not change the ordinary runtime target.
build/minyar-runtime-system.o: runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(LIMITED) $(LLVM_CC) $(LLVM_FLAGS) -DMINYAR_SYSTEM_HEAP=1 -c $< -o $@

# These matrices compile many sanitizer variants and reserve large virtual
# heaps. Keep them explicitly requested, outside the ordinary check target.
.PHONY: check-memory-profiles check-unary-pairs check-fused-unary
check-fused-unary:
	$(SANITIZER_LIMITED) python3 tests/fused-unary-regressions.py --clang "$(LLVM_CC)"
	$(SANITIZER_LIMITED) python3 tests/fused-work-regressions.py --clang "$(LLVM_CC)"

check-unary-pairs: check-fused-unary
	$(SANITIZER_LIMITED) python3 tests/unary-pair-regressions.py --clang "$(LLVM_CC)"

check-memory-profiles: build/minyar-runtime-system.o check-unary-pairs
	$(SANITIZER_LIMITED) python3 tests/memory-profile-regressions.py --runtime-source runtime/minyar_runtime.c --suite focused --clang "$(LLVM_CC)"
	$(SANITIZER_LIMITED) python3 tests/system-configurations.py
	$(SANITIZER_LIMITED) python3 tests/lazy-configurations.py --clang "$(LLVM_CC)"

build/minyar-runtime-bounded.o: runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(LIMITED) $(LLVM_CC) $(LLVM_FLAGS) $(BOUNDED_FLAGS) -c $< -o $@

build/bounded-runtime: tests/bounded-runtime.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(LIMITED) $(LLVM_CC) $(CFLAGS) $< -o $@

build/bounded-runtime-sanitize: tests/bounded-runtime.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(SANITIZER_LIMITED) $(LLVM_CC) $(SANITIZER_FLAGS) $< -o $@

build/bounded-ownership-runtime.o: tests/bounded-ownership-runtime.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(SANITIZER_LIMITED) $(LLVM_CC) $(SANITIZER_FLAGS) -c $< -o $@

check-recursive-data: build/minyarc build/minyarc-sanitize build/minyar-runtime.o build/ownership-runtime.o
	$(LIMITED) python3 tests/recursive-data.py
	$(LIMITED) python3 tests/production-memory.py
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/recursive-data.py
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/ownership-runtime.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/production-memory.py
	$(LIMITED) python3 experiments/memory/production-contract-model.py
	$(LIMITED) python3 tests/recursive-mutation.py

build/production-live-oracle: experiments/memory/production-live-oracle.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(SANITIZER_LIMITED) $(LLVM_CC) $(SANITIZER_FLAGS) $< -o $@

build/production-frame-oracle: experiments/memory/production-frame-oracle.c experiments/memory/production-live-oracle.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(SANITIZER_LIMITED) $(LLVM_CC) $(SANITIZER_FLAGS) $< -o $@

build/bounded-list-capacity: tests/bounded-list-capacity.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(LIMITED) $(LLVM_CC) $(CFLAGS) $< -o $@

build/bounded-list-capacity-sanitize: tests/bounded-list-capacity.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(SANITIZER_LIMITED) $(LLVM_CC) $(SANITIZER_FLAGS) $< -o $@

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

# The module frontend is optional. Its guarded build adapter is applied to the
# current core without changing the ordinary compiler or its fixed budgets.
build/module-compiler.min: src/compiler.min src/module-compiler.min src/module-compiler-adapter.patch scripts/build-module-compiler.py | build
	python3 scripts/build-module-compiler.py $@

build/module-compiler-stage1.ll: build/module-compiler.min build/minyarc
	$(LIMITED) ./build/minyarc $< $@

build/module-compiler-stage1: build/module-compiler-stage1.ll build/minyar-compiler-runtime.ll
	$(LIMITED) $(LLVM_CC) $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $^ -o $@

build/module-compiler-stage2.ll: build/module-compiler.min build/module-compiler-stage1
	$(LIMITED) ./build/module-compiler-stage1 $< $@

build/minyarc-modules: build/module-compiler-stage2.ll build/minyar-compiler-runtime.ll
	$(LIMITED) $(LLVM_CC) $(LLVM_FLAGS) $(COMPILER_LTO_FLAGS) $^ -o $@

build/module-compiler-stage3.ll: build/module-compiler.min build/minyarc-modules
	$(LIMITED) ./build/minyarc-modules $< $@

build/minyar-module-build: tools/module-build.c | build
	$(LIMITED) $(CC) $(CFLAGS) $< -o $@

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

build/module-compiler-sanitize.ll: build/module-compiler-stage2.ll tests/llvm_sanitizer.py
	$(SANITIZER_LIMITED) python3 tests/llvm_sanitizer.py $< $@

build/minyarc-modules-sanitize: build/module-compiler-sanitize.ll build/minyar-compiler-runtime-sanitize.o
	$(SANITIZER_LIMITED) $(LLVM_CC) $(SANITIZER_FLAGS) $^ -o $@

build/minyar-module-build-sanitize: tools/module-build.c | build
	$(SANITIZER_LIMITED) $(CC) -std=c11 -Wall -Wextra -Werror $(SANITIZER_FLAGS) $< -o $@

.PHONY: check-incremental-modules-sanitize
check-incremental-modules-sanitize: build/minyarc-modules-sanitize build/minyar-module-build-sanitize build/minyarc-modules build/minyar-module-build build/minyar-runtime.o build/minyar-runtime-sanitize.o build/ownership-runtime.o
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-modules-sanitize $(SANITIZER_LIMITED) python3 tests/incremental-modules.py
	ASAN_OPTIONS=detect_leaks=0 MINYAR_MODULE_DRIVER=./build/minyar-module-build-sanitize $(SANITIZER_LIMITED) python3 tests/incremental-module-driver.py
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-modules-sanitize MINYAR_MODULE_DRIVER=./build/minyar-module-build-sanitize $(SANITIZER_LIMITED) python3 tests/incremental-module-delta.py
	$(SANITIZER_LIMITED) python3 tests/incremental-module-regressions.py --sanitize

.PHONY: check-incremental-module-mutation
check-incremental-module-mutation: build/minyarc-modules build/module-compiler.min
	$(LIMITED) python3 tests/incremental-module-mutation.py
