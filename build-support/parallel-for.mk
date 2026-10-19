.PHONY: check-parallel-for check-parallel-for-sanitize

check-parallel-for: build/minyarc build/minyar-runtime.o build/tooling/tests/parallel-for
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/parallel-for
	MINYAR_PARALLEL_MODULES=1 MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) ./build/tooling/tests/parallel-for

check-parallel-for-sanitize: build/minyarc-sanitize build/minyar-runtime-sanitize.o build/tooling/tests/parallel-for
	ASAN_OPTIONS=detect_leaks=0 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/parallel-for
	ASAN_OPTIONS=detect_leaks=0 MINYAR_PARALLEL_MODULES=1 MINYAR_TEST_COMPILER=./build/minyarc-sanitize MINYAR_TEST_CLANG="$(LLVM_CC)" MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined $(SANITIZER_LIMITED) ./build/tooling/tests/parallel-for

check check-portable: check-parallel-for
check-sanitize: check-parallel-for-sanitize
