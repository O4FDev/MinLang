.PHONY: check-text-basics check-text-basics-sanitize check-text-basics-models benchmark-text-basics

check-text-basics: build/minyarc build/minyar-runtime.o build/minyarc-callbacks build/minyarc-errors build/tooling/tests/text-basics-callbacks build/tooling/tests/text-basics-errors
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/text-basics.py
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/text-basics-callbacks
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/text-basics-errors

build/text-basics-ownership.o: tests/memory-contracts-runtime.c runtime/minyar_runtime.c $(RUNTIME_HEADERS) | build
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(SANITIZER_FLAGS) -DMINYAR_SYSTEM_HEAP=1 -c $< -o $@

check-text-basics-sanitize: build/minyarc-sanitize build/text-basics-ownership.o build/minyarc-callbacks-sanitize build/minyarc-errors-sanitize build/tooling/tests/text-basics-callbacks build/tooling/tests/text-basics-errors
	MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_RUNTIME=./build/text-basics-ownership.o MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) python3 tests/text-basics.py
	MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/text-basics-callbacks
	MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/text-basics-errors

# Each model configuration is its own phony child, so a parallel runner can
# schedule them apart; publish_engine writes the shared cycle engine atomically.
.PHONY: check-text-basics-models-plain check-text-basics-models-cycles check-text-basics-models-cycles-budget1
check-text-basics-models: check-text-basics-models-plain check-text-basics-models-cycles check-text-basics-models-cycles-budget1

check-text-basics-models-plain:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/text-basics-model.py

check-text-basics-models-cycles:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/text-basics-model.py --cycles

check-text-basics-models-cycles-budget1:
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(SANITIZER_LIMITED) python3 tests/text-basics-model.py --cycles --budget 1

check check-portable: check-text-basics check-text-basics-models
check-sanitize: check-text-basics-sanitize

benchmark-text-basics: build/minyarc build/minyar-runtime.o build/minyarc-baseline
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/text-basics-benchmark.py --baseline-compiler build/minyarc-baseline --output build/text-basics-benchmark.json
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/text-basics-benchmark.py --fixture text-find-prefixes --output build/text-find-prefixes-benchmark.json
